package com.backend.paymentservice.service;

import com.backend.paymentservice.dto.request.PaymentRequest;
import com.backend.paymentservice.dto.response.PaymentResponse;
import com.backend.paymentservice.strategy.PaymentStrategy;
import com.backend.paymentservice.strategy.PaymentStrategyFactory;
import com.backend.paymentservice.util.Constants;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.Map;

@Service
@RequiredArgsConstructor
@Slf4j
public class PaymentService {

    private final PaymentStrategyFactory strategyFactory;

    public PaymentResponse createPaymentLink(PaymentRequest request) {
        PaymentStrategy strategy = strategyFactory.getStrategy(request.getPaymentProvider());
        return strategy.createPaymentLink(request);
    }

    public Map<String, Object> getPaymentLinkInformation(Long paymentCode) {
        try {
            return strategyFactory.getStrategy(Constants.PAYMENT_PROVIDER.STRIPE).getPaymentLinkInformation(paymentCode);
        } catch (Exception e) {
            return strategyFactory.getStrategy(Constants.PAYMENT_PROVIDER.PAYOS).getPaymentLinkInformation(paymentCode);
        }
    }

    public Map<String, Object> cancelPaymentLink(Long paymentCode, String reason) {
        try {
            return strategyFactory.getStrategy(Constants.PAYMENT_PROVIDER.STRIPE).cancelPaymentLink(paymentCode, reason);
        } catch (Exception e) {
            return strategyFactory.getStrategy(Constants.PAYMENT_PROVIDER.PAYOS).cancelPaymentLink(paymentCode, reason);
        }
    }

    public Map<String, Object> verifyStripeWebhook(String payload, String sigHeader) {
        return strategyFactory.getStrategy(Constants.PAYMENT_PROVIDER.STRIPE).verifyWebhook(payload, sigHeader);
    }

    public Map<String, Object> verifyPayOSWebhook(String payload, String sigHeader) {
        return strategyFactory.getStrategy(Constants.PAYMENT_PROVIDER.PAYOS).verifyWebhook(payload, sigHeader);
    }
}
