package com.backend.userservice.controller;

import com.backend.userservice.dto.request.CheckTokenRequest;
import com.backend.userservice.dto.request.UpdateUserRequest;
import com.backend.userservice.dto.response.ApiResponse;
import com.backend.userservice.dto.response.AuthenticationResponse;
import com.backend.userservice.dto.response.UserPagination;
import com.backend.userservice.dto.response.UserResponse;
import com.backend.userservice.service.AuthenticationService;
import com.backend.userservice.service.UserService;
import com.nimbusds.jose.JOSEException;
import jakarta.validation.Valid;
import java.text.ParseException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

import java.util.UUID;

@RestController
@RequestMapping(value = "/users")
@Slf4j
@RequiredArgsConstructor
public class UserController {
    private final UserService userService;

    @GetMapping
    ApiResponse<UserPagination> getUsers(@RequestParam(defaultValue = "0", required = false) int page,
                                         @RequestParam(defaultValue = "10", required = false) int size) {
        return ApiResponse.<UserPagination>builder()
                .data(userService.getAllUsers(page, size))
                .build();
    }

    @GetMapping("/{userId}")
    ApiResponse<UserResponse> getUser(@PathVariable("userId") String userId) {
        return ApiResponse.<UserResponse>builder()
                .data(userService.getUser(userId))
                .build();
    }

    @GetMapping("/my-info")
    ApiResponse<UserResponse> getMyInfo() {
        return ApiResponse.<UserResponse>builder()
                .data(userService.getMyInfo())
                .build();
    }

    @DeleteMapping("/{userId}")
    ApiResponse<String> deleteUser(@PathVariable String userId) {
        userService.deleteUser(UUID.fromString(userId));
        return ApiResponse.<String>builder().data("User has been deleted").build();
    }

    @PostMapping("/{userId}")
    ApiResponse<UserResponse> updateUser(@PathVariable String userId, @RequestBody UpdateUserRequest request) {
        return ApiResponse.<UserResponse>builder()
                .data(userService.updateUser(UUID.fromString(userId), request))
                .build();
    }
}
