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
@Table(name = "layout_placeholders")
@Getter
@Setter
@SuperBuilder
@NoArgsConstructor
@SQLDelete(sql = "UPDATE layout_placeholders SET is_active = false WHERE id = ?")
@Where(clause = "is_active = true")
public class LayoutPlaceholder extends AbstractAuditingEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @JdbcTypeCode(Types.VARCHAR)
    private UUID id;

    @Column(name = "element_type")
    private String elementType; // TEXT, IMAGE

    private Double x;
    private Double y;
    private Double width;
    private Double height;

    @Column(name = "z_index")
    private Integer zIndex;

    @ManyToOne
    @JoinColumn(name = "layout_id")
    private SlideLayout layout;
}
