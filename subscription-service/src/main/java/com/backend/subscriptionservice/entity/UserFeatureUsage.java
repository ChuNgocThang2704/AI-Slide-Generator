package com.backend.subscriptionservice.entity;

import jakarta.persistence.*;
import lombok.*;
import lombok.experimental.SuperBuilder;
import org.hibernate.annotations.SQLDelete;
import org.hibernate.annotations.Where;

import java.time.LocalDateTime;
import java.util.UUID;

@Entity
@Table(name = "user_feature_usages", uniqueConstraints = {
        @UniqueConstraint(columnNames = {"user_id", "feature_key"})
}, indexes = {
        @Index(name = "idx_user_feature_usages_user_id", columnList = "user_id")
})
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@SuperBuilder
@Where(clause = "is_active = true")
@SQLDelete(sql = "UPDATE user_feature_usages SET is_active = false WHERE id = ?")
public class UserFeatureUsage extends AbstractAuditingEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "id", updatable = false, nullable = false)
    private UUID id;

    @Column(name = "user_id", nullable = false)
    private UUID userId;

    @Column(name = "feature_key", nullable = false, length = 100)
    private String featureKey;

    @Column(name = "usage_value", nullable = false)
    private Integer usageValue;

    @Column(name = "last_reset_time", nullable = false)
    private LocalDateTime lastResetTime;
}
