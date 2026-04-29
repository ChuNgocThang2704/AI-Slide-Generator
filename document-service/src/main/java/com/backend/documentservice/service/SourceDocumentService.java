package com.backend.documentservice.service;

import com.backend.documentservice.dto.request.SourceDocumentSaveRequest;
import com.backend.documentservice.dto.response.SourceDocumentResponse;
import com.backend.documentservice.dto.response.PageResponse;
import com.backend.documentservice.entity.SourceDocument;
import com.backend.documentservice.exception.AppException;
import com.backend.documentservice.exception.ErrorCode;
import com.backend.documentservice.mapper.SourceDocumentMapper;
import com.backend.documentservice.repository.SourceDocumentRepository;
import com.backend.documentservice.util.Constants;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;
import software.amazon.awssdk.core.sync.RequestBody;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.S3Utilities;
import software.amazon.awssdk.services.s3.model.DeleteObjectsRequest;
import software.amazon.awssdk.services.s3.model.GetUrlRequest;
import software.amazon.awssdk.services.s3.model.ObjectIdentifier;
import software.amazon.awssdk.services.s3.model.PutObjectRequest;
import software.amazon.awssdk.services.s3.model.GetObjectRequest;
import software.amazon.awssdk.services.s3.presigner.S3Presigner;
import software.amazon.awssdk.services.s3.presigner.model.GetObjectPresignRequest;
import java.net.URL;
import java.time.Duration;

import java.io.IOException;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
@Slf4j
public class SourceDocumentService {

    private final SourceDocumentRepository sourceDocumentRepository;
    private final SourceDocumentMapper sourceDocumentMapper;
    private final S3Client s3Client;
    private final S3Presigner s3Presigner;

    @Value("${aws.s3.bucket}")
    private String bucketName;

    @Value("${aws.region}")
    private String region;

    @Transactional
    public Map<String, Object> uploadFileOnly(UUID userId, MultipartFile file) {
        log.info("[document-service] upload file lên S3: {} cho user: {}", file.getOriginalFilename(), userId);

        String fileName = file.getOriginalFilename();
        String s3Key = "documents/" + userId + "/" + UUID.randomUUID() + "_" + fileName;

        try {
            s3Client.putObject(PutObjectRequest.builder()
                            .bucket(bucketName)
                            .key(s3Key)
                            .contentType(file.getContentType())
                            .build(),
                    RequestBody.fromInputStream(file.getInputStream(), file.getSize()));

            S3Utilities s3Utilities = s3Client.utilities();
            GetUrlRequest request = GetUrlRequest.builder().bucket(bucketName).key(s3Key).build();
            String url = s3Utilities.getUrl(request).toExternalForm();
            
            Map<String, Object> result = new HashMap<>();
            result.put("url", url);
            result.put("fileName", fileName);
            result.put("fileSize", file.getSize());
            return result;
        } catch (IOException e) {
            throw new RuntimeException("Upload failed", e);
        }
    }

    @Transactional
    public SourceDocumentResponse saveDocumentMetadata(UUID userId, SourceDocumentSaveRequest request) {
        log.info("[document-service] lưu metadata tài liệu: {}, url: {}", request.getFileName(), request.getUrl());

        SourceDocument doc = SourceDocument.builder()
                .userId(userId)
                .fileName(request.getFileName())
                .url(request.getUrl())
                .fileSize(request.getFileSize())
                .fileType(determineFileType(request.getFileName()))
                .build();

        SourceDocument saved = sourceDocumentRepository.save(doc);
        return sourceDocumentMapper.toDto(saved);
    }

