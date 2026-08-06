package com.backend.statisticservice.dto.response;

import lombok.*;
import java.util.List;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class DashboardSummaryResponse {
    // 1. KPI Cards (Chỉ số tổng quan & xu hướng)
    private KpiMetric totalUsers;
    private KpiMetric activeSubscriptions;
    private KpiMetric totalRevenueVnd;
    private KpiMetric totalRevenueUsd;
    private KpiMetric totalSlidesGenerated;

    // 2. Xu hướng 6 tháng qua (Trends)
    private List<MonthlyTrend> monthlyTrends;

    // 3. Cảnh báo hành động (System Alerts)
    private List<SystemAlert> systemAlerts;

    // 4. Phân bổ Gói cước (Donut/Pie Chart)
    private List<PieChartData> packageDistribution;

    // 5. Phân bổ Cổng thanh toán (Donut/Pie Chart)
    private List<PieChartData> paymentGatewayDistribution;

    // 6. Phân bổ Trạng thái Giao dịch (Pie Chart)
    private List<PieChartData> transactionStatusDistribution;

    // 7. Bảng xếp hạng người dùng tích cực (Top Active Users)
    private List<TopUserMetric> topActiveUsers;

    // 8. Tải lượng của các Microservices (Service Load)
    private List<ServiceLoadMetric> microserviceLoads;

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class KpiMetric {
        private double value;
        private double percentageChange; // Ví dụ: +3.1 (tăng 3.1%)
        private String description;      // Ví dụ: "so với tháng trước"
        private List<Double> sparkline;  // Mảng dữ liệu vẽ biểu đồ nhỏ (7 điểm)
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class MonthlyTrend {
        private String month; // Ví dụ: "T2/2026"
        private double revenueVnd;
        private double revenueUsd;
        private long newUsers;
        private long slidesCount;
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class SystemAlert {
        private String level; // DANGER, WARNING, SUCCESS
        private String message;
        private String actionRequired;
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class PieChartData {
        private String name; // Ví dụ: "Gói PRO", "Stripe"
        private double value;
        private double percentage;
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class TopUserMetric {
        private int rank;
        private String email;
        private String packageTier;
        private long slidesCount;
        private double percentageChange;
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class ServiceLoadMetric {
        private String serviceName;
        private long requestCount;
        private double successRate; // Ví dụ: 99.9%
    }
}
