package com.backend.subscriptionservice.repository;

import com.backend.subscriptionservice.entity.UserFeatureUsage;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;
import java.util.UUID;

@Repository
public interface UserFeatureUsageRepository extends JpaRepository<UserFeatureUsage, UUID> {

    Optional<UserFeatureUsage> findByUserIdAndFeatureKey(UUID userId, String featureKey);
}
