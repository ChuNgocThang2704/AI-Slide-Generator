package com.backend.subscriptionservice.service;

import com.backend.subscriptionservice.client.PaymentClient;
import com.backend.subscriptionservice.dto.request.PaymentCreateRequest;
import com.backend.subscriptionservice.dto.request.UpgradeRequest;
import com.backend.subscriptionservice.dto.response.*;
import com.backend.subscriptionservice.entity.PackageFeature;
import com.backend.subscriptionservice.entity.SubscriptionHistory;
import com.backend.subscriptionservice.entity.SubscriptionPackage;
import com.backend.subscriptionservice.entity.UserFeatureUsage;
import com.backend.subscriptionservice.entity.UserSubscription;
import com.backend.subscriptionservice.exception.AppException;
import com.backend.subscriptionservice.exception.ErrorCode;
import com.backend.subscriptionservice.repository.*;
import com.backend.subscriptionservice.util.Constants;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.*;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
@Slf4j
public class UserSubscriptionService {

    private final UserSubscriptionRepository subscriptionRepository;
    private final SubscriptionPackageRepository packageRepository;
    private final PackageFeatureRepository featureRepository;
    private final SubscriptionHistoryRepository historyRepository;
    private final UserFeatureUsageRepository usageRepository;
    private final PaymentClient paymentClient;
    private final Random random = new Random();

    @Value("${payos.return-url:http://localhost:5173/success}")
    private String returnUrl;

    @Value("${payos.cancel-url:http://localhost:5173/cancel}")
    private String cancelUrl;

    @Transactional
    public UserSubscriptionResponse getOrCreateActiveSubscription(UUID userId) {
        return subscriptionRepository.findActiveOrCanceledNotExpired(userId, LocalDateTime.now())
                .map(this::mapToSubscriptionResponse)
                .orElseGet(() -> {
                    SubscriptionPackage freePack = packageRepository.findByCodeAndBillingCycle(Constants.PACKAGE_CODE.FREE, Constants.BILLING_CYCLE.MONTHLY)
                            .orElseThrow(() -> new AppException(ErrorCode.PACKAGE_NOT_FOUND));

                    UserSubscription freeSub = UserSubscription.builder()
                            .userId(userId)
                            .packageId(freePack.getId())
                            .startDate(LocalDateTime.now())
                            .expireDate(null)
                            .status(Constants.SUBSCRIPTION_STATUS.ACTIVE)
                            .build();

                    UserSubscription savedSub = subscriptionRepository.save(freeSub);

                    SubscriptionHistory history = SubscriptionHistory.builder()
                            .userId(userId)
                            .action(Constants.SUBSCRIPTION_ACTION.REGISTER)
                            .newPackageCode(Constants.PACKAGE_CODE.FREE)
                            .build();
                    historyRepository.save(history);

                    return mapToSubscriptionResponse(savedSub);
                });
    }

    public List<HistoryResponse> getHistory(UUID userId) {
        return historyRepository.findByUserIdOrderByCreatedAtDesc(userId).stream()
                .map(h -> HistoryResponse.builder()
                        .id(h.getId())
                        .userId(h.getUserId())
                        .action(h.getAction())
                        .previousPackageCode(h.getPreviousPackageCode())
                        .newPackageCode(h.getNewPackageCode())
                        .createdAt(h.getCreatedAt())
                        .note(h.getNote())
                        .build())
                .collect(Collectors.toList());
    }

