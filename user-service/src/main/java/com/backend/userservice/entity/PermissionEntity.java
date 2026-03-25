package com.backend.userservice.entity;

import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import lombok.*;
import org.hibernate.annotations.SQLDelete;
import org.hibernate.annotations.Where;

@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Entity(name = "permissions")
@Where(clause = "is_active = true")
@SQLDelete(sql = "UPDATE users SET is_active = false WHERE name = ?")
public class PermissionEntity extends AbstractAuditingEntity<String>{
    @Id
    private String name;

    private String description;
}
