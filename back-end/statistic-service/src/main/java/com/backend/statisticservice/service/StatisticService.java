package com.backend.statisticservice.service;

import com.backend.statisticservice.client.DocumentClient;
import com.backend.statisticservice.client.SubscriptionClient;
import com.backend.statisticservice.client.UserClient;
import com.backend.statisticservice.dto.response.ApiResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.time.LocalDate;
import java.time.ZoneId;
import java.util.*;

@Service
@RequiredArgsConstructor
@Slf4j
public class StatisticService {

    private final UserClient userClient;
    private final SubscriptionClient subscriptionClient;
    private final DocumentClient documentClient;

    /**
     * Màn hình 1: Dashboard Doanh Thu & Giao Dịch
     */
    public Map<String, Object> getRevenueDashboard(String startDate, String endDate) {
        log.info("[statistic-service] Đang lấy thống kê Doanh Thu & Giao Dịch từ database...");

        String startStr = toInstantString(startDate, LocalDate.now().minusDays(30));
        String endStr = toInstantString(endDate, LocalDate.now());

        // Lấy dữ liệu cước & doanh thu từ subscription-service
        Map<String, Object> stats = new HashMap<>();
        try {
            ApiResponse<Map<String, Object>> res = subscriptionClient.getSubscriptionDashboardStats(startStr, endStr, Collections.emptyList());
            if (res != null && res.getData() != null) stats = res.getData();
        } catch (Exception e) {
            log.error("[statistic-service] Lỗi gọi subscription-service: {}", e.getMessage());
        }

        Map<String, Object> activeSubData = getMapValue(stats, "active_subscriptions");
        Map<String, Object> revVndData = getMapValue(stats, "revenue_vnd");
        Map<String, Object> revUsdData = getMapValue(stats, "revenue_usd");

        double currentRevVnd = getDoubleValue(revVndData, "current_value");
        double prevRevVnd = getDoubleValue(revVndData, "previous_value");

        double currentRevUsd = getDoubleValue(revUsdData, "current_value");
        double prevRevUsd = getDoubleValue(revUsdData, "previous_value");

        long currentActiveSubs = getLongValue(activeSubData, "current_value");
        long prevActiveSubs = getLongValue(activeSubData, "previous_value");

        Map<String, Object> data = new LinkedHashMap<>();

        // 1. summary
        Map<String, Object> summary = new LinkedHashMap<>();
        summary.put("total_revenue_vnd", buildGrowthMap(prevRevVnd, currentRevVnd));
        summary.put("total_revenue_usd", buildGrowthMap(prevRevUsd, currentRevUsd));
        summary.put("active_subscriptions", buildGrowthMap(prevActiveSubs, currentActiveSubs));
        data.put("summary", summary);

        // 2. package_distribution (Từ DB thật)
        data.put("package_distribution", getListMapValue(stats, "package_distribution"));

        // 3. transaction_status_distribution (Từ DB thật)
        data.put("transaction_status_distribution", getListMapValue(stats, "transaction_status_distribution"));

        return data;
    }

