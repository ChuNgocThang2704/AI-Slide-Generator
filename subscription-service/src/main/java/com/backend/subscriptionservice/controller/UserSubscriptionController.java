package com.backend.subscriptionservice.controller;

import com.backend.subscriptionservice.dto.request.UpgradeRequest;
import com.backend.subscriptionservice.dto.response.*;
import com.backend.subscriptionservice.service.UserSubscriptionService;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/users")
@RequiredArgsConstructor
public class UserSubscriptionController {

    private final UserSubscriptionService subscriptionService;

    private UUID getLoggedInUserId() {
        return UUID.fromString(SecurityContextHolder.getContext().getAuthentication().getName());
    }

    @GetMapping
    public ApiResponse<UserSubscriptionResponse> getMySubscription() {
        return ApiResponse.<UserSubscriptionResponse>builder()
                .data(subscriptionService.getOrCreateActiveSubscription(getLoggedInUserId()))
                .build();
    }

    @GetMapping("/quotas")
    public ApiResponse<List<QuotaResponse>> getMyQuotas() {
        return ApiResponse.<List<QuotaResponse>>builder()
                .data(subscriptionService.getQuotas(getLoggedInUserId()))
                .build();
    }

    @GetMapping("/history")
    public ApiResponse<List<HistoryResponse>> getMyHistory() {
        return ApiResponse.<List<HistoryResponse>>builder()
                .data(subscriptionService.getHistory(getLoggedInUserId()))
                .build();
    }

    @PostMapping("/upgrade")
    public ApiResponse<UpgradeResponse> upgrade(@RequestBody UpgradeRequest request) {
        return ApiResponse.<UpgradeResponse>builder()
                .message("Upgrade request registered successfully")
                .data(subscriptionService.upgrade(getLoggedInUserId(), request))
                .build();
    }



    @PostMapping("/cancel")
    public ApiResponse<Void> cancel() {
        subscriptionService.cancel(getLoggedInUserId());
        return ApiResponse.<Void>builder()
                .message("Subscription canceled successfully")
                .build();
    }

    @PostMapping("/reactivate")
    public ApiResponse<Void> reactivate() {
        subscriptionService.reactivate(getLoggedInUserId());
        return ApiResponse.<Void>builder()
                .message("Subscription reactivated successfully")
                .build();
    }
}
