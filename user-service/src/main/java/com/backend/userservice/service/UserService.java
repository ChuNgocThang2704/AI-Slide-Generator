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
    private final RabbitTemplate rabbitTemplate;
    private final StringRedisTemplate redisTemplate;
    private final ObjectMapper objectMapper;
    @Value("${app.rabbitmq.queue:notification_queue}")
    private String notificationQueue;

    public UserResponse createUser(CreateUserRequest createUserRequest) {
        String email = createUserRequest.getEmail() != null ? createUserRequest.getEmail().trim().toLowerCase() : null;
        if (email == null || email.isBlank()) {
            throw new AppException(ErrorCode.EMAIL_IS_REQUIRED);
        }
        if (userRepository.existsByEmail(email)) {
            throw new AppException(ErrorCode.USER_EXISTED);
        }

        UserEntity userEntity = UserEntity.builder()
                .email(email)
                .username(generateUsernameFromEmail(email))
                .build();

        userEntity.setPassword(passwordEncoder.encode(createUserRequest.getPassword()));

        HashSet<RoleEntity> roles = new HashSet<>();
        RoleEntity defaultRole = roleRepository.findById(String.valueOf(RoleEnum.USER_FREE))
                .orElseThrow(() -> new AppException(ErrorCode.ROLE_NOT_FOUND));
        roles.add(defaultRole);
        userEntity.setRoles(roles);
        userEntity.setEmailVerified(false);
        userEntity.setStatus(Status.USER_STATUS.CREATED);

        try {
            userRepository.save(userEntity);
            sendVerificationEmail(userEntity);
        } catch (DataIntegrityViolationException e) {
            throw new AppException(ErrorCode.USER_EXISTED);
        }

        return toUserResponse(userEntity);
    }

    private void sendVerificationEmail(UserEntity userEntity) {
        String verificationCode = String.format("%08d", new java.util.Random().nextInt(100000000));
        String redisKey = "VERIFY_ACCOUNT_" + userEntity.getId() + "_" + verificationCode;
        redisTemplate.opsForValue().set(redisKey, "", 15, TimeUnit.MINUTES);

        Map<String, Object> payload = new HashMap<>();
        payload.put("email", userEntity.getEmail());
        payload.put("code", verificationCode);

        EmailRequest emailRequest = EmailRequest.builder()
                .to(userEntity.getEmail())
                .type("REGISTRATION_VERIFY")
                .payload(payload)
                .build();

        try {
            rabbitTemplate.convertAndSend(notificationQueue, emailRequest);
            log.info("Đã đẩy yêu cầu gửi mail xác nhận cho {} vào hàng đợi", userEntity.getEmail());
        } catch (Exception e) {
            log.error("Lỗi khi đẩy message vào RabbitMQ: ", e);
        }
    }

    public UserResponse getMyInfo() {
        log.info("Fetching current user info");
        var context = SecurityContextHolder.getContext();
        String uuid = context.getAuthentication().getName();

        UserEntity user = userRepository.findById(UUID.fromString(uuid))
                .orElseThrow(() -> new AppException(ErrorCode.USER_NOT_EXISTED));

        return toUserResponse(user);
    }

    public UserResponse updateUser(UUID userId, UpdateUserRequest request) {
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
        UserEntity userEntity = userRepository.findById(userId)
                .orElseThrow(() -> new AppException(ErrorCode.USER_NOT_EXISTED));
        userRepository.delete(userEntity);
    }

    public UserPagination getAllUsers(int page, int size) {
        log.info("Fetching users page {}", page);
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

    private String generateUsernameFromEmail(String email) {
        String base = email != null && email.contains("@")
                ? email.substring(0, email.indexOf('@'))
                : "user";
        String normalizedBase = base.replaceAll("[^a-zA-Z0-9_]", "_");
        String candidate = normalizedBase.isBlank() ? "user" : normalizedBase;
        int suffix = 1;

        while (userRepository.findByUsername(candidate).isPresent()) {
            candidate = normalizedBase + "_" + suffix;
            suffix++;
        }

        return candidate;
    }

    public void verifyCode(VerifyCodeRequest request) {
        String email = request.getEmail().trim().toLowerCase();
        UserEntity user = userRepository.findByEmail(email)
                .orElseThrow(() -> new AppException(ErrorCode.USER_NOT_EXISTED));
        String redisKey = "VERIFY_ACCOUNT_" + user.getId() + "_" + request.getCode();

        Boolean hasKey = redisTemplate.hasKey(redisKey);

        if (!hasKey) {
            log.warn("Xác thực thất bại cho email: {}. Mã không tồn tại hoặc hết hạn.", email);
            throw new AppException(ErrorCode.INVALID_CODE_OR_EXPIRED);
        }

        user.setEmailVerified(true);
        user.setStatus(Status.USER_STATUS.VERIFIED);
        userRepository.save(user);
        redisTemplate.delete(redisKey);

        log.info("Xác thực thành công cho User ID: {}", user.getId());
    }
}