    /**
     * Màn hình 2: Dashboard Hoạt Động Người Dùng & AI Usage
     */
    public Map<String, Object> getUsersDashboard(String startDate, String endDate) {
        log.info("[statistic-service] Đang lấy thống kê Hoạt Động Người Dùng từ database...");

        String startStr = toInstantString(startDate, LocalDate.now().minusDays(30));
        String endStr = toInstantString(endDate, LocalDate.now());
        int currentYear = LocalDate.now().getYear();

        // 1. Gọi gộp sang document-service lấy số liệu slide, top users và biểu đồ tháng
        Map<String, Object> projectStats = new HashMap<>();
        try {
            ApiResponse<Map<String, Object>> res = documentClient.getProjectDashboardStats(startStr, endStr, currentYear, 15);
            if (res != null && res.getData() != null) projectStats = res.getData();
        } catch (Exception e) {
            log.error("[statistic-service] Lỗi gọi document-service: {}", e.getMessage());
        }

        Map<String, Long> projectRangeMap = getMapStringLong(projectStats, "range_count");
        long distinctOwners = getLongValue(projectStats, "distinct_owners_count");
        List<Object[]> rawMonthlyCounts = getListObjects(projectStats, "monthly_counts");
        Map<String, Map<String, Long>> topUsersStats = getMapStringMapLong(projectStats, "top_users_stats");

        List<UUID> topUserIds = new ArrayList<>();
        for (String idStr : topUsersStats.keySet()) {
            try {
                topUserIds.add(UUID.fromString(idStr));
            } catch (Exception e) {
                // ignore
            }
        }

        // 2. Gọi gộp sang user-service lấy số lượng user đăng ký, số email chưa verify và phân giải email cho top users
        Map<String, Object> userStats = new HashMap<>();
        try {
            ApiResponse<Map<String, Object>> res = userClient.getUserDashboardStats(startStr, endStr, topUserIds);
            if (res != null && res.getData() != null) userStats = res.getData();
        } catch (Exception e) {
            log.error("[statistic-service] Lỗi gọi user-service: {}", e.getMessage());
        }

        Map<String, Long> userRangeMap = getMapStringLong(userStats, "range_count");
        long unverifiedCount = getLongValue(userStats, "unverified_emails_count");
        Map<String, String> emailMap = getMapStringString(userStats, "user_emails");

        // 3. Gọi gộp sang subscription-service lấy số gói sắp hết hạn và phân giải gói cước hoạt động cho top users
        Map<String, Object> subscriptionStats = new HashMap<>();
        try {
            ApiResponse<Map<String, Object>> res = subscriptionClient.getSubscriptionDashboardStats(startStr, endStr, topUserIds);
            if (res != null && res.getData() != null) subscriptionStats = res.getData();
        } catch (Exception e) {
            log.error("[statistic-service] Lỗi gọi subscription-service: {}", e.getMessage());
        }

        long expiringSubs = getLongValue(subscriptionStats, "expiring_subscriptions_count");
        Map<String, String> packageMap = getMapStringString(subscriptionStats, "package_codes");

        double currentUsers = userRangeMap.getOrDefault("current_value", 0L);
        double prevUsers = userRangeMap.getOrDefault("previous_value", 0L);
        long totalUsersCount = userRangeMap.getOrDefault("total_value", 0L);

        double currentSlides = projectRangeMap.getOrDefault("current_value", 0L);
        double prevSlides = projectRangeMap.getOrDefault("previous_value", 0L);

        Map<String, Object> data = new LinkedHashMap<>();

        // 1. summary
        Map<String, Object> summary = new LinkedHashMap<>();
        summary.put("total_users", buildGrowthMap(prevUsers, currentUsers));
        summary.put("slides_generated", buildGrowthMap(prevSlides, currentSlides));

        double avgSlidesCurrent = currentUsers > 0 ? currentSlides / currentUsers : 0.0;
        double avgSlidesPrev = prevUsers > 0 ? prevSlides / prevUsers : 0.0;
        summary.put("average_slides_per_user", buildGrowthMap(avgSlidesPrev, avgSlidesCurrent));
        data.put("summary", summary);

        // 2. Lắp ráp danh sách xếp hạng người dùng từ dữ liệu thật
        List<Map<String, Object>> allTopUsers = buildTopUsersList(topUsersStats, emailMap, packageMap);

        // Phân loại xếp hạng
        data.put("top_active_users", filterAndSortTopUsers(allTopUsers, "active", 5));
        data.put("top_increasers", filterAndSortTopUsers(allTopUsers, "increaser", 3));
        data.put("top_decreasers", filterAndSortTopUsers(allTopUsers, "decreaser", 3));

        // 3. user_warnings
        long inactiveUsers = Math.max(0, totalUsersCount - distinctOwners);

        Map<String, Object> warnings = new HashMap<>();
        warnings.put("inactive_users_30d", inactiveUsers); 
        warnings.put("package_expiring_3d", expiringSubs);  
        warnings.put("unverified_emails", unverifiedCount);    
        data.put("user_warnings", warnings);

        // 4. yearly_slides_chart (Biểu đồ cột theo tháng từ DB)
        List<Map<String, Object>> yearlySlidesChart = new ArrayList<>();
        int currentMonth = LocalDate.now().getMonthValue();
        Map<Integer, Long> monthlyCountsMap = parseMonthlyCounts(rawMonthlyCounts);

        for (int m = 1; m <= currentMonth; m++) {
            long total = monthlyCountsMap.getOrDefault(m, 0L);
            Map<String, Object> item = new HashMap<>();
            item.put("month", (double) m);
            item.put("total_slides", total);
            yearlySlidesChart.add(item);
        }
        data.put("yearly_slides_chart", yearlySlidesChart);

        // 5. daily_slides_chart (Biểu đồ các ngày trong khoảng lọc từ DB thật)
        List<Object[]> rawDailyCounts = getListObjects(projectStats, "daily_counts");
        LocalDate startLocalDate = parseLocalDate(startDate, LocalDate.now().minusDays(30));
        LocalDate endLocalDate = parseLocalDate(endDate, LocalDate.now());
        data.put("daily_slides_chart", buildDailySlidesChart(rawDailyCounts, startLocalDate, endLocalDate));

        return data;
    }

