package com.backend.userservice.service;

import com.backend.userservice.dto.request.RoleRequest;
import com.backend.userservice.dto.response.RoleResponse;
import com.backend.userservice.entity.PermissionEntity;
import com.backend.userservice.entity.RoleEntity;
import com.backend.userservice.repository.PermissionRepository;
import com.backend.userservice.repository.RoleRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.modelmapper.ModelMapper;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.stereotype.Service;

import java.util.HashSet;
import java.util.List;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
@Slf4j
public class RoleService {
    private final RoleRepository roleRepository;
    private final PermissionRepository permissionRepository;
    private final ModelMapper modelMapper;

    @PreAuthorize("hasRole('ADMIN')")
    public RoleResponse createRole(RoleRequest request) {
        RoleEntity roleEntity = modelMapper.map(request,RoleEntity.class);

        List<PermissionEntity> permissions = permissionRepository.findAllById(request.getPermissions());
        roleEntity.setPermissions(new HashSet<>(permissions));

        roleRepository.save(roleEntity);
        return modelMapper.map(roleEntity,RoleResponse.class);
    }

    @PreAuthorize("hasRole('ADMIN')")
    public List<RoleResponse> getAllRoles() {
        return roleRepository.findAll().stream().map(role ->
                modelMapper.map(role,RoleResponse.class))
                .collect(Collectors.toList());
    }

    @PreAuthorize("hasRole('ADMIN')")
    public void deleteRole(String role) {
        roleRepository.deleteById(role);
    }
}
