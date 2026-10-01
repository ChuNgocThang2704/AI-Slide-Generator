package com.backend.templateservice.service;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;
import software.amazon.awssdk.core.sync.RequestBody;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.DeleteObjectRequest;
import software.amazon.awssdk.services.s3.model.PutObjectRequest;

import java.io.IOException;
import java.util.UUID;

import software.amazon.awssdk.services.s3.presigner.S3Presigner;
import software.amazon.awssdk.services.s3.presigner.model.GetObjectPresignRequest;
import software.amazon.awssdk.services.s3.model.GetObjectRequest;
import java.time.Duration;

@Service
@RequiredArgsConstructor
@Slf4j
public class S3Service {

    private final S3Client s3Client;
    private final S3Presigner s3Presigner;

    @Value("${aws.s3.bucket}")
    private String bucketName;

    @Value("${aws.region}")
    private String region;

    public String uploadFile(MultipartFile file, String folderPath) throws IOException {
        String originalFilename = file.getOriginalFilename();
        String extension = "";
        if (originalFilename != null && originalFilename.contains(".")) {
            extension = originalFilename.substring(originalFilename.lastIndexOf("."));
        }

        String key = folderPath + "/" + UUID.randomUUID() + extension;

        PutObjectRequest putObjectRequest = PutObjectRequest.builder()
                .bucket(bucketName)
                .key(key)
                .contentType(file.getContentType())
                .build();

        s3Client.putObject(putObjectRequest, RequestBody.fromBytes(file.getBytes()));

        return String.format("https://%s.s3.%s.amazonaws.com/%s", bucketName, region, key);
    }

    public void putBytes(String key, byte[] data, String contentType) {
        PutObjectRequest request = PutObjectRequest.builder()
                .bucket(bucketName)
                .key(key)
                .contentType(contentType)
                .build();
        s3Client.putObject(request, RequestBody.fromBytes(data));
    }

    /** Returns the object bytes, or null when it does not exist. */
    public byte[] getBytes(String key) {
        try {
            return s3Client.getObjectAsBytes(GetObjectRequest.builder().bucket(bucketName).key(key).build()).asByteArray();
        } catch (Exception exception) {
            log.warn("Cannot read S3 object {}: {}", key, exception.getMessage());
            return null;
        }
    }

    /** Bytes of an object addressed by this bucket's public-style url; null if unknown. */
    public byte[] getBytesFromUrl(String fileUrl) {
        String bucketDomain = String.format("https://%s.s3.%s.amazonaws.com/", bucketName, region);
        if (fileUrl == null || !fileUrl.startsWith(bucketDomain)) return null;
        return getBytes(fileUrl.substring(bucketDomain.length()));
    }

    public void deleteKey(String key) {
        try {
            s3Client.deleteObject(DeleteObjectRequest.builder().bucket(bucketName).key(key).build());
        } catch (Exception exception) {
            log.warn("Cannot delete S3 object {}: {}", key, exception.getMessage());
        }
    }

    public void deleteFile(String fileUrl) {
        if (fileUrl == null || fileUrl.isEmpty()) return;

        try {
            String bucketDomain = String.format("https://%s.s3.%s.amazonaws.com/", bucketName, region);
            if (fileUrl.startsWith(bucketDomain)) {
                String key = fileUrl.substring(bucketDomain.length());
                DeleteObjectRequest deleteObjectRequest = DeleteObjectRequest.builder()
                        .bucket(bucketName)
                        .key(key)
                        .build();
                s3Client.deleteObject(deleteObjectRequest);
                log.info("Deleted file from S3: {}", key);
            }
        } catch (Exception e) {
            log.error("Failed to delete file from S3: {}", fileUrl, e);
        }
    }

    public String generatePresignedUrl(String fileUrl) {
        if (fileUrl == null || fileUrl.isEmpty()) return null;

        try {
            String bucketDomain = String.format("https://%s.s3.%s.amazonaws.com/", bucketName, region);
            if (fileUrl.startsWith(bucketDomain)) {
                String key = fileUrl.substring(bucketDomain.length());

                GetObjectRequest getObjectRequest = GetObjectRequest.builder()
                        .bucket(bucketName)
                        .key(key)
                        .build();

                GetObjectPresignRequest getObjectPresignRequest = GetObjectPresignRequest.builder()
                        .signatureDuration(Duration.ofMinutes(60))
                        .getObjectRequest(getObjectRequest)
                        .build();

                return s3Presigner.presignGetObject(getObjectPresignRequest).url().toString();
            }
        } catch (Exception e) {
            log.error("Failed to generate presigned URL for S3: {}", fileUrl, e);
        }
        return fileUrl;
    }
}
