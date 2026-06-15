package com.backend.subscriptionservice.dto.request;

import lombok.*;
import java.util.UUID;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class InternalQuotaRequest {
    private UUID userId;
    private String featureKey;
    private Integer amount;
}
