package com.backend.subscriptionservice.controller;

import com.backend.subscriptionservice.dto.request.InternalQuotaRequest;
import com.backend.subscriptionservice.dto.response.*;
import com.backend.subscriptionservice.service.UserSubscriptionService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

import java.time.Instant;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import java.util.List;

@RestController
@RequestMapping("/internal")
@RequiredArgsConstructor
@Slf4j
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

    @PostMapping("/subscriptions/dashboard-stats")
    public ApiResponse<Map<String, Object>> getSubscriptionDashboardStats(
            @RequestParam("startDate") String startDateStr,
            @RequestParam("endDate") String endDateStr,
            @RequestBody(required = false) List<UUID> userIds) {
        log.info("[subscription-service] Nhận yêu cầu nội bộ tính toán subscription stats tổng hợp...");
        Instant start = Instant.parse(startDateStr);
        Instant end = Instant.parse(endDateStr);

        Map<String, Object> stats = subscriptionService.getSubscriptionStatsInRange(start, end);
        
        Map<String, String> packageCodes = new HashMap<>();
        if (userIds != null && !userIds.isEmpty()) {
            packageCodes = subscriptionService.getActivePackageCodesByUserIds(userIds);
        }
        stats.put("package_codes", packageCodes);

        return ApiResponse.<Map<String, Object>>builder()
                .data(stats)
                .build();
    }
}