    @Transactional
    public UpgradeResponse upgrade(UUID userId, UpgradeRequest request) {
        SubscriptionPackage targetPack = null;
        if (request.getBillingCycle() != null) {
            targetPack = packageRepository.findByCodeAndBillingCycle(request.getPackageCode(), request.getBillingCycle()).orElse(null);
        }
        if (targetPack == null) {
            targetPack = packageRepository.findByCode(request.getPackageCode())
                    .orElseThrow(() -> new AppException(ErrorCode.PACKAGE_NOT_FOUND));
        }

        // Nếu là gói FREE, chuyển thẳng thành ACTIVE
        if (Constants.PACKAGE_CODE.FREE.equalsIgnoreCase(targetPack.getCode())) {
            deactivateAllActiveSubscriptions(userId);

            UserSubscription newSub = UserSubscription.builder()
                    .userId(userId)
                    .packageId(targetPack.getId())
                    .startDate(LocalDateTime.now())
                    .expireDate(null)
                    .status(Constants.SUBSCRIPTION_STATUS.ACTIVE)
                    .build();

            UserSubscription saved = subscriptionRepository.save(newSub);
            saveHistoryLog(userId, Constants.SUBSCRIPTION_ACTION.DOWNGRADE, Constants.PACKAGE_CODE.FREE, "Upgrade to FREE");

            return UpgradeResponse.builder()
                    .subscriptionId(saved.getId())
                    .status(Constants.SUBSCRIPTION_STATUS.ACTIVE)
                    .build();
        }

        long orderCode = generateOrderCode();

        UserSubscription pendingSub = UserSubscription.builder()
                .userId(userId)
                .packageId(targetPack.getId())
                .startDate(LocalDateTime.now())
                .expireDate(null)
                .status(Constants.SUBSCRIPTION_STATUS.PENDING_PAYMENT)
                .orderCode(orderCode)
                .build();

        UserSubscription saved = subscriptionRepository.save(pendingSub);

        String payProvider = request.getPaymentProvider() != null ? request.getPaymentProvider() : Constants.PAYMENT_PROVIDER.STRIPE;
        long amount = 0L;
        if (Constants.PAYMENT_PROVIDER.PAYOS.equalsIgnoreCase(payProvider)) {
            amount = targetPack.getPriceVnd() != null ? targetPack.getPriceVnd().longValue() : 0L;
        } else {
            amount = targetPack.getPriceUsd() != null ? targetPack.getPriceUsd().longValue() : 0L;
        }

        PaymentCreateRequest payRequest = PaymentCreateRequest.builder()
                .paymentCode(orderCode)
                .amount(amount)
                .description("Nang cap goi " + targetPack.getCode())
                .returnUrl(returnUrl)
                .cancelUrl(cancelUrl)
                .paymentProvider(payProvider)
                .build();

        ApiResponse<PaymentCreateResponse> payResponse = paymentClient.createPaymentLink(payRequest);
        String redirectUrl = (payResponse != null && payResponse.getData() != null) 
                ? payResponse.getData().getPaymentUrl() 
                : null;
        String clientSecret = (payResponse != null && payResponse.getData() != null) 
                ? payResponse.getData().getClientSecret() 
                : null;

        return UpgradeResponse.builder()
                .subscriptionId(saved.getId())
                .paymentCode(orderCode)
                .status(Constants.SUBSCRIPTION_STATUS.PENDING_PAYMENT)
                .paymentRedirectUrl(redirectUrl)
                .clientSecret(clientSecret)
                .build();
    }

    @Transactional
    public void processPaymentCallback(Long orderCode) {
        log.info("[subscription-service] Nhận tín hiệu callback thanh toán cho orderCode: {}", orderCode);
        UserSubscription sub = subscriptionRepository.findByOrderCode(orderCode)
                .orElseThrow(() -> new AppException(ErrorCode.SUBSCRIPTION_NOT_FOUND));

        if (sub.getStatus() == Constants.SUBSCRIPTION_STATUS.ACTIVE) {
            log.info("[subscription-service] Subscription cho orderCode: {} đã ACTIVE trước đó.", orderCode);
            return;
        }

        deactivateAllActiveSubscriptions(sub.getUserId());

        SubscriptionPackage pack = packageRepository.findById(sub.getPackageId())
                .orElseThrow(() -> new AppException(ErrorCode.PACKAGE_NOT_FOUND));

        sub.setStatus(Constants.SUBSCRIPTION_STATUS.ACTIVE);
        sub.setStartDate(LocalDateTime.now());
        if (pack.getBillingCycle() != null && pack.getBillingCycle() == Constants.BILLING_CYCLE.YEARLY) {
            sub.setExpireDate(LocalDateTime.now().plusYears(1));
        } else {
            sub.setExpireDate(LocalDateTime.now().plusDays(30));
        }
        subscriptionRepository.save(sub);

        saveHistoryLog(sub.getUserId(), Constants.SUBSCRIPTION_ACTION.REGISTER, pack.getCode(), "Thanh toan PayOS thanh cong cho orderCode: " + orderCode);
        log.info("[subscription-service] Nâng cấp thành công gói {} cho userId: {}", pack.getCode(), sub.getUserId());
    }

