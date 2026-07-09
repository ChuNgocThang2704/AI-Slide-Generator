package com.backend.subscriptionservice.dto.response;

import lombok.*;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class FeatureResponse {
    private String featureKey;
    private Integer featureValue;
}
