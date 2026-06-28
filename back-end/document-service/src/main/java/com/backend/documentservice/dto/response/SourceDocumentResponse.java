package com.backend.documentservice.dto.response;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.Instant;
import java.util.UUID;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class SourceDocumentResponse {
    private UUID id;
    private String fileName;
    private String url;
    private Integer fileType;
    private Long fileSize;
    private Instant createdAt;
    private Instant updatedAt;
}
