package com.backend.documentservice.service;

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
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;

@Service
@Slf4j
public class AiService {

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
        factory.setReadTimeout(900000); // 15 minutes timeout for AI response

        this.restTemplate = new RestTemplate(factory);
        this.restTemplate.getMessageConverters().removeIf(c -> c instanceof StringHttpMessageConverter);
        this.restTemplate.getMessageConverters().add(0, new StringHttpMessageConverter(StandardCharsets.UTF_8));
    }

    public JsonNode generateSlides(String prompt, String documentUrl, String fileName, String userRole) throws JsonProcessingException {
        String aiURLGenerate = aiUrl;
        if (aiURLGenerate != null && !aiURLGenerate.endsWith("/generate-spec")) {
            aiURLGenerate = aiURLGenerate.endsWith("/") ? aiURLGenerate + "generate-spec" : aiURLGenerate + "/generate-spec";
        }
        log.info("[document-service] Gọi AI tại: {} cho prompt: {}", aiURLGenerate, prompt);
        
        File tempFile = null;
        if (documentUrl != null && !documentUrl.isBlank()) {
            log.info("[document-service] Đang tải file tài liệu từ S3 để gửi sang AI: {}", documentUrl);
            tempFile = downloadFileToTemp(documentUrl, fileName);
        }

        try {
            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.MULTIPART_FORM_DATA);

            // Xác định plan ("free", "pro" hay "extra") dựa theo role tài khoản
            String plan = "free";
            if (userRole != null) {
                if (userRole.equalsIgnoreCase(Constants.USER_ROLES.USER_PRO) || userRole.toLowerCase().contains("pro")) {
                    plan = "pro";
                } else if (userRole.equalsIgnoreCase(Constants.USER_ROLES.USER_EXTRA) || userRole.toLowerCase().contains("extra")) {
                    plan = "extra";
                }
            }

            // Phân tích slide_count từ prompt, mặc định là 10
            String slideCount = parseSlideCount(prompt);

            MultiValueMap<String, Object> body = new LinkedMultiValueMap<>();
            body.add("text", prompt != null ? prompt : "");
            body.add("plan", plan);
            body.add("slide_count", slideCount);
            body.add("slide_theme", "modern");
            body.add("generate_images", "true");
            body.add("include_image_base64", "false");

            if (tempFile != null && tempFile.exists() && tempFile.length() > 0) {
                FileSystemResource fileResource = new FileSystemResource(tempFile);

                // Xác định content type của file
                String contentType = "application/octet-stream";
                String nameToUse = tempFile.getName();
                if (nameToUse.toLowerCase().endsWith(".pdf")) {
                    contentType = "application/pdf";
                } else if (nameToUse.toLowerCase().endsWith(".docx")) {
                    contentType = "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
                }

                HttpHeaders fileHeaders = new HttpHeaders();
                fileHeaders.setContentType(MediaType.parseMediaType(contentType));
                HttpEntity<FileSystemResource> filePart = new HttpEntity<>(fileResource, fileHeaders);

                body.add("file", filePart);
                log.info("[document-service] Đính kèm file '{}' vào request AI", nameToUse);
            } else {
                log.info("[document-service] Không gửi kèm tài liệu");
            }

            HttpEntity<MultiValueMap<String, Object>> requestEntity = new HttpEntity<>(body, headers);

            log.info("[document-service] Gửi request POST tới AI API: {}", aiURLGenerate);
            String responseStr = restTemplate.postForObject(aiURLGenerate, requestEntity, String.class);
            log.info("[document-service] AI API trả về kết quả thành công.");

            return objectMapper.readTree(responseStr);
        } catch (HttpStatusCodeException e) {
            throw new RuntimeException("Lỗi gọi AI API (" + e.getStatusCode() + "): " + e.getResponseBodyAsString(), e);
        } finally {
            // Delete temp file after execution
            if (tempFile != null && tempFile.exists()) {
                try {
                    boolean deleted = tempFile.delete();
                    log.info("[document-service] Xóa file tạm S3: {}, kết quả: {}", tempFile.getAbsolutePath(), deleted);
                } catch (Exception e) {
                    log.warn("[document-service] Lỗi khi xóa file tạm: {}", tempFile.getAbsolutePath(), e);
                }
            }
        }
    }

    private File downloadFileToTemp(String fileUrl, String originalFileName) {
        try {
            String key = extractS3KeyFromUrl(fileUrl);
            if (key == null) {
                log.warn("Không thể trích xuất từ URL: {}", fileUrl);
                return null;
            }
            log.info("Bắt đầu tải file từ S3");

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
            log.info("Tải file thành công về đường dẫn tạm: {}, kích thước: {} bytes", tempFile.getAbsolutePath(), tempFile.length());
            return tempFile;
        } catch (Exception e) {
            log.error("Lỗi khi tải file từ S3 về file tạm: {}", fileUrl, e);
            return null;
        }
    }

    private String extractS3KeyFromUrl(String url) {
        try {
            String cleanUrl = url.contains("?") ? url.split("\\?")[0] : url;
            URL parsedUrl = new URL(cleanUrl);
            String path = parsedUrl.getPath();

            path = java.net.URLDecoder.decode(path, java.nio.charset.StandardCharsets.UTF_8);

            if (path.startsWith("/")) {
                path = path.substring(1);
            }

            String bName = bucketName.trim();
            if (path.startsWith(bName + "/")) {
                path = path.substring(bName.length() + 1);
            }
            
            return path;
        } catch (Exception e) {
            log.error("Lỗi trích xuất S3 Key từ URL: {}", url);
            return null;
        }
    }

    private String parseSlideCount(String prompt) {
        if (prompt == null || prompt.isBlank()) {
            return "10";
        }
        // Tìm số trang từ prompt tiếng Việt và tiếng Anh (ví dụ: "15 trang", "8 slide", "12 pages")
        java.util.regex.Pattern pattern = java.util.regex.Pattern.compile(
                "\\b(\\d+)\\s*(trang|slide|slides|page|pages)\\b", 
                java.util.regex.Pattern.CASE_INSENSITIVE
        );
        java.util.regex.Matcher matcher = pattern.matcher(prompt);
        if (matcher.find()) {
            try {
                int count = Integer.parseInt(matcher.group(1));
                if (count > 0 && count <= 50) { // Giới hạn từ 1 đến 50 slide
                    return String.valueOf(count);
                }
            } catch (NumberFormatException e) {
                // ignore
            }
        }
        return "10";
    }
}
