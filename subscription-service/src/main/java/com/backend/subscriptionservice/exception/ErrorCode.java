package com.backend.subscriptionservice.exception;

import org.springframework.http.HttpStatus;
import org.springframework.http.HttpStatusCode;

import lombok.Getter;

@Getter
public enum ErrorCode {
    UNCATEGORIZED_EXCEPTION(1500, "Internal server error", HttpStatus.INTERNAL_SERVER_ERROR),
    UNAUTHENTICATED(1506, "Unauthenticated", HttpStatus.UNAUTHORIZED),
    UNAUTHORIZED(1507, "You do not have permission", HttpStatus.FORBIDDEN),
    PACKAGE_NOT_FOUND(1601, "Subscription package not found", HttpStatus.NOT_FOUND),
    SUBSCRIPTION_NOT_FOUND(1602, "User subscription not found", HttpStatus.NOT_FOUND),
    ACTIVE_SUBSCRIPTION_EXISTS(1603, "Active subscription already exists for this user", HttpStatus.BAD_REQUEST),
    PACKAGE_ALREADY_EXISTS(1604, "Subscription package code already exists", HttpStatus.BAD_REQUEST),
    FEATURE_NOT_FOUND(1605, "Package feature configuration not found", HttpStatus.NOT_FOUND),
    FEATURE_ALREADY_EXISTS(1606, "Package feature configuration already exists for this package", HttpStatus.BAD_REQUEST);

    ErrorCode(int code, String message, HttpStatusCode statusCode) {
        this.code = code;
        this.message = message;
        this.statusCode = statusCode;
    }

    private final int code;
    private final String message;
    private final HttpStatusCode statusCode;
}
