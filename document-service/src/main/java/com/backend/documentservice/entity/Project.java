package com.backend.documentservice.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import lombok.experimental.SuperBuilder;
import org.hibernate.annotations.SQLDelete;
import org.hibernate.annotations.Where;
import org.hibernate.annotations.JdbcTypeCode;

import java.sql.Types;
import java.util.UUID;

@Entity
@Table(name = "projects")
@Getter
@Setter
@SuperBuilder
@NoArgsConstructor
@SQLDelete(sql = "UPDATE projects SET is_active = false WHERE id = ?")
@Where(clause = "is_active = true")
public class Project extends AbstractAuditingEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @JdbcTypeCode(Types.VARCHAR)
    private UUID id;

    @Column(name = "name", nullable = false)
    private String name;

    @Column(name = "owner_id", nullable = false)
    @JdbcTypeCode(Types.VARCHAR)
    private UUID ownerId;

    @Column(name = "source_doc_id")
    @JdbcTypeCode(Types.VARCHAR)
    private UUID sourceDocId;

    @Column(name = "template_id")
    @JdbcTypeCode(Types.VARCHAR)
    private UUID templateId;

    @Column(name = "ai_config_id")
    @JdbcTypeCode(Types.VARCHAR)
    private UUID aiConfigId;

    @Column(name = "initial_prompt", columnDefinition = "TEXT")
    private String initialPrompt;

    @Column(name = "slide_url")
    private String slideUrl;

    @Column(name = "status")
    private Integer status;
}
