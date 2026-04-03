package com.backend.userservice.dto.response;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDate;
import java.util.UUID;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class UserProfileResponse {
    private UUID userId;
    private String fullName;
    private String avatarUrl;
    private LocalDate dateOfBirth;
    private String phoneNumber;
}
