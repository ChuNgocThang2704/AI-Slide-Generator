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
public class ProjectResponse {
    private UUID id;
    private String name;
    private UUID ownerId;
    private UUID sourceDocId;
    private UUID templateId;
    private UUID aiConfigId;
    private String initialPrompt;
    private Integer status;
    private Instant createdAt;
    private Instant updatedAt;
}
