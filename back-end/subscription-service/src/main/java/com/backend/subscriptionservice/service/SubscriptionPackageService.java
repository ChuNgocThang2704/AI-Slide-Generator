package com.backend.subscriptionservice.service;

import com.backend.subscriptionservice.dto.request.CreatePackageRequest;
import com.backend.subscriptionservice.dto.request.FeatureRequest;
import com.backend.subscriptionservice.dto.request.UpdatePackageRequest;
import com.backend.subscriptionservice.dto.response.FeatureResponse;
import com.backend.subscriptionservice.dto.response.PackageResponse;
import com.backend.subscriptionservice.entity.PackageFeature;
import com.backend.subscriptionservice.entity.SubscriptionPackage;
import com.backend.subscriptionservice.exception.AppException;
import com.backend.subscriptionservice.exception.ErrorCode;
import com.backend.subscriptionservice.repository.PackageFeatureRepository;
import com.backend.subscriptionservice.repository.SubscriptionPackageRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.UUID;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class SubscriptionPackageService {

    private final SubscriptionPackageRepository packageRepository;
    private final PackageFeatureRepository featureRepository;

    public List<PackageResponse> getPackages() {
        return packageRepository.findAll().stream()
                .map(this::mapToPackageResponse)
                .collect(Collectors.toList());
    }

    public PackageResponse getPackageByCode(String code) {
        SubscriptionPackage subscriptionPackage = packageRepository.findByCode(code)
                .orElseThrow(() -> new AppException(ErrorCode.PACKAGE_NOT_FOUND));
        return mapToPackageResponse(subscriptionPackage);
    }

    @Transactional
    public PackageResponse createPackage(CreatePackageRequest request) {
        if (packageRepository.existsByCode(request.getCode())) {
            throw new AppException(ErrorCode.PACKAGE_ALREADY_EXISTS);
        }
        SubscriptionPackage pack = SubscriptionPackage.builder()
                .code(request.getCode())
                .name(request.getName())
                .description(request.getDescription())
                .price(request.getPrice())
                .billingCycle(request.getBillingCycle())
                .build();
        SubscriptionPackage saved = packageRepository.save(pack);
        return mapToPackageResponse(saved);
    }

    @Transactional
    public PackageResponse updatePackage(UUID id, UpdatePackageRequest request) {
        SubscriptionPackage pack = packageRepository.findById(id)
                .orElseThrow(() -> new AppException(ErrorCode.PACKAGE_NOT_FOUND));
        pack.setName(request.getName());
        pack.setDescription(request.getDescription());
        pack.setPrice(request.getPrice());
        pack.setBillingCycle(request.getBillingCycle());
        SubscriptionPackage saved = packageRepository.save(pack);
        return mapToPackageResponse(saved);
    }

    @Transactional
    public void deletePackage(UUID id) {
        SubscriptionPackage pack = packageRepository.findById(id)
                .orElseThrow(() -> new AppException(ErrorCode.PACKAGE_NOT_FOUND));
        packageRepository.delete(pack);
    }

    @Transactional
    public void addFeature(UUID packageId, FeatureRequest request) {
        SubscriptionPackage pack = packageRepository.findById(packageId)
                .orElseThrow(() -> new AppException(ErrorCode.PACKAGE_NOT_FOUND));

        if (featureRepository.findByPackageIdAndFeatureKey(packageId, request.getFeatureKey()).isPresent()) {
            throw new AppException(ErrorCode.FEATURE_ALREADY_EXISTS);
        }

        PackageFeature feature = PackageFeature.builder()
                .packageId(packageId)
                .featureKey(request.getFeatureKey())
                .featureValue(request.getFeatureValue())
                .build();
        featureRepository.save(feature);
    }

    @Transactional
    public void updateFeature(UUID packageId, String featureKey, FeatureRequest request) {
        SubscriptionPackage pack = packageRepository.findById(packageId)
                .orElseThrow(() -> new AppException(ErrorCode.PACKAGE_NOT_FOUND));

        PackageFeature feature = featureRepository.findByPackageIdAndFeatureKey(packageId, featureKey)
                .orElseThrow(() -> new AppException(ErrorCode.FEATURE_NOT_FOUND));

        feature.setFeatureValue(request.getFeatureValue());
        featureRepository.save(feature);
    }

    @Transactional
    public void deleteFeature(UUID packageId, String featureKey) {
        SubscriptionPackage pack = packageRepository.findById(packageId)
                .orElseThrow(() -> new AppException(ErrorCode.PACKAGE_NOT_FOUND));

        PackageFeature feature = featureRepository.findByPackageIdAndFeatureKey(packageId, featureKey)
                .orElseThrow(() -> new AppException(ErrorCode.FEATURE_NOT_FOUND));

        featureRepository.delete(feature);
    }

    private PackageResponse mapToPackageResponse(SubscriptionPackage pack) {
        List<FeatureResponse> features = featureRepository.findByPackageId(pack.getId()).stream()
                .map(f -> FeatureResponse.builder()
                        .featureKey(f.getFeatureKey())
                        .featureValue(f.getFeatureValue())
                        .build())
                .collect(Collectors.toList());

        return PackageResponse.builder()
                .id(pack.getId())
                .code(pack.getCode())
                .name(pack.getName())
                .description(pack.getDescription())
                .price(pack.getPrice())
                .billingCycle(pack.getBillingCycle())
                .features(features)
                .build();
    }
}
