package com.backend.documentservice.dto.response;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.Instant;
import java.util.UUID;
import java.io.Serializable;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ProjectResponse implements Serializable {
    private UUID id;
    private String name;
    private UUID ownerId;
    private UUID sourceDocId;
    private UUID templateId;
    private String initialPrompt;
    private String slideUrl;
    private Integer status;
    private Instant createdAt;
    private Instant updatedAt;
}
