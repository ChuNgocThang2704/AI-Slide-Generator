package com.backend.paymentservice.exception;

import lombok.Getter;

@Getter
public class AppException extends RuntimeException {
    private final ErrorCode errorCode;
    private final String customMessage;

    public AppException(ErrorCode errorCode) {
        super(errorCode.getMessage());
        this.errorCode = errorCode;
        this.customMessage = null;
    }

    public AppException(ErrorCode errorCode, String customMessage) {
        super(customMessage != null ? customMessage : errorCode.getMessage());
        this.errorCode = errorCode;
        this.customMessage = customMessage;
    }
}
