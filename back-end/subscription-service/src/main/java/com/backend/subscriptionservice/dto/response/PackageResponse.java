package com.backend.subscriptionservice.dto.response;

import lombok.*;
import java.math.BigDecimal;
import java.util.List;
import java.util.UUID;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class PackageResponse {
    private UUID id;
    private String code;
    private String name;
    private String description;
    private BigDecimal priceVnd;
    private BigDecimal priceUsd;
    private Integer billingCycle;
    private List<FeatureResponse> features;
}
