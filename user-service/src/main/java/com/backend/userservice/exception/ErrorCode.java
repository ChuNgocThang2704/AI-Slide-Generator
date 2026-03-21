package com.backend.userservice.exception;

import org.springframework.http.HttpStatus;
import org.springframework.http.HttpStatusCode;

import lombok.Getter;

@Getter
public enum ErrorCode {
    UNCATEGORIZED_EXCEPTION(1500, "Uncategorized error", HttpStatus.INTERNAL_SERVER_ERROR),
    ROLE_NOT_FOUND(1501, "Role not found", HttpStatus.BAD_REQUEST),
    USER_EXISTED(1502, "User existed", HttpStatus.BAD_REQUEST),
    USERNAME_OR_PASSWORD_INCORRECT(1503, "Username or password incorrect", HttpStatus.BAD_REQUEST),
    USER_NOT_EXISTED(1505, "User not existed", HttpStatus.NOT_FOUND),
    UNAUTHENTICATED(1506, "Unauthenticated", HttpStatus.UNAUTHORIZED),
    UNAUTHORIZED(1507, "You do not have permission", HttpStatus.FORBIDDEN),
    INVALID_DOB(1508, "Your age must be at least {min}", HttpStatus.BAD_REQUEST),
    INVALID_EMAIL(1509, "Invalid email address", HttpStatus.BAD_REQUEST),
    EMAIL_IS_REQUIRED(1509, "Email is required", HttpStatus.BAD_REQUEST),
    USER_IS_NOT_ACTIVE(1510, "User is inactive", HttpStatus.BAD_REQUEST),
    ;

    ErrorCode(int code, String message, HttpStatusCode statusCode) {
        this.code = code;
        this.message = message;
        this.statusCode = statusCode;
    }

    private final int code;
    private final String message;
    private final HttpStatusCode statusCode;
}
