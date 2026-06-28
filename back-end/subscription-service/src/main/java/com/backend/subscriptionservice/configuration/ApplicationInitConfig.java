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

            // 1. Khởi tạo Gói FREE
            SubscriptionPackage freePack = packageRepository.findByCode(Constants.PACKAGE_CODE.FREE).orElseGet(() ->
                    packageRepository.save(SubscriptionPackage.builder()
                            .code(Constants.PACKAGE_CODE.FREE)
                            .name("Gói Miễn Phí")
                            .description("Dành cho trải nghiệm cơ bản (3 slide/ngày)")
                            .price(BigDecimal.ZERO)
                            .billingCycle(Constants.BILLING_CYCLE.MONTHLY)
                            .build())
            );
            initFeatureIfNotExist(freePack.getId(), Constants.FEATURE_KEY.MAX_SLIDES_PER_DAY, 3);
            initFeatureIfNotExist(freePack.getId(), Constants.FEATURE_KEY.MAX_IMAGES_PER_SLIDE, 5);
            initFeatureIfNotExist(freePack.getId(), Constants.FEATURE_KEY.ALLOW_EXPORT_PDF, 0); // 0: False
 
            // 2. Khởi tạo Gói PRO
            SubscriptionPackage proPack = packageRepository.findByCode(Constants.PACKAGE_CODE.PRO).orElseGet(() ->
                    packageRepository.save(SubscriptionPackage.builder()
                            .code(Constants.PACKAGE_CODE.PRO)
                            .name("Gói Chuyên Nghiệp")
                            .description("Tính năng nâng cao (20 slide/ngày, ảnh HD, Xuất PDF)")
                            .price(new BigDecimal("199000"))
                            .billingCycle(Constants.BILLING_CYCLE.MONTHLY)
                            .build())
            );
            initFeatureIfNotExist(proPack.getId(), Constants.FEATURE_KEY.MAX_SLIDES_PER_DAY, 20);
            initFeatureIfNotExist(proPack.getId(), Constants.FEATURE_KEY.MAX_IMAGES_PER_SLIDE, 15);
            initFeatureIfNotExist(proPack.getId(), Constants.FEATURE_KEY.ALLOW_EXPORT_PDF, 1); // 1: True
 
            // 3. Khởi tạo Gói ULTRA (hoặc EXTRA)
            SubscriptionPackage ultraPack = packageRepository.findByCode(Constants.PACKAGE_CODE.ULTRA).orElseGet(() ->
                    packageRepository.save(SubscriptionPackage.builder()
                            .code(Constants.PACKAGE_CODE.ULTRA)
                            .name("Gói Vô Cực")
                            .description("Đầy đủ quyền năng thiết kế slide không giới hạn")
                            .price(new BigDecimal("499000"))
                            .billingCycle(Constants.BILLING_CYCLE.MONTHLY)
                            .build())
            );
            initFeatureIfNotExist(ultraPack.getId(), Constants.FEATURE_KEY.MAX_SLIDES_PER_DAY, 999999);
            initFeatureIfNotExist(ultraPack.getId(), Constants.FEATURE_KEY.MAX_IMAGES_PER_SLIDE, 35);
            initFeatureIfNotExist(ultraPack.getId(), Constants.FEATURE_KEY.ALLOW_EXPORT_PDF, 1);
            initFeatureIfNotExist(ultraPack.getId(), Constants.FEATURE_KEY.ALLOW_CUSTOM_TEMPLATE, 1);

            log.info("Subscription-service database initialization completed successfully.");
        };
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