    @Transactional
    public void cancel(UUID userId) {
        UserSubscription sub = subscriptionRepository.findActiveOrCanceledNotExpired(userId, LocalDateTime.now())
                .orElseThrow(() -> new AppException(ErrorCode.SUBSCRIPTION_NOT_FOUND));

        if (sub.getStatus() == Constants.SUBSCRIPTION_STATUS.CANCELED) {
            return; // Already canceled, do nothing
        }

        sub.setStatus(Constants.SUBSCRIPTION_STATUS.CANCELED);
        subscriptionRepository.save(sub);

        saveHistoryLog(userId, Constants.SUBSCRIPTION_ACTION.CANCEL, null, "User requested cancellation");
    }

    @Transactional
    public void reactivate(UUID userId) {
        UserSubscription sub = subscriptionRepository.findActiveOrCanceledNotExpired(userId, LocalDateTime.now())
                .orElseThrow(() -> new AppException(ErrorCode.SUBSCRIPTION_NOT_FOUND));

        if (sub.getStatus() == Constants.SUBSCRIPTION_STATUS.ACTIVE) {
            return; // Already active, do nothing
        }

        sub.setStatus(Constants.SUBSCRIPTION_STATUS.ACTIVE);
        subscriptionRepository.save(sub);

        saveHistoryLog(userId, Constants.SUBSCRIPTION_ACTION.EXTEND, null, "User reactivated subscription");
    }

    public List<QuotaResponse> getQuotas(UUID userId) {
        UserSubscriptionResponse activeSub = getOrCreateActiveSubscription(userId);
        SubscriptionPackage pack = packageRepository.findByCode(activeSub.getPackageCode())
                .orElseThrow(() -> new AppException(ErrorCode.PACKAGE_NOT_FOUND));

        List<PackageFeature> features = featureRepository.findByPackageId(pack.getId());

        List<QuotaResponse> quotaResponses = new ArrayList<>();
        for (PackageFeature feature : features) {
            if (feature.getFeatureKey().startsWith("MAX_")) {
                UserFeatureUsage usage = getOrInitUsage(userId, feature.getFeatureKey());
                int limit = feature.getFeatureValue();
                int current = usage.getUsageValue();
                int remaining = Math.max(0, limit - current);

                quotaResponses.add(QuotaResponse.builder()
                        .featureKey(feature.getFeatureKey())
                        .displayName(getDisplayName(feature.getFeatureKey()))
                        .limitValue(limit)
                        .currentUsage(current)
                        .remaining(remaining)
                        .lastResetTime(usage.getLastResetTime())
                        .build());
            }
        }
        return quotaResponses;
    }

    // --- INTERNAL API SERVICES ---

