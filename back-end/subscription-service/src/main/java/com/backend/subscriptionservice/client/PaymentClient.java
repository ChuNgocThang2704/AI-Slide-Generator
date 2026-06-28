package com.backend.subscriptionservice.client;

import com.backend.subscriptionservice.dto.request.PaymentCreateRequest;
import com.backend.subscriptionservice.dto.response.ApiResponse;
import com.backend.subscriptionservice.dto.response.PaymentCreateResponse;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;

@FeignClient(
        name = "payment-service",
        url = "${app.payment-service.url:http://localhost:8085/api/payment}"
)
public interface PaymentClient {

    @PostMapping("/create")
    ApiResponse<PaymentCreateResponse> createPaymentLink(@RequestBody PaymentCreateRequest request);
}
