package com.backend.userservice.dto.request;

import jakarta.validation.constraints.NotBlank;
import lombok.*;

@Data
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class VerifyCodeRequest {
    @NotBlank(message = "EMAIL_IS_REQUIRED")
    private String email;

    @NotBlank(message = "CODE_IS_REQUIRED")
    private String code;
}