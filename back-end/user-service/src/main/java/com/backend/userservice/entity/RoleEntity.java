package com.backend.userservice.entity;

import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.SQLDelete;
import org.hibernate.annotations.Where;

import java.io.Serializable;
import java.util.HashSet;
import java.util.Set;

import lombok.experimental.SuperBuilder;

@Getter
@Setter
@SuperBuilder
@NoArgsConstructor
@AllArgsConstructor
@Entity(name = "roles")
@Where(clause = "is_active = true")
@SQLDelete(sql = "UPDATE roles SET is_active = false WHERE name = ?")
public class RoleEntity extends  AbstractAuditingEntity<String> {
    @Id
    private String name;

    private String description;

    @ManyToMany()
    @JoinTable(name="role_permission",
            joinColumns = @JoinColumn(name="role_name"),
            inverseJoinColumns = @JoinColumn(name="permission_name"))
    private Set<PermissionEntity> permissions = new HashSet<>();
}
