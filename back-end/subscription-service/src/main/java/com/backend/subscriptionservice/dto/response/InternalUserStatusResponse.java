package com.backend.subscriptionservice.dto.response;

import lombok.*;
import java.time.LocalDateTime;
import java.util.UUID;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class InternalUserStatusResponse {
    private UUID userId;
    private String packageCode;
    private String roleName;
    private Integer status;
    private LocalDateTime expireDate;
}
