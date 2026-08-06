package com.backend.statisticservice.client;

import com.backend.statisticservice.dto.response.ApiResponse;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;

import java.util.Map;

@FeignClient(
        name = "document-service",
        url = "${app.document-service.url:http://localhost:8082}",
        path = "/api/document"
)
public interface DocumentClient {
    @GetMapping("/internal/projects/dashboard-stats")
    ApiResponse<Map<String, Object>> getProjectDashboardStats(
            @RequestParam("startDate") String startDate,
            @RequestParam("endDate") String endDate,
            @RequestParam("year") int year,
            @RequestParam("topUsersLimit") int topUsersLimit);
}
