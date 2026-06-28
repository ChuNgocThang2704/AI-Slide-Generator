package com.backend.subscriptionservice.dto.response;

import lombok.*;
import java.time.Instant;
import java.util.UUID;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class HistoryResponse {
    private UUID id;
    private UUID userId;
    private Integer action;
    private String previousPackageCode;
    private String newPackageCode;
    private Instant createdAt;
    private String note;
}
