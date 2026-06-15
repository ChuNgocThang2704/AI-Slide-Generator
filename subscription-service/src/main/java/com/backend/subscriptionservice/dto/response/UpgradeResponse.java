package com.backend.subscriptionservice.dto.response;

import lombok.*;
import java.util.UUID;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class UpgradeResponse {
    private UUID subscriptionId;
    private Integer status;
    private String paymentRedirectUrl;
}