    // --- TYPE-SAFE CONVERSION HELPER METHODS ---

    private List<Map<String, Object>> getListMapValue(Map<String, Object> map, String key) {
        List<Map<String, Object>> result = new ArrayList<>();
        if (map == null) return result;
        Object val = map.get(key);
        if (val instanceof List) {
            for (Object item : (List<?>) val) {
                if (item instanceof Map) {
                    Map<?, ?> m = (Map<?, ?>) item;
                    Map<String, Object> typedMap = new HashMap<>();
                    for (Map.Entry<?, ?> entry : m.entrySet()) {
                        if (entry.getKey() != null) {
                            typedMap.put(entry.getKey().toString(), entry.getValue());
                        }
                    }
                    result.add(typedMap);
                }
            }
        }
        return result;
    }

    private Map<String, Long> getMapStringLong(Map<String, Object> map, String key) {
        Map<String, Long> result = new HashMap<>();
        if (map == null) return result;
        Object val = map.get(key);
        if (val instanceof Map) {
            for (Map.Entry<?, ?> entry : ((Map<?, ?>) val).entrySet()) {
                if (entry.getKey() != null && entry.getValue() instanceof Number) {
                    result.put(entry.getKey().toString(), ((Number) entry.getValue()).longValue());
                }
            }
        }
        return result;
    }

    private Map<String, String> getMapStringString(Map<String, Object> map, String key) {
        Map<String, String> result = new HashMap<>();
        if (map == null) return result;
        Object val = map.get(key);
        if (val instanceof Map) {
            for (Map.Entry<?, ?> entry : ((Map<?, ?>) val).entrySet()) {
                if (entry.getKey() != null && entry.getValue() != null) {
                    result.put(entry.getKey().toString(), entry.getValue().toString());
                }
            }
        }
        return result;
    }

    private Map<String, Map<String, Long>> getMapStringMapLong(Map<String, Object> map, String key) {
        Map<String, Map<String, Long>> result = new HashMap<>();
        if (map == null) return result;
        Object val = map.get(key);
        if (val instanceof Map) {
            for (Map.Entry<?, ?> entry : ((Map<?, ?>) val).entrySet()) {
                if (entry.getKey() != null && entry.getValue() instanceof Map) {
                    Map<String, Long> innerMap = new HashMap<>();
                    for (Map.Entry<?, ?> innerEntry : ((Map<?, ?>) entry.getValue()).entrySet()) {
                        if (innerEntry.getKey() != null && innerEntry.getValue() instanceof Number) {
                            innerMap.put(innerEntry.getKey().toString(), ((Number) innerEntry.getValue()).longValue());
                        }
                    }
                    result.put(entry.getKey().toString(), innerMap);
                }
            }
        }
        return result;
    }

