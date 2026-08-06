package com.backend.statisticservice.client;

import com.backend.statisticservice.dto.response.ApiResponse;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;

import java.util.List;
import java.util.Map;
import java.util.UUID;

@FeignClient(
        name = "subscription-service",
        url = "${app.subscription-service.url:http://localhost:8084}",
        path = "/api/subscription"
)
public interface SubscriptionClient {
    @PostMapping("/internal/subscriptions/dashboard-stats")
    ApiResponse<Map<String, Object>> getSubscriptionDashboardStats(
            @RequestParam("startDate") String startDate,
            @RequestParam("endDate") String endDate,
            @RequestBody List<UUID> userIds);
}
