package com.backend.subscriptionservice.dto.response;

import lombok.*;
import java.util.UUID;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class QuotaCheckResponse {
    private UUID userId;
    private String featureKey;
    private boolean allowed;
    private Integer limitValue;
    private Integer currentUsage;
    private Integer remaining;
}
