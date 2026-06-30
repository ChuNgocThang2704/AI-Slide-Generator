package com.backend.subscriptionservice.dto.response;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class PaymentCreateResponse {
    private Long paymentCode;
    private String paymentUrl;
    private String paymentLinkId;
    private String clientSecret;
    private String status;
}
