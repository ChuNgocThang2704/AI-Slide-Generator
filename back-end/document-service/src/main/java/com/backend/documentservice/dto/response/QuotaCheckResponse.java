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
public class QuotaCheckResponse {
    private UUID userId;
    private String featureKey;
    private boolean allowed;
    private int limitValue;
    private int currentUsage;
    private int remaining;
}
