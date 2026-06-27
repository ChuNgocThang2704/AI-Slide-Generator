package com.backend.subscriptionservice.entity;

import jakarta.persistence.*;
import lombok.*;
import lombok.experimental.SuperBuilder;
import org.hibernate.annotations.SQLDelete;
import org.hibernate.annotations.Where;

import java.time.LocalDateTime;
import java.util.UUID;

@Entity
@Table(name = "user_subscriptions", indexes = {
        @Index(name = "idx_user_subscriptions_user_id", columnList = "user_id"),
        @Index(name = "idx_user_subscriptions_status", columnList = "status"),
        @Index(name = "idx_user_subscriptions_order_code", columnList = "order_code")
})
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@SuperBuilder
@Where(clause = "is_active = true")
@SQLDelete(sql = "UPDATE user_subscriptions SET is_active = false WHERE id = ?")
public class UserSubscription extends AbstractAuditingEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "id", updatable = false, nullable = false)
    private UUID id;

    @Column(name = "user_id", nullable = false)
    private UUID userId;

    @Column(name = "package_id", nullable = false)
    private UUID packageId;

    @Column(name = "start_date", nullable = false)
    private LocalDateTime startDate;

    @Column(name = "expire_date")
    private LocalDateTime expireDate;

    @Column(name = "status", nullable = false)
    private Integer status;

    @Column(name = "quota_reset_date")
    private LocalDateTime quotaResetDate;

    @Column(name = "order_code")
    private Long orderCode;
}
