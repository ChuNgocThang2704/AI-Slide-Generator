package com.backend.paymentservice.dto.request;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class PaymentRequest {
    
    @NotNull(message = "Amount is required")
    @Min(value = 1000, message = "Minimum amount is 1000 VND")
    private Long amount;

    @NotBlank(message = "Description is required")
    private String description;

    @NotBlank(message = "Return URL is required")
    private String returnUrl;

    @NotBlank(message = "Cancel URL is required")
    private String cancelUrl;
}
