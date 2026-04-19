package com.backend.documentservice.controller;

import com.backend.documentservice.dto.request.ProjectCreateRequest;
import com.backend.documentservice.dto.response.ApiResponse;
import com.backend.documentservice.dto.response.ProjectResponse;
import com.backend.documentservice.service.ProjectService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.ModelAttribute;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/projects")
@RequiredArgsConstructor
@Slf4j
public class ProjectController {

    private final ProjectService projectService;

    @PostMapping
    public ApiResponse<ProjectResponse> create(@ModelAttribute @Valid ProjectCreateRequest request) {
        UUID ownerId = UUID.fromString(SecurityContextHolder.getContext().getAuthentication().getName());
        request.setOwnerId(ownerId);
        
        return ApiResponse.<ProjectResponse>builder()
                .data(projectService.createProject(request))
                .build();
    }

    @GetMapping
    public ApiResponse<List<ProjectResponse>> getAll() {
        UUID userId = UUID.fromString(SecurityContextHolder.getContext().getAuthentication().getName());
        return ApiResponse.<List<ProjectResponse>>builder()
                .data(projectService.getProjectsByUser(userId))
                .build();
    }

    @GetMapping("/{id}")
    public ApiResponse<ProjectResponse> getById(@PathVariable UUID id) {
        UUID userId = UUID.fromString(SecurityContextHolder.getContext().getAuthentication().getName());
        return ApiResponse.<ProjectResponse>builder()
                .data(projectService.getProjectDetail(id, userId))
                .build();
    }

    @DeleteMapping
    public ApiResponse<String> delete(@RequestBody List<UUID> ids) {
        UUID userId = UUID.fromString(SecurityContextHolder.getContext().getAuthentication().getName());
        projectService.deleteProjects(ids, userId);
        return ApiResponse.<String>builder()
                .data("Projects deleted successfully")
                .build();
    }
}