    public PageResponse<SourceDocumentResponse> getDocumentsByUser(UUID userId, String search, int page, int size) {
        log.info("[document-service] lấy danh sách tài liệu phân trang cho user: {}, search: {}", userId, search);
        Pageable pageable = PageRequest.of(page, size, Sort.by("createdAt").descending());
        
        Page<SourceDocument> docPage;
        if (search != null && !search.isBlank()) {
            docPage = sourceDocumentRepository.findByUserIdAndFileNameContainingIgnoreCase(userId, search, pageable);
        } else {
            docPage = sourceDocumentRepository.findByUserId(userId, pageable);
        }
        
        return PageResponse.<SourceDocumentResponse>builder()
                .page(docPage.getNumber())
                .size(docPage.getSize())
                .totalElements(docPage.getTotalElements())
                .totalPages(docPage.getTotalPages())
                .items(docPage.getContent().stream().map(sourceDocumentMapper::toDto).collect(Collectors.toList()))
                .build();
    }

    public SourceDocumentResponse getDocument(UUID id, UUID userId) {
        log.info("[document-service] lấy chi tiết tài liệu id: {} của user: {}", id, userId);

        SourceDocument entity = sourceDocumentRepository.findById(id)
                .orElseThrow(() -> new AppException(ErrorCode.DOCUMENT_NOT_FOUND));

        if (!entity.getUserId().equals(userId)) {
            throw new AppException(ErrorCode.ACCESS_DENIED);
        }

        return sourceDocumentMapper.toDto(entity);
    }

    public String generatePresignedViewUrl(UUID id, UUID userId) {
        log.info("[document-service] tạo pre-signed URL xem tài liệu id: {} cho user: {}", id, userId);
        SourceDocument doc = sourceDocumentRepository.findById(id)
                .orElseThrow(() -> new AppException(ErrorCode.DOCUMENT_NOT_FOUND));

        if (!doc.getUserId().equals(userId)) {
            throw new AppException(ErrorCode.ACCESS_DENIED);
        }

        String key = extractS3KeyFromUrl(doc.getUrl());

        if (key == null) throw new AppException(ErrorCode.DOCUMENT_NOT_FOUND);

        GetObjectRequest getObjectRequest = GetObjectRequest.builder()
                .bucket(bucketName.trim())
                .key(key)
                .build();

        GetObjectPresignRequest presignRequest = GetObjectPresignRequest.builder()
                .signatureDuration(Duration.ofMinutes(120))
                .getObjectRequest(getObjectRequest)
                .build();

        return s3Presigner.presignGetObject(presignRequest).url().toString();
    }

    @Transactional
    public void deleteDocuments(List<UUID> ids, UUID userId) {
        log.info("[document-service] xóa {} tài liệu của user: {}", ids.size(), userId);

        List<SourceDocument> docs = sourceDocumentRepository.findAllById(ids);

        for (SourceDocument doc : docs) {
            if (!doc.getUserId().equals(userId)) {
                throw new AppException(ErrorCode.ACCESS_DENIED);
            }
        }

        List<ObjectIdentifier> s3Objects = docs.stream()
                .filter(doc -> doc.getUrl() != null)
                .map(doc -> {
                    String key = extractS3KeyFromUrl(doc.getUrl());
                    return ObjectIdentifier.builder().key(key).build();
                })
                .collect(Collectors.toList());

        if (!s3Objects.isEmpty()) {
            s3Client.deleteObjects(DeleteObjectsRequest.builder()
                    .bucket(bucketName)
                    .delete(d -> d.objects(s3Objects))
                    .build());
        }

        sourceDocumentRepository.deleteAllById(ids);
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
            log.error("Could not extract S3 key from URL: {}", url);
            return null;
        }
    }

    private Integer determineFileType(String fileName) {
        if (fileName == null) return Constants.DOCUMENT_TYPE.TEXT_PROMPT;
        String lower = fileName.toLowerCase();
        if (lower.endsWith(".pdf")) return Constants.DOCUMENT_TYPE.PDF;
        if (lower.endsWith(".docx")) return Constants.DOCUMENT_TYPE.DOCX;
        return Constants.DOCUMENT_TYPE.TEXT_PROMPT;
    }
}
