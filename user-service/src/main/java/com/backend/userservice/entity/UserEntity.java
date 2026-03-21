package com.backend.userservice.entity;

import jakarta.persistence.*;
import lombok.*;

import java.util.Set;

@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Entity(name = "users")
public class UserEntity {
    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private String id;

    @Column(name = "username", unique = true)
    private String username;
    private String password;

    @Column(name = "email", unique = true)
    private String email;

    @Column(name = "status")
    private String status;

    @Column(name = "email_verified", nullable = false)
    private boolean emailVerified;

    @ManyToMany
    @JoinTable(name="user_role",
            joinColumns = @JoinColumn(name="user_id"),
            inverseJoinColumns = @JoinColumn(name="role_name"))
    private Set<RoleEntity> roles;
}