    @Transactional
    public QuotaCheckResponse checkQuota(UUID userId, String featureKey) {
        UserSubscriptionResponse activeSub = getOrCreateActiveSubscription(userId);
        SubscriptionPackage pack = packageRepository.findByCode(activeSub.getPackageCode())
                .orElseThrow(() -> new AppException(ErrorCode.PACKAGE_NOT_FOUND));

        PackageFeature feature = featureRepository.findByPackageIdAndFeatureKey(pack.getId(), featureKey)
                .orElse(null);

        if (feature == null) {
            return QuotaCheckResponse.builder()
                    .userId(userId)
                    .featureKey(featureKey)
                    .allowed(true)
                    .limitValue(999999)
                    .currentUsage(0)
                    .remaining(999999)
                    .build();
        }

        UserFeatureUsage usage = getOrInitUsage(userId, featureKey);
        int limit = feature.getFeatureValue();
        int current = usage.getUsageValue();
        int remaining = Math.max(0, limit - current);

        return QuotaCheckResponse.builder()
                .userId(userId)
                .featureKey(featureKey)
                .allowed(current < limit)
                .limitValue(limit)
                .currentUsage(current)
                .remaining(remaining)
                .build();
    }

    @Transactional
    public QuotaConsumeResponse consumeQuota(UUID userId, String featureKey, int amount) {
        UserFeatureUsage usage = getOrInitUsage(userId, featureKey);
        usage.setUsageValue(usage.getUsageValue() + amount);
        UserFeatureUsage saved = usageRepository.save(usage);

        return QuotaConsumeResponse.builder()
                .success(true)
                .userId(userId)
                .featureKey(featureKey)
                .newUsageValue(saved.getUsageValue())
                .build();
    }

    @Transactional
    public QuotaConsumeResponse revertQuota(UUID userId, String featureKey, int amount) {
        UserFeatureUsage usage = getOrInitUsage(userId, featureKey);
        int newVal = Math.max(0, usage.getUsageValue() - amount);
        usage.setUsageValue(newVal);
        UserFeatureUsage saved = usageRepository.save(usage);

        return QuotaConsumeResponse.builder()
                .success(true)
                .userId(userId)
                .featureKey(featureKey)
                .newUsageValue(saved.getUsageValue())
                .build();
    }

    public InternalUserStatusResponse getUserStatus(UUID userId) {
        UserSubscriptionResponse activeSub = getOrCreateActiveSubscription(userId);
        return InternalUserStatusResponse.builder()
                .userId(userId)
                .packageCode(activeSub.getPackageCode())
                .roleName("USER_" + activeSub.getPackageCode().toUpperCase())
                .status(activeSub.getStatus())
                .expireDate(activeSub.getExpireDate())
                .build();
    }

    // --- PRIVATE UTILITIES ---

    private long generateOrderCode() {
        long timestampPart = System.currentTimeMillis() % 10000000000L;
        long randomPart = random.nextInt(1000000);
        return timestampPart * 1000000L + randomPart;
    }

    private UserSubscriptionResponse mapToSubscriptionResponse(UserSubscription sub) {
        SubscriptionPackage pack = packageRepository.findById(sub.getPackageId())
                .orElseThrow(() -> new AppException(ErrorCode.PACKAGE_NOT_FOUND));

        return UserSubscriptionResponse.builder()
                .id(sub.getId())
                .userId(sub.getUserId())
                .packageCode(pack.getCode())
                .packageName(pack.getName())
                .startDate(sub.getStartDate())
                .expireDate(sub.getExpireDate())
                .status(sub.getStatus())
                .build();
    }

    private void deactivateAllActiveSubscriptions(UUID userId) {
        subscriptionRepository.findActiveOrCanceledNotExpired(userId, LocalDateTime.now())
                .ifPresent(sub -> {
                    sub.setStatus(Constants.SUBSCRIPTION_STATUS.EXPIRED);
                    subscriptionRepository.save(sub);
                });
    }

    private void saveHistoryLog(UUID userId, int action, String newPackageCode, String note) {
        SubscriptionHistory log = SubscriptionHistory.builder()
                .userId(userId)
                .action(action)
                .newPackageCode(newPackageCode)
                .note(note)
                .build();
        historyRepository.save(log);
    }

