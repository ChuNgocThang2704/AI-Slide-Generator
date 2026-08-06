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
        name = "user-service",
        url = "${app.user-service.url:http://localhost:8081}"
)
public interface UserClient {
    @PostMapping("/internal/users/dashboard-stats")
    ApiResponse<Map<String, Object>> getUserDashboardStats(
            @RequestParam("startDate") String startDate,
            @RequestParam("endDate") String endDate,
            @RequestBody List<UUID> userIds);
}
