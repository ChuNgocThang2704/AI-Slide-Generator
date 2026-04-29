package com.backend.userservice.controller;

import com.backend.userservice.dto.request.*;
import com.backend.userservice.dto.response.ApiResponse;
import com.backend.userservice.dto.response.AuthenticationResponse;
import com.backend.userservice.dto.response.GoogleAuthUrlResponse;
import com.backend.userservice.dto.response.UserResponse;
import com.backend.userservice.service.AuthenticationService;
import com.backend.userservice.service.UserService;
import jakarta.validation.Valid;
import com.nimbusds.jose.JOSEException;
import jakarta.servlet.http.HttpServletRequest;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.text.ParseException;

@RestController
@RequestMapping(value = "/auth")
@Slf4j
@RequiredArgsConstructor
public class AuthenticationController {
    private final AuthenticationService authenticationService;

    @PostMapping("/login")
    ApiResponse<AuthenticationResponse> authenticate(@RequestBody AuthenticationRequest request) {
        AuthenticationResponse result = authenticationService.authenticate(request);
        return ApiResponse.<AuthenticationResponse>builder().data(result).build();
    }

    @GetMapping("/google/login")
    ApiResponse<GoogleAuthUrlResponse> getGoogleAuthUrl() {
        return ApiResponse.<GoogleAuthUrlResponse>builder()
                .data(authenticationService.getGoogleAuthUrl())
                .build();
    }

    @PostMapping("/google/redirect")
    ApiResponse<AuthenticationResponse> googleRedirect(@RequestBody GoogleAuthenticationRequest request) {
        AuthenticationResponse result = authenticationService.handleGoogleOAuthCode(request.getCode());
        return ApiResponse.<AuthenticationResponse>builder().data(result).build();
    }

    @PostMapping("/register")
    ApiResponse<String> createUser(@RequestBody @Valid CreateUserRequest request) {
        return ApiResponse.<String>builder()
                .data(authenticationService.register(request))
                .build();
    }

    @PostMapping("/verify-code")
    ApiResponse<String> verifyCode(@RequestBody @Valid VerifyCodeRequest request) {
        authenticationService.verifyCode(request);
        return ApiResponse.<String>builder()
                .data("Xác thực tài khoản thành công! Bạn có thể đăng nhập ngay.")
                .build();
    }

    @PostMapping("/refresh")
    ApiResponse<AuthenticationResponse> refresh(@RequestBody CheckTokenRequest request)
            throws ParseException, JOSEException {
        AuthenticationResponse result = authenticationService.refreshToken(request);
        return ApiResponse.<AuthenticationResponse>builder().data(result).build();
    }
    @PostMapping("/logout")
    ApiResponse<Void> logout(HttpServletRequest request) {
        String header = request.getHeader("Authorization");
        if (header != null && header.startsWith("Bearer ")) {
            String token = header.substring(7);
            authenticationService.logout(token);
        }
        return ApiResponse.<Void>builder()
                .message("Logout successfully")
                .build();
    }
}
