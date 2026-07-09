package com.backend.paymentservice.client;

import com.backend.paymentservice.dto.response.ApiResponse;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;

@FeignClient(
        name = "subscription-service",
        url = "${app.subscription-service.url:http://localhost:8084/api/subscription}"
)
public interface SubscriptionClient {

    @PostMapping("/internal/payment-callback")
    ApiResponse<Void> notifyPaymentSuccess(@RequestParam("orderCode") Long orderCode);
}
