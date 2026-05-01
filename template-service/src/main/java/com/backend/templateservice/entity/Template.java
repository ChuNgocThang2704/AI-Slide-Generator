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
import java.util.List;
import java.util.UUID;

@Entity
@Table(name = "templates")
@Getter
@Setter
@SuperBuilder
@NoArgsConstructor
@SQLDelete(sql = "UPDATE templates SET is_active = false WHERE id = ?")
@Where(clause = "is_active = true")
public class Template extends AbstractAuditingEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @JdbcTypeCode(Types.VARCHAR)
    private UUID id;

    @Column(nullable = false)
    private String name;

    @Column(columnDefinition = "TEXT")
    private String description;

    @Column(name = "s3_url")
    private String s3Url;

    @Column(name = "num_slides")
    private Integer numSlides;

    @Column(name = "is_premium")
    private Boolean isPremium;

    @ManyToOne
    @JoinColumn(name = "category_id")
    private Category category;

    @OneToMany(mappedBy = "template", cascade = CascadeType.ALL)
    private List<SlideLayout> layouts;

    @OneToMany(mappedBy = "template", cascade = CascadeType.ALL)
    private List<TemplatePreview> previews;
}
