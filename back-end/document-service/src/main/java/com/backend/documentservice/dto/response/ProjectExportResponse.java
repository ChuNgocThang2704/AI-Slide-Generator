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
public class ProjectExportResponse {
    private UUID id;
    private UUID projectId;
    private Integer exportType;
    private String s3Url;
    private Instant createdAt;
}
