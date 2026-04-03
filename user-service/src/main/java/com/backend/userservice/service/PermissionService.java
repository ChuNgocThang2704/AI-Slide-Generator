package com.backend.userservice.service;

import com.backend.userservice.dto.request.PermissionRequest;
import com.backend.userservice.dto.response.PermissionResponse;
import com.backend.userservice.entity.PermissionEntity;
import com.backend.userservice.repository.PermissionRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
@Slf4j
public class PermissionService {
    private final PermissionRepository permissionRepository;

    public PermissionResponse createPermission(PermissionRequest request) {
        PermissionEntity permission = permissionRepository.findById(request.getName())
                .orElse(PermissionEntity.builder().name(request.getName()).build());

        permission.setDescription(request.getDescription());
        permissionRepository.save(permission);

        return PermissionResponse.builder()
                .name(permission.getName())
                .description(permission.getDescription())
                .build();
    }

    public List<PermissionResponse> getAllPermissions() {
        var permissions = permissionRepository.findAll();
        return permissions.stream().map(permission ->
                PermissionResponse.builder()
                        .name(permission.getName())
                        .description(permission.getDescription())
                        .build())
                .collect(Collectors.toList());
    }

    public void deletePermission(String permission) {
        permissionRepository.deleteById(permission);
    }
}
