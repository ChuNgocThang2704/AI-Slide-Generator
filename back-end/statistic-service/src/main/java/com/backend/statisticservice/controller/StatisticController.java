package com.backend.statisticservice.controller;

import com.backend.statisticservice.dto.response.ApiResponse;
import com.backend.statisticservice.service.StatisticService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/dashboard")
@RequiredArgsConstructor
@Slf4j
public class StatisticController {

    private final StatisticService statisticService;

    /**
     * API Màn hình 1: Dashboard Doanh Thu & Giao Dịch
     */
    @GetMapping("/revenue")
    public ApiResponse<Map<String, Object>> getRevenueDashboard(
            @RequestParam(value = "startDate", required = false) String startDate,
            @RequestParam(value = "endDate", required = false) String endDate) {
        log.info("[statistic-service] Yêu cầu lấy Dashboard Doanh Thu từ {} đến {}", startDate, endDate);
        return ApiResponse.<Map<String, Object>>builder()
                .data(statisticService.getRevenueDashboard(startDate, endDate))
                .build();
    }

    /**
     * API Màn hình 2: Dashboard Hoạt Động Người Dùng & AI Usage
     */
    @GetMapping("/users")
    public ApiResponse<Map<String, Object>> getUsersDashboard(
            @RequestParam(value = "startDate", required = false) String startDate,
            @RequestParam(value = "endDate", required = false) String endDate) {
        log.info("[statistic-service] Yêu cầu lấy Dashboard Hoạt Động Người Dùng từ {} đến {}", startDate, endDate);
        return ApiResponse.<Map<String, Object>>builder()
                .data(statisticService.getUsersDashboard(startDate, endDate))
                .build();
    }
}
