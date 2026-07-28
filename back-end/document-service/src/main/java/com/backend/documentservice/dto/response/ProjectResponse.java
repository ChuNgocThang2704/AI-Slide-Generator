package com.backend.documentservice.dto.response;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.Instant;
import java.util.List;
import java.util.UUID;
import java.io.Serializable;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ProjectResponse implements Serializable {
    private static final long serialVersionUID = 1L;

    private UUID id;
    private String name;
    private UUID ownerId;
    private UUID sourceDocId;
    private String templateId;
    private String initialPrompt;
    private String slideUrl;
    private Integer status;
    private String aiTaskId;
    private String presentationMode;
    private List<String> learningObjectives;
    private Instant createdAt;
    private Instant updatedAt;
}
