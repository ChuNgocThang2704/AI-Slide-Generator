package com.backend.documentservice.dto.response;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.UUID;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class SourceDocumentResponse {
    private UUID id;
    private UUID userId;
    private String fileName;
    private String s3Url;
    private Integer fileType;
    private Long fileSize;
}
