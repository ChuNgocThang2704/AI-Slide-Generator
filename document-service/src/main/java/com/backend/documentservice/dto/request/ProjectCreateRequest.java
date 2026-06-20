package com.backend.documentservice.dto.request;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.UUID;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ProjectCreateRequest {

    private String prompt;

    private UUID templateId;

    private UUID sourceDocId;

    private String fileUrl;
    private String fileName;
    private Long fileSize;

    private UUID ownerId;
}
