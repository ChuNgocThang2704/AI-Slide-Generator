package com.backend.userservice.entity;

import jakarta.persistence.*;
import lombok.*;

import java.util.Set;

@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Entity(name = "roles")
public class RoleEntity {
    @Id
    private String name;

    private String description;

    @ManyToMany()
    @JoinTable(name="role_permission",
            joinColumns = @JoinColumn(name="role_name"),
            inverseJoinColumns = @JoinColumn(name="permission_name"))
    private Set<PermissionEntity> permissions;
}
