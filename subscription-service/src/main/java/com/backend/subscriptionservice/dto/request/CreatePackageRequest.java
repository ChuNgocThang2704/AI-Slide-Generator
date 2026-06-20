package com.backend.subscriptionservice.dto.request;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class CreatePackageRequest {
    private String code;
    private String name;
    private String description;
    private BigDecimal price;
    private Integer billingCycle;
}
