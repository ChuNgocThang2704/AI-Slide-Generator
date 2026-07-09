package com.backend.subscriptionservice.dto.response;

import lombok.*;
import java.time.LocalDateTime;
import java.util.UUID;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class UserSubscriptionResponse {
    private UUID id;
    private UUID userId;
    private String packageCode;
    private String packageName;
    private LocalDateTime startDate;
    private LocalDateTime expireDate;
    private Integer status;
}
