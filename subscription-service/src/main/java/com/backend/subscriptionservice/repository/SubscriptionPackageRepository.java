package com.backend.subscriptionservice.repository;

import com.backend.subscriptionservice.entity.SubscriptionPackage;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;
import java.util.UUID;

@Repository
public interface SubscriptionPackageRepository extends JpaRepository<SubscriptionPackage, UUID> {

    Optional<SubscriptionPackage> findByCode(String code);

    boolean existsByCode(String code);
}