    private List<Object[]> getListObjects(Map<String, Object> map, String key) {
        List<Object[]> result = new ArrayList<>();
        if (map == null) return result;
        Object val = map.get(key);
        if (val instanceof List) {
            for (Object item : (List<?>) val) {
                if (item instanceof List) {
                    result.add(((List<?>) item).toArray());
                }
            }
        }
        return result;
    }

    private Map<String, Object> getMapValue(Map<String, Object> map, String key) {
        if (map == null) return Collections.emptyMap();
        Object val = map.get(key);
        if (val instanceof Map) {
            Map<String, Object> typedMap = new HashMap<>();
            for (Map.Entry<?, ?> entry : ((Map<?, ?>) val).entrySet()) {
                if (entry.getKey() != null) {
                    typedMap.put(entry.getKey().toString(), entry.getValue());
                }
            }
            return typedMap;
        }
        return Collections.emptyMap();
    }

    private double getDoubleValue(Map<String, Object> map, String key) {
        if (map == null) return 0.0;
        Object val = map.get(key);
        return val instanceof Number ? ((Number) val).doubleValue() : 0.0;
    }

    private long getLongValue(Map<String, Object> map, String key) {
        if (map == null) return 0L;
        Object val = map.get(key);
        return val instanceof Number ? ((Number) val).longValue() : 0L;
    }

    // --- CLEAN DATA PROCESSING METHODS ---

    private List<Map<String, Object>> buildDailySlidesChart(
            List<Object[]> rawDailyCounts, 
            LocalDate startLocalDate, 
            LocalDate endLocalDate) {
        
        Map<String, Long> dailyCountsMap = new HashMap<>();
        if (rawDailyCounts != null) {
            for (Object[] row : rawDailyCounts) {
                if (row.length >= 2) {
                    try {
                        String dateStr = row[0].toString();
                        long count = ((Number) row[1]).longValue();
                        dailyCountsMap.put(dateStr, count);
                    } catch (Exception e) {
                        // ignore
                    }
                }
            }
        }

        List<Map<String, Object>> chart = new ArrayList<>();
        LocalDate current = startLocalDate;
        
        while (!current.isAfter(endLocalDate)) {
            String dateStr = current.toString();
            long total = dailyCountsMap.getOrDefault(dateStr, 0L);

            Map<String, Object> item = new LinkedHashMap<>();
            item.put("date", dateStr);
            item.put("total_slides", total);
            chart.add(item);

            current = current.plusDays(1);
        }
        return chart;
    }

    private List<Map<String, Object>> buildTopUsersList(
            Map<String, Map<String, Long>> topUsersStats, 
            Map<String, String> emailMap, 
            Map<String, String> packageMap) {
        
        List<Map<String, Object>> list = new ArrayList<>();
        if (topUsersStats == null) return list;
        
        for (Map.Entry<String, Map<String, Long>> entry : topUsersStats.entrySet()) {
            String userId = entry.getKey();
            Map<String, Long> range = entry.getValue();
            if (range == null) continue;

            long current = range.getOrDefault("current_value", 0L);
            long previous = range.getOrDefault("previous_value", 0L);
            double growth = previous > 0 ? ((double) (current - previous) / previous) * 100.0 : 0.0;

            Map<String, Object> userMap = new HashMap<>();
            userMap.put("email", emailMap.getOrDefault(userId, "unknown@user.com"));
            userMap.put("package_tier", packageMap.getOrDefault(userId, "FREE"));
            userMap.put("slides_count", current);
            userMap.put("growth", Math.round(growth * 10.0) / 10.0);
            list.add(userMap);
        }
        return list;
    }

