package com.backend.subscriptionservice.dto.request;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class PaymentCreateRequest {
    private Long paymentCode;
    private Long amount;
    private String description;
    private String returnUrl;
    private String cancelUrl;
    private String paymentProvider;
}
