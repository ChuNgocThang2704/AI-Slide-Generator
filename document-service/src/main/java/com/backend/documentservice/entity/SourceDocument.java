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
@Table(name = "source_documents")
@Getter
@Setter
@SuperBuilder
@NoArgsConstructor
@SQLDelete(sql = "UPDATE source_documents SET is_active = false WHERE id = ?")
@Where(clause = "is_active = true")
public class SourceDocument extends AbstractAuditingEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @JdbcTypeCode(Types.VARCHAR)
    private UUID id;

    @Column(name = "user_id", nullable = false)
    @JdbcTypeCode(Types.VARCHAR)
    private UUID userId;

    @Column(name = "file_name")
    private String fileName;

    @Column(name = "file_type")
    private Integer fileType;

    @Column(name = "file_size")
    private Long fileSize;

    @Column(name = "url", length = 1000)
    private String url;
}