    private UserFeatureUsage getOrInitUsage(UUID userId, String featureKey) {
        UserFeatureUsage usage = usageRepository.findByUserIdAndFeatureKey(userId, featureKey)
                .orElseGet(() -> UserFeatureUsage.builder()
                        .userId(userId)
                        .featureKey(featureKey)
                        .usageValue(0)
                        .lastResetTime(LocalDateTime.now())
                        .build());

        if (shouldResetUsage(featureKey, usage.getLastResetTime())) {
            usage.setUsageValue(0);
            usage.setLastResetTime(LocalDateTime.now());
        }

        return usageRepository.save(usage);
    }

    private boolean shouldResetUsage(String featureKey, LocalDateTime lastResetTime) {
        LocalDateTime now = LocalDateTime.now();
        if (featureKey.contains("TODAY") || featureKey.contains("DAILY") || featureKey.contains("DAY")) {
            return lastResetTime.toLocalDate().isBefore(now.toLocalDate());
        }
        if (featureKey.contains("MONTH")) {
            return lastResetTime.getYear() < now.getYear() || lastResetTime.getMonthValue() < now.getMonthValue();
        }
        return false;
    }

    private String getDisplayName(String featureKey) {
        if (Constants.FEATURE_KEY.MAX_SLIDES_PER_DAY.equals(featureKey)) {
            return "Số bài trình chiếu được tạo trong ngày";
        } else if (Constants.FEATURE_KEY.MAX_IMAGES_PER_SLIDE.equals(featureKey)) {
            return "Số ảnh tối đa mỗi bài trình chiếu";
        }
        if (Constants.FEATURE_KEY.MAX_REVISIONS_PER_DAY.equals(featureKey)) {
            return "Số lần sửa slide trong ngày";
        }
        return featureKey;
    }

    public java.util.Map<String, Object> getSubscriptionStats() {
        log.info("[subscription-service] Đang tính toán dữ liệu thống kê subscription...");
        long activeCount = subscriptionRepository.countActiveSubscriptions();
        java.math.BigDecimal revVnd = subscriptionRepository.sumTotalRevenueVnd();
        java.math.BigDecimal revUsd = subscriptionRepository.sumTotalRevenueUsd();

        java.util.Map<String, Object> stats = new java.util.HashMap<>();
        stats.put("activeSubscriptionsCount", activeCount);
        stats.put("totalRevenueVnd", revVnd != null ? revVnd.doubleValue() : 0.0);
        stats.put("totalRevenueUsd", revUsd != null ? revUsd.doubleValue() : 0.0);
        return stats;
    }

