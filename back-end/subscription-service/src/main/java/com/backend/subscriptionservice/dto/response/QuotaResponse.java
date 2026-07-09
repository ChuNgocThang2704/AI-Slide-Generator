package com.backend.subscriptionservice.dto.response;

import lombok.*;
import java.time.LocalDateTime;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class QuotaResponse {
    private String featureKey;
    private String displayName;
    private Integer limitValue;
    private Integer currentUsage;
    private Integer remaining;
    private LocalDateTime lastResetTime;
}
