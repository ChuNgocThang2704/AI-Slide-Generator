package com.backend.userservice.service;

import com.backend.userservice.constant.RoleEnum;
import com.backend.userservice.constant.Status;
import com.backend.userservice.dto.request.CreateUserRequest;
import com.backend.userservice.dto.request.EmailRequest;
import com.backend.userservice.dto.request.UpdateUserRequest;
import com.backend.userservice.dto.request.VerifyCodeRequest;
import com.backend.userservice.dto.response.RoleResponse;
import com.backend.userservice.dto.response.UserPagination;
import com.backend.userservice.dto.response.UserProfileResponse;
import com.backend.userservice.dto.response.UserResponse;
import com.backend.userservice.entity.RoleEntity;
import com.backend.userservice.entity.UserEntity;
import com.backend.userservice.entity.UserProfileEntity;
import com.backend.userservice.exception.AppException;
import com.backend.userservice.exception.ErrorCode;
import com.backend.userservice.repository.RoleRepository;
import com.backend.userservice.repository.UserProfileRepository;
import com.backend.userservice.repository.UserRepository;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.TimeUnit;
import java.util.stream.Collectors;

import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

@Service
@Slf4j
@RequiredArgsConstructor
public class UserService {
    private final UserRepository userRepository;
    private final UserProfileRepository userProfileRepository;
    private final PasswordEncoder passwordEncoder;
    private final RoleRepository roleRepository;
    private final StringRedisTemplate redisTemplate;

    public UserResponse getMyInfo() {
        String uuid = SecurityContextHolder.getContext().getAuthentication().getName();
        log.info("[user-service] lấy thông tin cá nhân của user: {}", uuid);
        UserEntity user = userRepository.findById(UUID.fromString(uuid))
                .orElseThrow(() -> new AppException(ErrorCode.USER_NOT_EXISTED));
        return toUserResponse(user);
    }

    public UserResponse updateUser(UUID userId, UpdateUserRequest request) {
        log.info("[user-service] cập nhật thông tin user: {}", userId);
        UserEntity user = userRepository.findById(userId)
                .orElseThrow(() -> new AppException(ErrorCode.USER_NOT_EXISTED));

        UserProfileEntity profile = user.getProfile();
        if (profile == null) {
            profile = UserProfileEntity.builder().build();
            user.setProfile(profile);
        }

        if (request.getDateOfBirth() != null) {
            profile.setDateOfBirth(request.getDateOfBirth());
        }
        if (request.getPassword() != null && !request.getPassword().isEmpty()) {
            user.setPassword(passwordEncoder.encode(request.getPassword()));
        }
        if (request.getFullName() != null) {
            profile.setFullName(request.getFullName());
        }
        if (request.getAvatarUrl() != null) {
            profile.setAvatarUrl(request.getAvatarUrl());
        }
        if (request.getPhoneNumber() != null) {
            profile.setPhoneNumber(request.getPhoneNumber());
        }
        if (request.getRoles() != null && !request.getRoles().isEmpty()) {
            List<RoleEntity> roles = roleRepository.findAllById(request.getRoles());
            user.setRoles(new HashSet<>(roles));
        }

        UserEntity savedUser = userRepository.save(user);
        if (savedUser.getProfile() != null) {
            userProfileRepository.save(savedUser.getProfile());
        }
        return toUserResponse(savedUser);
    }

    public void deleteUser(UUID userId) {
        log.info("[user-service] xóa user: {}", userId);
        UserEntity userEntity = userRepository.findById(userId)
                .orElseThrow(() -> new AppException(ErrorCode.USER_NOT_EXISTED));
        userRepository.delete(userEntity);
        log.info("[user-service] xóa user thành công: {}", userId);
    }

    public UserPagination getAllUsers(int page, int size) {
        log.info("[user-service] lấy danh sách user, trang: {}, kích thước: {}", page, size);
        Pageable pageable = PageRequest.of(page, size, Sort.by("username").ascending());

        Page<UserResponse> result = userRepository.findAll(pageable).map(this::toUserResponse);

        return UserPagination.builder()
                .content(result.getContent())
                .page(result.getNumber())
                .size(result.getSize())
                .totalElements(result.getTotalElements())
                .totalPages(result.getTotalPages())
                .build();
    }

    public UserResponse getUser(String id) {
        log.info("[user-service] lấy thông tin user theo id: {}", id);
        UserEntity userEntity = userRepository.findById(UUID.fromString(id))
                .orElseThrow(() -> new AppException(ErrorCode.USER_NOT_EXISTED));
        return toUserResponse(userEntity);
    }

    private UserResponse toUserResponse(UserEntity userEntity) {
        return UserResponse.builder()
                .id(userEntity.getId())
                .username(userEntity.getUsername())
                .email(userEntity.getEmail())
                .status(userEntity.getStatus())
                .emailVerified(userEntity.isEmailVerified())
                .lastLoginAt(userEntity.getLastLoginAt())
                .profile(toUserProfileResponse(userEntity.getProfile()))
                .roles(mapRoles(userEntity.getRoles()))
                .createdAt(userEntity.getCreatedAt())
                .build();
    }

    private UserProfileResponse toUserProfileResponse(UserProfileEntity profileEntity) {
        if (profileEntity == null) {
            return null;
        }
        return UserProfileResponse.builder()
                .userId(profileEntity.getUserId())
                .fullName(profileEntity.getFullName())
                .avatarUrl(profileEntity.getAvatarUrl())
                .dateOfBirth(profileEntity.getDateOfBirth())
                .phoneNumber(profileEntity.getPhoneNumber())
                .build();
    }

    private Set<RoleResponse> mapRoles(Set<RoleEntity> roles) {
        return roles.stream()
                .map(role -> RoleResponse.builder()
                        .name(role.getName())
                        .description(role.getDescription())
                        .build())
                .collect(Collectors.toSet());
    }
}
