package com.backend.documentservice.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Index;
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

/**
 * A set of lecture scripts written in one go (the videos of a chapter): what becomes one Excel
 * workbook with a sheet per deck. The decks themselves are not kept, only the text read from
 * them and the scripts.
 */
@Entity
@Table(name = "script_sets", indexes = @Index(name = "idx_script_sets_user", columnList = "user_id, updated_at"))
@Getter
@Setter
@SuperBuilder
@NoArgsConstructor
@SQLDelete(sql = "UPDATE script_sets SET is_active = false WHERE id = ?")
@Where(clause = "is_active = true")
public class ScriptSet extends AbstractAuditingEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @JdbcTypeCode(Types.VARCHAR)
    private UUID id;

    @Column(name = "user_id", nullable = false)
    @JdbcTypeCode(Types.VARCHAR)
    private UUID userId;

    @Column(name = "name", nullable = false, length = 200)
    private String name;

    @Column(name = "prompt", columnDefinition = "TEXT")
    private String prompt;

    @Column(name = "item_count")
    private Integer itemCount;

    @Column(name = "total_words")
    private Integer totalWords;

    @Column(name = "total_minutes")
    private Integer totalMinutes;

    /** JSON array of the scripts: [{id, fileName, sheet, title, rows, slides, missing}]. */
    @Column(name = "content", columnDefinition = "LONGTEXT")
    private String content;
}
