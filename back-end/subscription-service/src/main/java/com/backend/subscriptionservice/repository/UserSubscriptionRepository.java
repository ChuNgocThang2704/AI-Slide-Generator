package com.backend.subscriptionservice.repository;

import com.backend.subscriptionservice.entity.UserSubscription;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.Optional;
import java.util.UUID;
import java.util.List;

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
     * Lấy subscription theo mã đơn hàng orderCode
     */
    Optional<UserSubscription> findByOrderCode(Long orderCode);

    /**
     * Lấy subscription đang hoạt động (ACTIVE hoặc CANCELED nhưng chưa hết hạn)
     */
    @Query("SELECT s FROM UserSubscription s WHERE s.userId = :userId AND " +
           "(s.status = 1 OR (s.status = 3 AND (s.expireDate IS NULL OR s.expireDate > :now)))")
    Optional<UserSubscription> findActiveOrCanceledNotExpired(@Param("userId") UUID userId, @Param("now") LocalDateTime now);

    @Query("SELECT COUNT(s) FROM UserSubscription s WHERE s.status = 1")
    long countActiveSubscriptions();

    @Query("SELECT SUM(p.priceVnd) FROM UserSubscription s JOIN SubscriptionPackage p ON s.packageId = p.id WHERE s.status = 1")
    java.math.BigDecimal sumTotalRevenueVnd();

    @Query("SELECT SUM(p.priceUsd) FROM UserSubscription s JOIN SubscriptionPackage p ON s.packageId = p.id WHERE s.status = 1")
    java.math.BigDecimal sumTotalRevenueUsd();

    @Query("SELECT COUNT(s) FROM UserSubscription s WHERE s.status = 1 AND s.createdAt < :date")
    long countActiveSubscriptionsBefore(@Param("date") java.time.Instant date);

    @Query("SELECT COUNT(s) FROM UserSubscription s WHERE s.status = 1 AND s.createdAt >= :startDate AND s.createdAt <= :endDate")
    long countActiveSubscriptionsBetween(@Param("startDate") java.time.Instant startDate, @Param("endDate") java.time.Instant endDate);

    @Query("SELECT SUM(p.priceVnd) FROM UserSubscription s JOIN SubscriptionPackage p ON s.packageId = p.id WHERE s.status = 1 AND s.createdAt < :date")
    java.math.BigDecimal sumRevenueVndBefore(@Param("date") java.time.Instant date);

    @Query("SELECT SUM(p.priceVnd) FROM UserSubscription s JOIN SubscriptionPackage p ON s.packageId = p.id WHERE s.status = 1 AND s.createdAt >= :startDate AND s.createdAt <= :endDate")
    java.math.BigDecimal sumRevenueVndBetween(@Param("startDate") java.time.Instant startDate, @Param("endDate") java.time.Instant endDate);

    @Query("SELECT SUM(p.priceUsd) FROM UserSubscription s JOIN SubscriptionPackage p ON s.packageId = p.id WHERE s.status = 1 AND s.createdAt < :date")
    java.math.BigDecimal sumRevenueUsdBefore(@Param("date") java.time.Instant date);

    @Query("SELECT SUM(p.priceUsd) FROM UserSubscription s JOIN SubscriptionPackage p ON s.packageId = p.id WHERE s.status = 1 AND s.createdAt >= :startDate AND s.createdAt <= :endDate")
    java.math.BigDecimal sumRevenueUsdBetween(@Param("startDate") java.time.Instant startDate, @Param("endDate") java.time.Instant endDate);

    @Query("SELECT s.userId, p.code FROM UserSubscription s JOIN SubscriptionPackage p ON s.packageId = p.id WHERE s.userId IN :userIds AND s.status = 1")
    List<Object[]> findActivePackageCodesByUserIds(@Param("userIds") List<UUID> userIds);

    @Query("SELECT p.name, COUNT(s) FROM UserSubscription s JOIN SubscriptionPackage p ON s.packageId = p.id WHERE s.status = 1 AND s.createdAt >= :startDate AND s.createdAt <= :endDate GROUP BY p.name")
    List<Object[]> getPackageDistributionInRange(@Param("startDate") java.time.Instant startDate, @Param("endDate") java.time.Instant endDate);

    @Query("SELECT s.status, COUNT(s) FROM UserSubscription s WHERE s.createdAt >= :startDate AND s.createdAt <= :endDate GROUP BY s.status")
    List<Object[]> getTransactionStatusDistributionInRange(@Param("startDate") java.time.Instant startDate, @Param("endDate") java.time.Instant endDate);

    @Query("SELECT COUNT(s) FROM UserSubscription s WHERE s.status = 1 AND s.expireDate >= :now AND s.expireDate <= :future")
    long countExpiringSubscriptions(@Param("now") java.time.LocalDateTime now, @Param("future") java.time.LocalDateTime future);
}
