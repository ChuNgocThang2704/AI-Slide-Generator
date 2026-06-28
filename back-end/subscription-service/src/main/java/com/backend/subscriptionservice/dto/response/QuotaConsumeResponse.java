package com.backend.subscriptionservice.dto.response;

import lombok.*;
import java.util.UUID;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class QuotaConsumeResponse {
    private boolean success;
    private UUID userId;
    private String featureKey;
    private Integer newUsageValue;
}
