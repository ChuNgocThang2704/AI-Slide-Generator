package com.backend.subscriptionservice.entity;

import jakarta.persistence.*;
import lombok.*;
import lombok.experimental.SuperBuilder;
import org.hibernate.annotations.SQLDelete;
import org.hibernate.annotations.Where;

import java.math.BigDecimal;
import java.util.UUID;

@Entity
@Table(name = "subscription_packages", uniqueConstraints = {
    @UniqueConstraint(name = "uk_subscription_packages_code_billing_cycle", columnNames = {"code", "billing_cycle"})
})
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@SuperBuilder
@Where(clause = "is_active = true")
@SQLDelete(sql = "UPDATE subscription_packages SET is_active = false WHERE id = ?")
public class SubscriptionPackage extends AbstractAuditingEntity {
    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "id", updatable = false, nullable = false)
    private UUID id;

    @Column(name = "code", nullable = false, length = 50)
    private String code;

    @Column(name = "name", nullable = false, length = 100)
    private String name;

    @Column(name = "description", columnDefinition = "TEXT")
    private String description;

    @Column(name = "price_vnd")
    private BigDecimal priceVnd;

    @Column(name = "price_usd")
    private BigDecimal priceUsd;

    @Column(name = "billing_cycle")
    private Integer billingCycle;
}
