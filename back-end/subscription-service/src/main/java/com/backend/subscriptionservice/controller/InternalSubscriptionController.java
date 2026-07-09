package com.backend.subscriptionservice.controller;

import com.backend.subscriptionservice.dto.request.InternalQuotaRequest;
import com.backend.subscriptionservice.dto.response.*;
import com.backend.subscriptionservice.service.UserSubscriptionService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.UUID;

@RestController
@RequestMapping("/internal")
@RequiredArgsConstructor
public class InternalSubscriptionController {

    private final UserSubscriptionService subscriptionService;

    @GetMapping("/quota/check")
    public ApiResponse<QuotaCheckResponse> checkQuota(@RequestParam UUID userId, @RequestParam String featureKey) {
        return ApiResponse.<QuotaCheckResponse>builder()
                .data(subscriptionService.checkQuota(userId, featureKey))
                .build();
    }

    @PostMapping("/quota/consume")
    public ApiResponse<QuotaConsumeResponse> consumeQuota(@RequestBody InternalQuotaRequest request) {
        return ApiResponse.<QuotaConsumeResponse>builder()
                .data(subscriptionService.consumeQuota(request.getUserId(), request.getFeatureKey(), request.getAmount()))
                .build();
    }

    @PostMapping("/quota/revert")
    public ApiResponse<QuotaConsumeResponse> revertQuota(@RequestBody InternalQuotaRequest request) {
        return ApiResponse.<QuotaConsumeResponse>builder()
                .data(subscriptionService.revertQuota(request.getUserId(), request.getFeatureKey(), request.getAmount()))
                .build();
    }

    @GetMapping("/users/{userId}/status")
    public ApiResponse<InternalUserStatusResponse> getUserStatus(@PathVariable UUID userId) {
        return ApiResponse.<InternalUserStatusResponse>builder()
                .data(subscriptionService.getUserStatus(userId))
                .build();
    }

    @PostMapping("/payment-callback")
    public ApiResponse<Void> handlePaymentCallback(@RequestParam Long orderCode) {
        subscriptionService.processPaymentCallback(orderCode);
        return ApiResponse.<Void>builder()
                .message("Payment callback processed successfully")
                .build();
    }
}
