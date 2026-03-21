package com.backend.userservice.service;

import com.backend.userservice.constant.RoleEnum;
import com.backend.userservice.dto.request.CreateUserRequest;
import com.backend.userservice.dto.request.UpdateUserRequest;
import com.backend.userservice.dto.response.UserPagination;
import com.backend.userservice.dto.response.UserResponse;
import com.backend.userservice.entity.RoleEntity;
import com.backend.userservice.entity.UserEntity;
import com.backend.userservice.exception.AppException;
import com.backend.userservice.exception.ErrorCode;
import com.backend.userservice.repository.RoleRepository;
import com.backend.userservice.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.modelmapper.ModelMapper;
import org.springframework.dao.DataIntegrityViolationException;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

import java.util.HashSet;
import java.util.List;


@Service
@Slf4j
@RequiredArgsConstructor
public class UserService {
    private final UserRepository userRepository;
    private final ModelMapper modelMapper;
    private final PasswordEncoder passwordEncoder;
    private final RoleRepository roleRepository;

    public UserResponse createUser(CreateUserRequest createUserRequest){
        UserEntity userEntity = modelMapper.map(createUserRequest, UserEntity.class);
        userEntity.setPassword(passwordEncoder.encode(createUserRequest.getPassword()));

        HashSet<RoleEntity> roles = new HashSet<>();
        roleRepository.findById(String.valueOf(RoleEnum.USER)).ifPresent(roles::add);

        userEntity.setRoles(roles);
        userEntity.setEmailVerified(false);
        userEntity.setStatus("active");
        try {
            userRepository.save(userEntity);
        } catch (DataIntegrityViolationException e) {
            throw new AppException(ErrorCode.USER_EXISTED);
        }



//        var profileRequest = profileMapper.toProfileCreationRequest(request);
//        profileRequest.setUserId(user.getId());
//
//        var profile = profileClient.createProfile(profileRequest);
//
//        NotificationEvent notificationEvent = NotificationEvent.builder()
//                .channel("EMAIL")
//                .recipient(request.getEmail())
//                .subject("Welcome to bookteria")
//                .body("Hello, " + request.getUsername())
//                .build();
//
//        // Publish message to kafka
//        kafkaTemplate.send("notification-delivery", notificationEvent);
        UserResponse userResponse = modelMapper.map(userEntity, UserResponse.class);
        userResponse.setId(userEntity.getId());

        return userResponse;
    }

    public UserResponse getMyInfo() {
        log.info("In method get User is using");
        var context = SecurityContextHolder.getContext();
        String name = context.getAuthentication().getName();

        UserEntity user = userRepository.findByUsername(name).orElseThrow(() -> new AppException(ErrorCode.USER_NOT_EXISTED));

        return modelMapper.map(user, UserResponse.class);
    }

    @PreAuthorize("hasRole('ADMIN')")
    public UserResponse updateUser(String userId, UpdateUserRequest request) {
        UserEntity user = userRepository.findById(userId).orElseThrow(() -> new AppException(ErrorCode.USER_NOT_EXISTED));

        UserEntity updatedUser = modelMapper.map(request, UserEntity.class);
        updatedUser.setId(user.getId());
        updatedUser.setStatus(user.getStatus());
        updatedUser.setEmail(user.getEmail());
        updatedUser.setRoles(user.getRoles());
        updatedUser.setUsername(user.getUsername());
        updatedUser.setPassword(passwordEncoder.encode(request.getPassword()));

        List<RoleEntity> roles = roleRepository.findAllById(request.getRoles());
        updatedUser.setRoles(new HashSet<>(roles));

        userRepository.save(updatedUser);

        return modelMapper.map(updatedUser,UserResponse.class);
    }

    @PreAuthorize("hasRole('ADMIN')")
    public void deleteUser(String userId) {
        UserEntity userEntity = userRepository.findById(userId).orElseThrow(() -> new AppException(ErrorCode.USER_NOT_EXISTED));
        userEntity.setStatus("inactive");
        userRepository.save(userEntity);
    }

    @PreAuthorize("hasAuthority('ALL_PERMISSION')")
    public UserPagination getAllUsers(int page, int size) {
        log.info("In method get all Users");
        Pageable pageable = PageRequest.of(page,size, Sort.by("username").ascending());

        Page<UserResponse> result = userRepository.findAll(pageable).map(user -> modelMapper.map(user, UserResponse.class));
        return UserPagination.builder()
                .content(result.getContent())
                .page(result.getNumber())
                .size(result.getSize())
                .totalElements(result.getTotalElements())
                .totalPages(result.getTotalPages())
                .build();
    }

    @PreAuthorize("hasRole('ADMIN')")
    public UserResponse getUser(String id) {
        return modelMapper.map(
                userRepository.findById(id).orElseThrow(() -> new AppException(ErrorCode.USER_NOT_EXISTED)), UserResponse.class);
    }
}
