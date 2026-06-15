package com.backend.subscriptionservice.entity;

import jakarta.persistence.*;
import lombok.*;
import lombok.experimental.SuperBuilder;
import org.hibernate.annotations.SQLDelete;
import org.hibernate.annotations.Where;

import java.util.UUID;

@Entity
@Table(name = "subscription_history", indexes = {
        @Index(name = "idx_subscription_history_user_id", columnList = "user_id")
})
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@SuperBuilder
@Where(clause = "is_active = true")
@SQLDelete(sql = "UPDATE subscription_history SET is_active = false WHERE id = ?")
public class SubscriptionHistory extends AbstractAuditingEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "id", updatable = false, nullable = false)
    private UUID id;

    @Column(name = "user_id", nullable = false)
    private UUID userId;

    @Column(name = "action", nullable = false)
    private Integer action;

    @Column(name = "previous_package_code", length = 50)
    private String previousPackageCode;

    @Column(name = "new_package_code", length = 50)
    private String newPackageCode;

    @Column(name = "note", columnDefinition = "TEXT")
    private String note;
}