    public java.util.Map<String, Object> getSubscriptionStatsInRange(java.time.Instant start, java.time.Instant end) {
        log.info("[subscription-service] Đang tính toán dữ liệu thống kê subscription theo khoảng thời gian...");
        long activeCountTotal = subscriptionRepository.countActiveSubscriptions();
        long activeCountPrev = subscriptionRepository.countActiveSubscriptionsBefore(start);
        long activeCountBetween = subscriptionRepository.countActiveSubscriptionsBetween(start, end);

        java.math.BigDecimal revVndTotal = subscriptionRepository.sumTotalRevenueVnd();
        java.math.BigDecimal revVndPrev = subscriptionRepository.sumRevenueVndBefore(start);
        java.math.BigDecimal revVndBetween = subscriptionRepository.sumRevenueVndBetween(start, end);

        java.math.BigDecimal revUsdTotal = subscriptionRepository.sumTotalRevenueUsd();
        java.math.BigDecimal revUsdPrev = subscriptionRepository.sumRevenueUsdBefore(start);
        java.math.BigDecimal revUsdBetween = subscriptionRepository.sumRevenueUsdBetween(start, end);

        java.util.Map<String, Object> stats = new java.util.HashMap<>();
        
        java.util.Map<String, Object> activeSubMap = new java.util.HashMap<>();
        activeSubMap.put("previous_value", activeCountPrev);
        activeSubMap.put("current_value", activeCountBetween);
        activeSubMap.put("total_value", activeCountTotal);
        stats.put("active_subscriptions", activeSubMap);

        java.util.Map<String, Object> revVndMap = new java.util.HashMap<>();
        revVndMap.put("previous_value", revVndPrev != null ? revVndPrev.doubleValue() : 0.0);
        revVndMap.put("current_value", revVndBetween != null ? revVndBetween.doubleValue() : 0.0);
        revVndMap.put("total_value", revVndTotal != null ? revVndTotal.doubleValue() : 0.0);
        stats.put("revenue_vnd", revVndMap);

        java.util.Map<String, Object> revUsdMap = new java.util.HashMap<>();
        revUsdMap.put("previous_value", revUsdPrev != null ? revUsdPrev.doubleValue() : 0.0);
        revUsdMap.put("current_value", revUsdBetween != null ? revUsdBetween.doubleValue() : 0.0);
        revUsdMap.put("total_value", revUsdTotal != null ? revUsdTotal.doubleValue() : 0.0);
        stats.put("revenue_usd", revUsdMap);

        // Phân bổ gói cước thực tế từ DB
        java.util.List<Object[]> pkgDist = subscriptionRepository.getPackageDistributionInRange(start, end);
        java.util.List<java.util.Map<String, Object>> packageDistributionList = new java.util.ArrayList<>();
        double totalPackages = 0;
        for (Object[] row : pkgDist) {
            totalPackages += ((Number) row[1]).doubleValue();
        }
        for (Object[] row : pkgDist) {
            java.util.Map<String, Object> map = new java.util.HashMap<>();
            String pkgName = (String) row[0];
            long count = ((Number) row[1]).longValue();
            map.put("package_name", pkgName);
            map.put("count", count);
            map.put("percent", totalPackages > 0 ? Math.round((count / totalPackages) * 1000.0) / 10.0 : 0.0);
            packageDistributionList.add(map);
        }
        stats.put("package_distribution", packageDistributionList);

        // Phân bổ trạng thái giao dịch thực tế từ DB
        java.util.List<Object[]> statusDist = subscriptionRepository.getTransactionStatusDistributionInRange(start, end);
        java.util.List<java.util.Map<String, Object>> statusDistributionList = new java.util.ArrayList<>();
        double totalStatuses = 0;
        for (Object[] row : statusDist) {
            totalStatuses += ((Number) row[1]).doubleValue();
        }
        for (Object[] row : statusDist) {
            java.util.Map<String, Object> map = new java.util.HashMap<>();
            int statusVal = ((Number) row[0]).intValue();
            long count = ((Number) row[1]).longValue();
            String statusName = "Khác";
            if (statusVal == 0) statusName = "Đang xử lý (PENDING)";
            else if (statusVal == 1) statusName = "Thành công (SUCCESS)";
            else if (statusVal == 3) statusName = "Bị hủy (CANCELLED)";
            
            map.put("package_name", statusName);
            map.put("count", count);
            map.put("percent", totalStatuses > 0 ? Math.round((count / totalStatuses) * 1000.0) / 10.0 : 0.0);
            statusDistributionList.add(map);
        }
        stats.put("transaction_status_distribution", statusDistributionList);

        long expiringCount = subscriptionRepository.countExpiringSubscriptions(
            java.time.LocalDateTime.now(), 
            java.time.LocalDateTime.now().plusDays(3)
        );
        stats.put("expiring_subscriptions_count", expiringCount);

        return stats;
    }

    public java.util.Map<String, String> getActivePackageCodesByUserIds(java.util.List<UUID> userIds) {
        java.util.Map<String, String> map = new java.util.HashMap<>();
        if (userIds == null || userIds.isEmpty()) return map;
        java.util.List<Object[]> results = subscriptionRepository.findActivePackageCodesByUserIds(userIds);
        for (Object[] row : results) {
            map.put(row[0].toString(), (String) row[1]);
        }
        return map;
    }
}
