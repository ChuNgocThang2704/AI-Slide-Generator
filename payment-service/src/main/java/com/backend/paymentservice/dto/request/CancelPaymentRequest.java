package com.backend.paymentservice.dto.request;

import jakarta.validation.constraints.NotNull;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class CancelPaymentRequest {

    @NotNull(message = "Payment code is required")
    private Long paymentCode;

    private String reason;
}
