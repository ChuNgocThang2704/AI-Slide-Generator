package com.backend.documentservice.service;

import com.backend.documentservice.exception.AppException;
import com.backend.documentservice.exception.ErrorCode;
import com.backend.documentservice.util.Constants;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.FileSystemResource;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.http.converter.StringHttpMessageConverter;
import org.springframework.stereotype.Service;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.HttpStatusCodeException;
import org.springframework.web.client.RestTemplate;
import software.amazon.awssdk.core.ResponseInputStream;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.GetObjectRequest;
import software.amazon.awssdk.services.s3.model.GetObjectResponse;

import java.io.File;
import java.net.URL;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.time.Duration;
import java.util.function.Consumer;

@Service
@Slf4j
public class AiService {

    private static final Duration AI_POLL_INTERVAL = Duration.ofSeconds(2);
    private static final Duration AI_MAX_WAIT = Duration.ofMinutes(20);

    private final ObjectMapper objectMapper;
    private final S3Client s3Client;
    private final RestTemplate restTemplate;

    @Value("${aws.s3.bucket}")
    private String bucketName;

    @Value("${app.ai.url}")
    private String aiUrl;

    public AiService(ObjectMapper objectMapper, S3Client s3Client) {
        this.objectMapper = objectMapper;
        this.s3Client = s3Client;

        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(5000);
        factory.setReadTimeout((int) AI_MAX_WAIT.toMillis());

        this.restTemplate = new RestTemplate(factory);
        this.restTemplate.getMessageConverters().removeIf(c -> c instanceof StringHttpMessageConverter);
        this.restTemplate.getMessageConverters().add(0, new StringHttpMessageConverter(StandardCharsets.UTF_8));
    }

