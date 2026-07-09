package com.backend.paymentservice.exception;

import org.springframework.http.HttpStatus;
import org.springframework.http.HttpStatusCode;

import lombok.Getter;

@Getter
public enum ErrorCode {
    UNCATEGORIZED_EXCEPTION(1500, "Internal server error", HttpStatus.INTERNAL_SERVER_ERROR),
    UNAUTHENTICATED(1506, "Unauthenticated", HttpStatus.UNAUTHORIZED),
    UNAUTHORIZED(1507, "You do not have permission", HttpStatus.FORBIDDEN),
    
    PAYMENT_LINK_CREATION_FAILED(1701, "Failed to create payment link with PayOS", HttpStatus.BAD_REQUEST),
    PAYMENT_NOT_FOUND(1702, "Payment order not found or retrieval failed", HttpStatus.NOT_FOUND),
    INVALID_WEBHOOK_SIGNATURE(1703, "Invalid PayOS webhook signature", HttpStatus.BAD_REQUEST),
    PAYMENT_CANCELLATION_FAILED(1704, "Failed to cancel payment link with PayOS", HttpStatus.BAD_REQUEST);

    ErrorCode(int code, String message, HttpStatusCode statusCode) {
        this.code = code;
        this.message = message;
        this.statusCode = statusCode;
    }

    private final int code;
    private final String message;
    private final HttpStatusCode statusCode;
}
