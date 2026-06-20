package com.backend.subscriptionservice.repository;

import com.backend.subscriptionservice.entity.UserSubscription;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.Optional;
import java.util.UUID;

@Repository
public interface UserSubscriptionRepository extends JpaRepository<UserSubscription, UUID> {

    /**
     * Lấy subscription đang ACTIVE của user
     */
    Optional<UserSubscription> findByUserIdAndStatus(UUID userId, Integer status);

    /**
     * Kiểm tra user có subscription ACTIVE không
     */
    boolean existsByUserIdAndStatus(UUID userId, Integer status);

    /**
     * Lấy subscription mới nhất của user (bất kể trạng thái)
     */
    Optional<UserSubscription> findTopByUserIdOrderByCreatedAtDesc(UUID userId);

    /**
     * Lấy subscription đang hoạt động (ACTIVE hoặc CANCELED nhưng chưa hết hạn)
     */
    @Query("SELECT s FROM UserSubscription s WHERE s.userId = :userId AND " +
           "(s.status = 1 OR (s.status = 3 AND (s.expireDate IS NULL OR s.expireDate > :now)))")
    Optional<UserSubscription> findActiveOrCanceledNotExpired(@Param("userId") UUID userId, @Param("now") LocalDateTime now);
}
