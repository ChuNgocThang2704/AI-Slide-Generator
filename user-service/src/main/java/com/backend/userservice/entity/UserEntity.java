package com.backend.userservice.entity;

import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.SQLDelete;
import org.hibernate.annotations.Where;

import java.time.LocalDate;
import java.util.HashSet;
import java.util.Set;
import java.util.UUID;

@Entity(name = "users")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
@Where(clause = "is_active = true")
@SQLDelete(sql = "UPDATE users SET is_active = false WHERE id = ?")
public class UserEntity extends AbstractAuditingEntity<UUID> {
    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id ;

    @Column(name = "username", unique = true)
    private String username;

    @Column(name = "password")
    private String password;

    @Column(name = "email", unique = true)
    private String email;

    @Column(name = "dayOfBirth")
    private LocalDate dayOfBirth;

    @Column(name = "status")
    private String status;

    @Column(name = "email_verified", nullable = false)
    private boolean emailVerified;

    @ManyToMany
    @JoinTable(name="user_roles",
            joinColumns = @JoinColumn(name="user_id"),
            inverseJoinColumns = @JoinColumn(name="role_name"))
    private Set<RoleEntity> roles = new HashSet<>();
}

