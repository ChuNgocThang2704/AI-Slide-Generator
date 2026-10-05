package com.backend.documentservice.service;

import com.backend.documentservice.exception.AppException;
import com.backend.documentservice.exception.ErrorCode;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.ByteArrayResource;
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
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.nio.charset.StandardCharsets;

/**
 * Lecture script for an uploaded deck (ai-service /api/lecture-script). A feature of its own:
 * nothing is stored and no project is involved, the deck is read and the script handed back.
 */
@Service
@Slf4j
public class LectureScriptService {

    private final ObjectMapper objectMapper;
    private final RestTemplate restTemplate;

    @Value("${app.ai.url}")
    private String aiUrl;

    public LectureScriptService(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(5000);
        factory.setReadTimeout(60000);
        this.restTemplate = new RestTemplate(factory);
        this.restTemplate.getMessageConverters().removeIf(c -> c instanceof StringHttpMessageConverter);
        this.restTemplate.getMessageConverters().add(0, new StringHttpMessageConverter(StandardCharsets.UTF_8));
    }

    public JsonNode start(MultipartFile file, String prompt) {
        if (file == null || file.isEmpty()) {
            throw new AppException(ErrorCode.INVALID_KEY, "Hãy chọn file slide (.pptx hoặc .pdf)");
        }
        final String filename = file.getOriginalFilename() == null ? "slides.pptx" : file.getOriginalFilename();
        byte[] bytes;
        try {
            bytes = file.getBytes();
        } catch (IOException exception) {
            throw new AppException(ErrorCode.INVALID_KEY, "Không đọc được file tải lên");
        }
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.MULTIPART_FORM_DATA);
        MultiValueMap<String, Object> body = new LinkedMultiValueMap<>();
        body.add("file", new ByteArrayResource(bytes) {
            @Override
            public String getFilename() {
                return filename;
            }
        });
        body.add("prompt", prompt == null ? "" : prompt);
        return call("/api/lecture-script/generate", new HttpEntity<>(body, headers));
    }

    public JsonNode revise(JsonNode request) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        return call("/api/lecture-script/revise", new HttpEntity<>(request.toString(), headers));
    }

    public JsonNode status(String taskId) {
        try {
            return objectMapper.readTree(restTemplate.getForObject(url("/api/status/" + taskId), String.class));
        } catch (HttpStatusCodeException exception) {
            throw failure(exception);
        } catch (Exception exception) {
            log.warn("[document-service] Lecture script status failed: {}", exception.getMessage());
            throw new AppException(ErrorCode.UNCATEGORIZED_EXCEPTION, "Không kết nối được dịch vụ AI");
        }
    }

    public byte[] export(JsonNode request) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        try {
            return restTemplate.postForObject(
                    url("/api/lecture-script/export"), new HttpEntity<>(request.toString(), headers), byte[].class);
        } catch (HttpStatusCodeException exception) {
            throw failure(exception);
        } catch (Exception exception) {
            log.warn("[document-service] Lecture script export failed: {}", exception.getMessage());
            throw new AppException(ErrorCode.UNCATEGORIZED_EXCEPTION, "Không xuất được file Excel");
        }
    }

    private JsonNode call(String path, HttpEntity<?> entity) {
        try {
            return objectMapper.readTree(restTemplate.postForObject(url(path), entity, String.class));
        } catch (HttpStatusCodeException exception) {
            throw failure(exception);
        } catch (Exception exception) {
            log.warn("[document-service] Lecture script call {} failed: {}", path, exception.getMessage());
            throw new AppException(ErrorCode.UNCATEGORIZED_EXCEPTION, "Không kết nối được dịch vụ AI");
        }
    }

    /** The reason ai-service gave ({"detail": "..."}) reaches the user as it is. */
    private AppException failure(HttpStatusCodeException exception) {
        String message = "Không xử lý được yêu cầu";
        try {
            JsonNode detail = objectMapper.readTree(exception.getResponseBodyAsString(StandardCharsets.UTF_8)).path("detail");
            if (detail.isTextual() && !detail.asText().isBlank()) {
                message = detail.asText();
            }
        } catch (Exception ignored) {
            // keep the generic message
        }
        return new AppException(
                exception.getStatusCode().is4xxClientError() ? ErrorCode.INVALID_KEY : ErrorCode.UNCATEGORIZED_EXCEPTION,
                message);
    }

    private String url(String path) {
        String base = aiUrl == null ? "" : aiUrl.trim();
        while (base.endsWith("/")) {
            base = base.substring(0, base.length() - 1);
        }
        if (base.endsWith("/api")) {
            base = base.substring(0, base.length() - "/api".length());
        }
        return base + path;
    }
}
