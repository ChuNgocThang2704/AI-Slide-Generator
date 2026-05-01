package com.backend.templateservice.entity;

import jakarta.persistence.*;
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
@Table(name = "template_previews")
@Getter
@Setter
@SuperBuilder
@NoArgsConstructor
@SQLDelete(sql = "UPDATE template_previews SET is_active = false WHERE id = ?")
@Where(clause = "is_active = true")
public class TemplatePreview extends AbstractAuditingEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @JdbcTypeCode(Types.VARCHAR)
    private UUID id;

    @Column(name = "image_url")
    private String imageUrl;

    @Column(name = "page_index")
    private Integer pageIndex;

    @ManyToOne
    @JoinColumn(name = "template_id")
    private Template template;
}
