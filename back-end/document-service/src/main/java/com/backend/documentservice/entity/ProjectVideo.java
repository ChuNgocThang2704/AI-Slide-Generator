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
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.annotations.SQLDelete;
import org.hibernate.annotations.Where;

import java.sql.Types;
import java.util.UUID;

@Entity
@Table(name = "project_videos")
@Getter
@Setter
@SuperBuilder
@NoArgsConstructor
@SQLDelete(sql = "UPDATE project_videos SET is_active = false WHERE id = ?")
@Where(clause = "is_active = true")
public class ProjectVideo extends AbstractAuditingEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @JdbcTypeCode(Types.VARCHAR)
    private UUID id;

    @Column(name = "project_id", nullable = false)
    @JdbcTypeCode(Types.VARCHAR)
    private UUID projectId;

    @Column(name = "phase", length = 32)
    private String phase;

    @Column(name = "status_text", length = 500)
    private String status;

    @Column(name = "progress")
    private Integer progress;

    @Column(name = "current_slide")
    private Integer currentSlide;

    @Column(name = "total_slides")
    private Integer totalSlides;

    @Column(name = "video_url", columnDefinition = "TEXT")
    private String videoUrl;

    @Column(name = "temporary_video_url", columnDefinition = "TEXT")
    private String temporaryVideoUrl;

    @Column(name = "error_message", columnDefinition = "TEXT")
    private String error;
}
