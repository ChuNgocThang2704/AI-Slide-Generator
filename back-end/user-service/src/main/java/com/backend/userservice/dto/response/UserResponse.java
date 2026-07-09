package com.backend.userservice.dto.response;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.Instant;
import java.util.Set;
import java.util.UUID;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class UserResponse {
    private UUID id;
    private String username;
    private String email;
    private Integer status;
    private boolean emailVerified;
    private Instant lastLoginAt;
    private UserProfileResponse profile;
    private Set<RoleResponse> roles;
    private Instant createdAt;
}
