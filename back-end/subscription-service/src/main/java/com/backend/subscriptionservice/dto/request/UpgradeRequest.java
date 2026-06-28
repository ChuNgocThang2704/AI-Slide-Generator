package com.backend.subscriptionservice.dto.request;

import lombok.*;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class UpgradeRequest {
    private String packageCode;
    private Integer billingCycle;
}
