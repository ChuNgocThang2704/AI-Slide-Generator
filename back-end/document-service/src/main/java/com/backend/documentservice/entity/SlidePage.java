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
@Table(name = "slide_pages")
@Getter
@Setter
@SuperBuilder
@NoArgsConstructor
@SQLDelete(sql = "UPDATE slide_pages SET is_active = false WHERE id = ?")
@Where(clause = "is_active = true")
public class SlidePage extends AbstractAuditingEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @JdbcTypeCode(Types.VARCHAR)
    private UUID id;

    @Column(name = "project_id", nullable = false)
    @JdbcTypeCode(Types.VARCHAR)
    private UUID projectId;

    @Column(name = "page_index", nullable = false)
    private Integer pageIndex;

    @Column(name = "title")
    private String title;

    @Column(name = "bullets", columnDefinition = "TEXT")
    private String bullets;

    @Column(name = "notes", columnDefinition = "TEXT")
    private String notes;

    @Column(name = "script", columnDefinition = "TEXT")
    private String script;

    @Column(name = "chart", columnDefinition = "TEXT")
    private String chart;

    @Column(name = "table_data", columnDefinition = "TEXT")
    private String table;

    @Column(name = "image_url")
    private String imageUrl;

    @Column(name = "layout")
    private String layout;

    @Column(name = "primary_visual")
    private String primaryVisual;

    @Column(name = "likely_multi_pptx_slides")
    private Boolean likelyMultiPptxSlides;
}
