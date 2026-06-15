package com.backend.subscriptionservice.entity;

import jakarta.persistence.*;
import lombok.*;
import lombok.experimental.SuperBuilder;
import org.hibernate.annotations.SQLDelete;
import org.hibernate.annotations.Where;

import java.util.UUID;

@Entity
@Table(name = "package_features", uniqueConstraints = {
        @UniqueConstraint(columnNames = {"package_id", "feature_key"})
})
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@SuperBuilder
@Where(clause = "is_active = true")
@SQLDelete(sql = "UPDATE package_features SET is_active = false WHERE id = ?")
public class PackageFeature extends AbstractAuditingEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "id", updatable = false, nullable = false)
    private UUID id;

    @Column(name = "package_id")
    private UUID packageId;

    @Column(name = "feature_key")
    private String featureKey;

    @Column(name = "feature_value")
    private Integer featureValue;
}
