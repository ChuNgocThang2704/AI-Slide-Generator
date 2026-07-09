package com.backend.subscriptionservice.repository;

import com.backend.subscriptionservice.entity.PackageFeature;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Repository
public interface PackageFeatureRepository extends JpaRepository<PackageFeature, UUID> {
    List<PackageFeature> findByPackageId(UUID packageId);
    Optional<PackageFeature> findByPackageIdAndFeatureKey(UUID packageId, String featureKey);
    void deleteByPackageIdAndFeatureKey(UUID packageId, String featureKey);
}
