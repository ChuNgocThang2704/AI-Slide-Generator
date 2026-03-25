package com.backend.userservice.service;

import com.backend.userservice.constant.RoleEnum;
import com.backend.userservice.dto.request.CreateUserRequest;
import com.backend.userservice.dto.request.UpdateUserRequest;
import com.backend.userservice.dto.response.RoleResponse;
import com.backend.userservice.dto.response.UserPagination;
import com.backend.userservice.dto.response.UserResponse;
import com.backend.userservice.entity.RoleEntity;
import com.backend.userservice.entity.UserEntity;
import com.backend.userservice.exception.AppException;
import com.backend.userservice.exception.ErrorCode;
import com.backend.userservice.repository.RoleRepository;
import com.backend.userservice.repository.UserRepository;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.UUID;
import java.util.stream.Collectors;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

@Service
@Slf4j
@RequiredArgsConstructor
public class UserService {
    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final RoleRepository roleRepository;

    public UserResponse createUser(CreateUserRequest createUserRequest) {
        UserEntity userEntity = UserEntity.builder()
                .username(createUserRequest.getUsername())
                .email(createUserRequest.getEmail())
                .dayOfBirth(createUserRequest.getDayOfBirth())
                .build();

        userEntity.setPassword(passwordEncoder.encode(createUserRequest.getPassword()));

        HashSet<RoleEntity> roles = new HashSet<>();
        RoleEntity defaultRole = roleRepository.findById(String.valueOf(RoleEnum.USER))
                .orElseThrow(() -> new AppException(ErrorCode.ROLE_NOT_FOUND));
        roles.add(defaultRole);
        userEntity.setRoles(roles);
        userEntity.setEmailVerified(false);
        userEntity.setStatus("active");

        try {
            userRepository.save(userEntity);
        } catch (DataIntegrityViolationException e) {
            throw new AppException(ErrorCode.USER_EXISTED);
        }

        return toUserResponse(userEntity);
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

        if (request.getDayOfBirth() != null) {
            user.setDayOfBirth(request.getDayOfBirth());
        }
        if (request.getPassword() != null && !request.getPassword().isEmpty()) {
            user.setPassword(passwordEncoder.encode(request.getPassword()));
        }
        if (request.getRoles() != null && !request.getRoles().isEmpty()) {
            List<RoleEntity> roles = roleRepository.findAllById(request.getRoles());
            user.setRoles(new HashSet<>(roles));
        }

        return toUserResponse(userRepository.save(user));
    }

    public void deleteUser(UUID userId) {
        UserEntity userEntity = userRepository.findById(userId)
                .orElseThrow(() -> new AppException(ErrorCode.USER_NOT_EXISTED));
        userEntity.setStatus("inactive");
        userRepository.save(userEntity);
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
                .dayOfBirth(userEntity.getDayOfBirth())
                .emailVerified(userEntity.isEmailVerified())
                .roles(mapRoles(userEntity.getRoles()))
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
