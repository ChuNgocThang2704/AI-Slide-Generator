package com.backend.paymentservice.strategy;

import com.backend.paymentservice.dto.request.PaymentRequest;
import com.backend.paymentservice.dto.response.PaymentResponse;

import java.util.Map;

public interface PaymentStrategy {
    PaymentResponse createPaymentLink(PaymentRequest request);
    Map<String, Object> verifyWebhook(String payload, String sigHeader);
    Map<String, Object> getPaymentLinkInformation(Long paymentCode);
    Map<String, Object> cancelPaymentLink(Long paymentCode, String reason);
    String getProviderName();
}
