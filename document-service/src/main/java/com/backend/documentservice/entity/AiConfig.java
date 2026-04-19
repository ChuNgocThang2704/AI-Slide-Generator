package com.backend.documentservice.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import org.hibernate.annotations.SQLDelete;
import org.hibernate.annotations.Where;

import java.util.UUID;

@Entity
@Table(name = "ai_configs")
@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
@SQLDelete(sql = "UPDATE ai_configs SET is_active = false WHERE id = ?")
@Where(clause = "is_active = true")
public class AiConfig extends AbstractAuditingEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @Column(name = "role_code", unique = true)
    private String roleCode;

    @Column(name = "config_name", nullable = false)
    private String configName;

    @Column(name = "language", nullable = false)
    private String language;

    @Column(name = "tone", nullable = false)
    private String tone;

    @Column(name = "max_projects_per_day")
    private Integer maxProjectsPerDay;

    @Column(name = "min_pages_per_project")
    private Integer minPagesPerProject;

    @Column(name = "max_pages_per_project")
    private Integer maxPagesPerProject;
}