    private List<Map<String, Object>> filterAndSortTopUsers(List<Map<String, Object>> users, String type, int limit) {
        List<Map<String, Object>> filtered = new ArrayList<>();
        for (Map<String, Object> u : users) {
            double growth = ((Number) u.get("growth")).doubleValue();
            if ("increaser".equals(type) && growth <= 0) continue;
            if ("decreaser".equals(type) && growth >= 0) continue;
            filtered.add(u);
        }

        filtered.sort((a, b) -> {
            if ("decreaser".equals(type)) {
                return Double.compare(
                        ((Number) a.get("growth")).doubleValue(),
                        ((Number) b.get("growth")).doubleValue()
                );
            } else if ("increaser".equals(type)) {
                return Double.compare(
                        ((Number) b.get("growth")).doubleValue(),
                        ((Number) a.get("growth")).doubleValue()
                );
            } else {
                return Long.compare(
                        ((Number) b.get("slides_count")).longValue(),
                        ((Number) a.get("slides_count")).longValue()
                );
            }
        });

        return filtered.size() > limit ? filtered.subList(0, limit) : filtered;
    }

    private Map<Integer, Long> parseMonthlyCounts(List<Object[]> rawCounts) {
        Map<Integer, Long> map = new HashMap<>();
        if (rawCounts == null) return map;
        for (Object[] row : rawCounts) {
            if (row.length >= 2) {
                try {
                    int month = ((Number) row[0]).intValue();
                    long count = ((Number) row[1]).longValue();
                    map.put(month, count);
                } catch (Exception e) {
                    // ignore
                }
            }
        }
        return map;
    }

    private LocalDate parseLocalDate(String dateStr, LocalDate defaultVal) {
        if (dateStr == null || dateStr.isBlank()) return defaultVal;
        try {
            return LocalDate.parse(dateStr);
        } catch (Exception e) {
            try {
                String[] parts = dateStr.split("/");
                return LocalDate.of(Integer.parseInt(parts[2]), Integer.parseInt(parts[1]), Integer.parseInt(parts[0]));
            } catch (Exception ex) {
                try {
                    String[] parts = dateStr.split("-");
                    return LocalDate.of(Integer.parseInt(parts[0]), Integer.parseInt(parts[1]), Integer.parseInt(parts[2]));
                } catch (Exception exc) {
                    log.warn("[statistic-service] Không thể parse LocalDate {}, dùng mặc định {}", dateStr, defaultVal);
                }
            }
        }
        return defaultVal;
    }

    private Map<String, Object> buildGrowthMap(double prev, double curr) {
        Map<String, Object> item = new HashMap<>();
        double growth = prev > 0 ? ((curr - prev) / prev) * 100.0 : 0.0;
        item.put("previous_value", Math.round(prev));
        item.put("growth", Math.round(growth * 10.0) / 10.0);
        item.put("current_value", Math.round(curr));
        return item;
    }

    private Map<String, Long> createDefaultRangeMap() {
        Map<String, Long> map = new HashMap<>();
        map.put("previous_value", 0L);
        map.put("current_value", 0L);
        map.put("total_value", 0L);
        return map;
    }

    private String toInstantString(String dateStr, LocalDate defaultVal) {
        LocalDate localDate = defaultVal;
        if (dateStr != null && !dateStr.isBlank()) {
            try {
                localDate = LocalDate.parse(dateStr);
            } catch (Exception e) {
                try {
                    String[] parts = dateStr.split("/");
                    localDate = LocalDate.of(Integer.parseInt(parts[2]), java.time.Month.valueOf(parts[1].toUpperCase()).getValue(), Integer.parseInt(parts[0]));
                } catch (Exception ex) {
                    try {
                        String[] parts = dateStr.split("/");
                        localDate = LocalDate.of(Integer.parseInt(parts[2]), Integer.parseInt(parts[1]), Integer.parseInt(parts[0]));
                    } catch (Exception exc) {
                        log.warn("[statistic-service] Không thể parse ngày {}, dùng giá trị mặc định {}", dateStr, defaultVal);
                    }
                }
            }
        }
        return localDate.atStartOfDay(ZoneId.of("UTC")).toInstant().toString();
    }
}
