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
public class AITaskLogResponse {
    private UUID id;
    private UUID projectId;
    private Integer taskType;
    private Integer status;
    private String errorMessage;
    private Instant startedAt;
    private Instant completedAt;
    private Instant createdAt;
}