    public JsonNode generateSlides(String prompt, String documentUrl, String fileName, String userRole, Consumer<String> taskIdConsumer) throws JsonProcessingException {
        String submitUrl = buildAiUrl("/api/generate-slide-spec");
        log.info("[document-service] Calling AI submit endpoint: {}", submitUrl);

        File tempFile = null;
        if (documentUrl != null && !documentUrl.isBlank()) {
            log.info("[document-service] Downloading source document from S3 for AI request: {}", documentUrl);
            tempFile = downloadFileToTemp(documentUrl, fileName);
        }

        try {
            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.MULTIPART_FORM_DATA);

            MultiValueMap<String, Object> body = new LinkedMultiValueMap<>();
            body.add("text", prompt != null ? prompt : "");
            body.add("plan", resolveAiPlan(userRole));
            body.add("generate_images", "true");
            body.add("image_limit", null);

            if (tempFile != null && tempFile.exists() && tempFile.length() > 0) {
                FileSystemResource fileResource = new FileSystemResource(tempFile);

                String contentType = "application/octet-stream";
                String nameToUse = tempFile.getName();
                if (nameToUse.toLowerCase().endsWith(".pdf")) {
                    contentType = "application/pdf";
                } else if (nameToUse.toLowerCase().endsWith(".docx")) {
                    contentType = "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
                } else if (nameToUse.toLowerCase().endsWith(".txt")) {
                    contentType = "text/plain";
                }

                HttpHeaders fileHeaders = new HttpHeaders();
                fileHeaders.setContentType(MediaType.parseMediaType(contentType));
                HttpEntity<FileSystemResource> filePart = new HttpEntity<>(fileResource, fileHeaders);

                body.add("file", filePart);
                log.info("[document-service] Attached source file to AI request: {}", nameToUse);
            } else {
                log.info("[document-service] No source document attached to AI request");
            }

            HttpEntity<MultiValueMap<String, Object>> requestEntity = new HttpEntity<>(body, headers);
            String responseStr = restTemplate.postForObject(submitUrl, requestEntity, String.class);
            JsonNode submitResponse = objectMapper.readTree(responseStr);

            if (submitResponse.hasNonNull("deck")) {
                return submitResponse;
            }

            String taskId = submitResponse.path("task_id").asText("");
            if (taskId.isBlank()) {
                throw new RuntimeException("AI submit response does not contain task_id: " + responseStr);
            }

            if (taskIdConsumer != null) {
                try {
                    taskIdConsumer.accept(taskId);
                } catch (Exception e) {
                    log.warn("[document-service] Error invoking taskIdConsumer", e);
                }
            }

            log.info("[document-service] AI task submitted, task_id={}", taskId);
            return waitForCompletedSpec(taskId);
        } catch (HttpStatusCodeException e) {
            String responseBody = e.getResponseBodyAsString();
            String errorMessage = null;
            try {
                JsonNode errorNode = objectMapper.readTree(responseBody);
                if (errorNode.hasNonNull("detail")) {
                    errorMessage = errorNode.path("detail").asText();
                } else if (errorNode.hasNonNull("message")) {
                    errorMessage = errorNode.path("message").asText();
                }
            } catch (Exception jsonEx) {
                // Ignore
            }
            if (errorMessage == null || errorMessage.isBlank()) {
                errorMessage = "AI API error (" + e.getStatusCode() + "): " + responseBody;
            }
            throw new com.backend.documentservice.exception.AppException(com.backend.documentservice.exception.ErrorCode.AI_API_ERROR, errorMessage);
        } finally {
            if (tempFile != null && tempFile.exists()) {
                try {
                    boolean deleted = tempFile.delete();
                    log.info("[document-service] Deleted temp AI source file: {}, result={}", tempFile.getAbsolutePath(), deleted);
                } catch (Exception e) {
                    log.warn("[document-service] Could not delete temp AI source file: {}", tempFile.getAbsolutePath(), e);
                }
            }
        }
    }

    private JsonNode waitForCompletedSpec(String taskId) throws JsonProcessingException, AppException {
        String statusUrl = buildAiUrl("/api/status/" + taskId);
        long deadline = System.currentTimeMillis() + AI_MAX_WAIT.toMillis();

        while (System.currentTimeMillis() < deadline) {
            try {
                String statusResponseStr = restTemplate.getForObject(statusUrl, String.class);
                JsonNode statusResponse = objectMapper.readTree(statusResponseStr);
                String status = statusResponse.path("status").asText("");
                int progress = statusResponse.path("progress").asInt(-1);
                log.info("[document-service] AI task {} status={}, progress={}", taskId, status, progress);

                if ("completed".equalsIgnoreCase(status)) {
                    JsonNode result = statusResponse.path("result");
                    if (result.isMissingNode() || result.isNull() || !result.hasNonNull("deck")) {
                        throw new com.backend.documentservice.exception.AppException(com.backend.documentservice.exception.ErrorCode.AI_API_ERROR, "Tác vụ AI hoàn thành nhưng không có dữ liệu slide.");
                    }
                    return result;
                }

                if ("error".equalsIgnoreCase(status) || "failed".equalsIgnoreCase(status)) {
                    String message = statusResponse.path("result").path("error").asText(statusResponse.toString());
                    throw new com.backend.documentservice.exception.AppException(com.backend.documentservice.exception.ErrorCode.AI_API_ERROR, message);
                }

                if ("cancelled".equalsIgnoreCase(status) || "canceled".equalsIgnoreCase(status)) {
                    throw new com.backend.documentservice.exception.AppException(com.backend.documentservice.exception.ErrorCode.AI_API_ERROR, "Tác vụ tạo slide đã bị hủy.");
                }

                Thread.sleep(AI_POLL_INTERVAL.toMillis());
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                throw new RuntimeException("Interrupted while waiting for AI task: " + taskId, e);
            } catch (HttpStatusCodeException e) {
                String responseBody = e.getResponseBodyAsString();
                String errorMessage = null;
                try {
                    JsonNode errorNode = objectMapper.readTree(responseBody);
                    if (errorNode.hasNonNull("detail")) {
                        errorMessage = errorNode.path("detail").asText();
                    } else if (errorNode.hasNonNull("message")) {
                        errorMessage = errorNode.path("message").asText();
                    }
                } catch (Exception jsonEx) {
                    // Ignore
                }
                if (errorMessage == null || errorMessage.isBlank()) {
                    errorMessage = "AI status API error (" + e.getStatusCode() + "): " + responseBody;
                }
                throw new AppException(ErrorCode.AI_API_ERROR, errorMessage);
            }
        }

        throw new AppException(ErrorCode.AI_API_ERROR, "Thời gian chờ tác vụ AI vượt quá giới hạn.");
    }

    private String buildAiUrl(String path) {
        String base = aiUrl == null || aiUrl.isBlank() ? "http://20.196.129.89:8000" : aiUrl.trim();
        while (base.endsWith("/")) {
            base = base.substring(0, base.length() - 1);
        }
        if (base.endsWith("/api")) {
            base = base.substring(0, base.length() - "/api".length());
        }
        return base + path;
    }

    private String resolveAiPlan(String userRole) {
        if (userRole == null || userRole.isBlank()) {
            return "free";
        }
        String normalizedRole = userRole.toLowerCase();
        if (Constants.USER_ROLES.USER_ULTRA.equalsIgnoreCase(userRole) || normalizedRole.contains("extra") || normalizedRole.contains("ultra")) {
            return "ultra";
        }
        if (Constants.USER_ROLES.USER_PRO.equalsIgnoreCase(userRole) || normalizedRole.contains("pro")) {
            return "pro";
        }
        return "free";
    }

    private File downloadFileToTemp(String fileUrl, String originalFileName) {
        try {
            String key = extractS3KeyFromUrl(fileUrl);
            if (key == null) {
                log.warn("Could not extract S3 key from URL: {}", fileUrl);
                return null;
            }

            String suffix = ".tmp";
            if (originalFileName != null && !originalFileName.isBlank()) {
                int dotIndex = originalFileName.lastIndexOf('.');
                if (dotIndex != -1) {
                    suffix = originalFileName.substring(dotIndex).toLowerCase();
                }
            }

            Path tempFilePath = Files.createTempFile("slide-doc-", suffix);
            File tempFile = tempFilePath.toFile();
            tempFile.deleteOnExit();

            GetObjectRequest getObjectRequest = GetObjectRequest.builder()
                    .bucket(bucketName.trim())
                    .key(key)
                    .build();

            try (ResponseInputStream<GetObjectResponse> s3Stream = s3Client.getObject(getObjectRequest)) {
                Files.copy(s3Stream, tempFilePath, StandardCopyOption.REPLACE_EXISTING);
            }
            log.info("Downloaded source document to temp file: {}, size={} bytes", tempFile.getAbsolutePath(), tempFile.length());
            return tempFile;
        } catch (Exception e) {
            log.error("Error downloading S3 file to temp file: {}", fileUrl, e);
            return null;
        }
    }

    private String extractS3KeyFromUrl(String url) {
        try {
            String cleanUrl = url.contains("?") ? url.split("\\?")[0] : url;
            URL parsedUrl = new URL(cleanUrl);
            String path = parsedUrl.getPath();

            path = URLDecoder.decode(path, StandardCharsets.UTF_8);

            if (path.startsWith("/")) {
                path = path.substring(1);
            }

            String bName = bucketName.trim();
            if (path.startsWith(bName + "/")) {
                path = path.substring(bName.length() + 1);
            }

            return path;
        } catch (Exception e) {
            log.error("Error extracting S3 key from URL: {}", url);
            return null;
        }
    }

    public JsonNode checkAiTaskStatus(String taskId) {
        String statusUrl = buildAiUrl("/api/status/" + taskId);
        log.info("[document-service] Checking AI task status: {}", statusUrl);
        try {
            String responseStr = restTemplate.getForObject(statusUrl, String.class);
            return objectMapper.readTree(responseStr);
        } catch (Exception e) {
            log.error("[document-service] Error checking AI task status: {}", taskId, e);
            throw new RuntimeException("Lỗi kiểm tra trạng thái AI task: " + e.getMessage(), e);
        }
    }

    public JsonNode cancelAiTask(String taskId) {
        String cancelUrl = buildAiUrl("/api/cancel/" + taskId);
        log.info("[document-service] Cancelling AI task: {}", cancelUrl);
        try {
            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_JSON);
            HttpEntity<String> entity = new HttpEntity<>("{}", headers);
            String responseStr = restTemplate.postForObject(cancelUrl, entity, String.class);
            return objectMapper.readTree(responseStr);
        } catch (Exception e) {
            log.error("[document-service] Error cancelling AI task: {}", taskId, e);
            throw new RuntimeException("Lỗi hủy AI task: " + e.getMessage(), e);
        }
    }
}
