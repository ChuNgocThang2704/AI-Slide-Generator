package com.backend.subscriptionservice.configuration;

import com.backend.subscriptionservice.entity.PackageFeature;
import com.backend.subscriptionservice.entity.SubscriptionPackage;
import com.backend.subscriptionservice.repository.PackageFeatureRepository;
import com.backend.subscriptionservice.repository.SubscriptionPackageRepository;
import com.backend.subscriptionservice.util.Constants;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.ApplicationRunner;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.math.BigDecimal;
import java.util.UUID;

@Configuration
@RequiredArgsConstructor
@Slf4j
public class ApplicationInitConfig {

    private final SubscriptionPackageRepository packageRepository;
    private final PackageFeatureRepository featureRepository;

    @Bean
    ApplicationRunner initDatabase() {
        return args -> {
            log.info("Start initializing subscription-service packages and features...");

            // 1. Khởi tạo Gói FREE ($0 USD / 0 VNĐ)
            SubscriptionPackage freePack = packageRepository.findByCodeAndBillingCycle(Constants.PACKAGE_CODE.FREE, Constants.BILLING_CYCLE.MONTHLY).orElseGet(() ->
                    packageRepository.save(SubscriptionPackage.builder()
                            .code(Constants.PACKAGE_CODE.FREE)
                            .name("Gói Miễn Phí")
                            .description("Dành cho trải nghiệm cơ bản (3 slide/ngày)")
                            .priceVnd(BigDecimal.ZERO)
                            .priceUsd(BigDecimal.ZERO)
                            .billingCycle(Constants.BILLING_CYCLE.MONTHLY)
                            .build())
            );
            updatePackagePricesIfNull(freePack, BigDecimal.ZERO, BigDecimal.ZERO);
            initFeatureIfNotExist(freePack.getId(), Constants.FEATURE_KEY.MAX_SLIDES_PER_DAY, 3);
            initFeatureIfNotExist(freePack.getId(), Constants.FEATURE_KEY.MAX_IMAGES_PER_SLIDE, 5);
            initFeatureIfNotExist(freePack.getId(), Constants.FEATURE_KEY.ALLOW_EXPORT_PDF, 0); // 0: False

            // 2. Khởi tạo Gói PRO ($10 USD / 199.000 VNĐ)
            SubscriptionPackage proPack = packageRepository.findByCodeAndBillingCycle(Constants.PACKAGE_CODE.PRO, Constants.BILLING_CYCLE.MONTHLY).orElseGet(() ->
                    packageRepository.save(SubscriptionPackage.builder()
                            .code(Constants.PACKAGE_CODE.PRO)
                            .name("Gói Chuyên Nghiệp")
                            .description("Tính năng nâng cao (20 slide/ngày, ảnh HD, Xuất PDF)")
                            .priceVnd(new BigDecimal("199000"))
                            .priceUsd(new BigDecimal("10"))
                            .billingCycle(Constants.BILLING_CYCLE.MONTHLY)
                            .build())
            );
            updatePackagePricesIfNull(proPack, new BigDecimal("199000"), new BigDecimal("10"));
            initFeatureIfNotExist(proPack.getId(), Constants.FEATURE_KEY.MAX_SLIDES_PER_DAY, 20);
            initFeatureIfNotExist(proPack.getId(), Constants.FEATURE_KEY.MAX_IMAGES_PER_SLIDE, 15);
            initFeatureIfNotExist(proPack.getId(), Constants.FEATURE_KEY.ALLOW_EXPORT_PDF, 1); // 1: True

            // 3. Khởi tạo Gói ULTRA ($20 USD / 499.000 VNĐ)
            SubscriptionPackage ultraPack = packageRepository.findByCodeAndBillingCycle(Constants.PACKAGE_CODE.ULTRA, Constants.BILLING_CYCLE.MONTHLY).orElseGet(() ->
                    packageRepository.save(SubscriptionPackage.builder()
                            .code(Constants.PACKAGE_CODE.ULTRA)
                            .name("Gói Vô Cực")
                            .description("Đầy đủ quyền năng thiết kế slide không giới hạn")
                            .priceVnd(new BigDecimal("499000"))
                            .priceUsd(new BigDecimal("20"))
                            .billingCycle(Constants.BILLING_CYCLE.MONTHLY)
                            .build())
            );
            updatePackagePricesIfNull(ultraPack, new BigDecimal("499000"), new BigDecimal("20"));
            initFeatureIfNotExist(ultraPack.getId(), Constants.FEATURE_KEY.MAX_SLIDES_PER_DAY, 999999);
            initFeatureIfNotExist(ultraPack.getId(), Constants.FEATURE_KEY.MAX_IMAGES_PER_SLIDE, 35);
            initFeatureIfNotExist(ultraPack.getId(), Constants.FEATURE_KEY.ALLOW_EXPORT_PDF, 1);
            initFeatureIfNotExist(ultraPack.getId(), Constants.FEATURE_KEY.ALLOW_CUSTOM_TEMPLATE, 1);

            log.info("Subscription-service database initialization completed successfully.");
        };
    }

    private void updatePackagePricesIfNull(SubscriptionPackage pack, BigDecimal priceVnd, BigDecimal priceUsd) {
        boolean updated = false;
        if (pack.getPriceVnd() == null) {
            pack.setPriceVnd(priceVnd);
            updated = true;
        }
        if (pack.getPriceUsd() == null) {
            pack.setPriceUsd(priceUsd);
            updated = true;
        }
        if (updated) {
            packageRepository.save(pack);
        }
    }

    private void initFeatureIfNotExist(UUID packageId, String featureKey, Integer value) {
        if (featureRepository.findByPackageIdAndFeatureKey(packageId, featureKey).isEmpty()) {
            featureRepository.save(PackageFeature.builder()
                    .packageId(packageId)
                    .featureKey(featureKey)
                    .featureValue(value)
                    .build());
        }
    }
}
