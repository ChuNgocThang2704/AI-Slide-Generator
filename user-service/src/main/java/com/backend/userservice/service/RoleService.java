package com.backend.userservice.service;

import com.backend.userservice.dto.request.RoleRequest;
import com.backend.userservice.dto.response.PermissionResponse;
import com.backend.userservice.dto.response.RoleResponse;
import com.backend.userservice.entity.PermissionEntity;
import com.backend.userservice.entity.RoleEntity;
import com.backend.userservice.repository.PermissionRepository;
import com.backend.userservice.repository.RoleRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
@Slf4j
public class RoleService {
    private final RoleRepository roleRepository;
    private final PermissionRepository permissionRepository;

    public RoleResponse createRole(RoleRequest request) {
        RoleEntity roleEntity = roleRepository.findById(request.getName())
                .orElse(RoleEntity.builder().name(request.getName()).build());

        roleEntity.setDescription(request.getDescription());

        List<PermissionEntity> permissions = permissionRepository.findAllById(request.getPermissions());
        roleEntity.setPermissions(new HashSet<>(permissions));

        roleRepository.save(roleEntity);

        Set<PermissionResponse> permissionResponses = permissions.stream()
                .map(permission -> PermissionResponse.builder()
                        .name(permission.getName())
                        .description(permission.getDescription())
                        .build())
                .collect(Collectors.toSet());

        return RoleResponse.builder()
                .name(roleEntity.getName())
                .description(roleEntity.getDescription())
                .permissions(permissionResponses)
                .build();
    }

    public List<RoleResponse> getAllRoles() {
        return roleRepository.findAll().stream().map(role ->
                RoleResponse.builder()
                        .name(role.getName())
                        .description(role.getDescription())
                        .permissions(role.getPermissions().stream()
                                .map(permission -> PermissionResponse.builder()
                                        .name(permission.getName())
                                        .description(permission.getDescription())
                                        .build())
                                .collect(Collectors.toSet()))
                        .build())
                .collect(Collectors.toList());
    }

    public void deleteRole(String role) {
        roleRepository.deleteById(role);
    }
}
