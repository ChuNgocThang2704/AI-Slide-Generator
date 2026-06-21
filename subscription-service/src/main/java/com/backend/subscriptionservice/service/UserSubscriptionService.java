package com.backend.subscriptionservice.service;

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

    @Transactional
    public UserSubscriptionResponse getOrCreateActiveSubscription(UUID userId) {
        return subscriptionRepository.findActiveOrCanceledNotExpired(userId, LocalDateTime.now())
                .map(this::mapToSubscriptionResponse)
                .orElseGet(() -> {
                    log.info("No active subscription found for user: {}. Auto-provisioning FREE package.", userId);
                    SubscriptionPackage freePack = packageRepository.findByCode(Constants.PACKAGE_CODE.FREE)
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
                            .note("Auto-provisioned on query fallback")
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
        SubscriptionPackage targetPack = packageRepository.findByCode(request.getPackageCode())
                .orElseThrow(() -> new AppException(ErrorCode.PACKAGE_NOT_FOUND));

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

        UserSubscription pendingSub = UserSubscription.builder()
                .userId(userId)
                .packageId(targetPack.getId())
                .startDate(LocalDateTime.now())
                .expireDate(null)
                .status(Constants.SUBSCRIPTION_STATUS.PENDING_PAYMENT)
                .build();

        UserSubscription saved = subscriptionRepository.save(pendingSub);

        return UpgradeResponse.builder()
                .subscriptionId(saved.getId())
                .status(Constants.SUBSCRIPTION_STATUS.PENDING_PAYMENT)
                .paymentRedirectUrl(null)
                .build();
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

        // Tìm limit trong PackageFeature
        PackageFeature feature = featureRepository.findByPackageIdAndFeatureKey(pack.getId(), featureKey)
                .orElse(null);

        if (feature == null) {
            // Không tìm thấy cấu hình hạn mức nghĩa là cho phép không giới hạn hoặc mặc định không cho
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
            return "Số Slide được tạo trong ngày";
        } else if (Constants.FEATURE_KEY.MAX_IMAGES_PER_SLIDE.equals(featureKey)) {
            return "Số ảnh tối đa mỗi slide";
        }
        return featureKey;
    }
}
