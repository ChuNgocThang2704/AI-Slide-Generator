package com.backend.userservice.controller;

import com.backend.userservice.dto.response.ApiResponse;
import com.backend.userservice.service.UserService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

import java.time.Instant;
import java.util.HashMap;
import java.util.Map;
import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/internal/users")
@Slf4j
@RequiredArgsConstructor
public class InternalUserController {

    private final UserService userService;

    @PostMapping("/dashboard-stats")
    public ApiResponse<Map<String, Object>> getUserDashboardStats(
            @RequestParam("startDate") String startDateStr,
            @RequestParam("endDate") String endDateStr,
            @RequestBody(required = false) List<UUID> userIds) {
        log.info("[user-service] Nhận yêu cầu nội bộ tính toán user dashboard stats tổng hợp...");
        Instant start = Instant.parse(startDateStr);
        Instant end = Instant.parse(endDateStr);

        Map<String, Long> rangeCount = new HashMap<>();
        rangeCount.put("previous_value", userService.countUsersBefore(start));
        rangeCount.put("current_value", userService.countUsersBetween(start, end));
        rangeCount.put("total_value", userService.countTotalUsers());

        Map<String, String> userEmails = new HashMap<>();
        if (userIds != null && !userIds.isEmpty()) {
            userEmails = userService.getUserEmailsMap(userIds);
        }

        Map<String, Object> result = new HashMap<>();
        result.put("range_count", rangeCount);
        result.put("unverified_emails_count", userService.countUnverifiedEmails());
        result.put("user_emails", userEmails);

        return ApiResponse.<Map<String, Object>>builder()
                .data(result)
                .build();
    }
}
