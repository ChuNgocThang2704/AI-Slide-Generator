package com.backend.documentservice.controller;

import com.backend.documentservice.dto.request.ProjectCreateRequest;
import com.backend.documentservice.dto.request.ProjectUpdateRequest;
import com.backend.documentservice.dto.request.SlidePageUpdateRequest;
import com.backend.documentservice.dto.response.ApiResponse;
import com.backend.documentservice.dto.response.AITaskLogResponse;
import com.backend.documentservice.dto.response.ProjectExportResponse;
import com.backend.documentservice.dto.response.ProjectResponse;
import com.backend.documentservice.dto.response.SlidePageResponse;
import com.backend.documentservice.dto.response.SourceDocumentResponse;
import com.backend.documentservice.dto.response.PageResponse;
import com.backend.documentservice.service.ProjectService;
import com.backend.documentservice.service.SourceDocumentService;
import com.backend.documentservice.util.Constants;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;
import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping
@RequiredArgsConstructor
@Slf4j
public class DocumentController {

    private final ProjectService projectService;
    private final SourceDocumentService sourceDocumentService;

    private UUID currentUserId() {
        return UUID.fromString(SecurityContextHolder.getContext().getAuthentication().getName());
    }

    private String currentUserRole() {
        return SecurityContextHolder.getContext().getAuthentication().getAuthorities().stream()
                .map(GrantedAuthority::getAuthority)
                .map(role -> role.startsWith("ROLE_") ? role.substring(5) : role)
                .findFirst()
                .orElse(Constants.USER_ROLES.USER_FREE);
    }

    @PostMapping("/projects")
    public ApiResponse<ProjectResponse> createProject(@RequestBody @Valid ProjectCreateRequest request) {
        request.setOwnerId(currentUserId());
        return ApiResponse.<ProjectResponse>builder()
                .data(projectService.createProject(request, currentUserRole()))
                .build();
    }

    @GetMapping("/projects")
    public ApiResponse<PageResponse<ProjectResponse>> getAllProjects(
            @RequestParam(required = false) String search,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "10") int size
    ) {
        return ApiResponse.<PageResponse<ProjectResponse>>builder()
                .data(projectService.getProjectsByUser(currentUserId(), search, page, size))
                .build();
    }

    @GetMapping("/projects/{id}")
    public ApiResponse<ProjectResponse> getProjectById(@PathVariable UUID id) {
        return ApiResponse.<ProjectResponse>builder()
                .data(projectService.getProjectDetail(id, currentUserId()))
                .build();
    }

    @PostMapping("/projects/{id}")
    public ApiResponse<ProjectResponse> updateProject(@PathVariable UUID id, @RequestBody ProjectUpdateRequest request) {
        return ApiResponse.<ProjectResponse>builder()
                .data(projectService.updateProject(id, currentUserId(), request))
                .build();
    }

    @GetMapping("/projects/{id}/pages")
    public ApiResponse<List<SlidePageResponse>> getSlidePages(@PathVariable UUID id) {
        return ApiResponse.<List<SlidePageResponse>>builder()
                .data(projectService.getSlidePages(id, currentUserId()))
                .build();
    }

    @PostMapping("/projects/{projectId}/pages/{pageId}")
    public ApiResponse<SlidePageResponse> updateSlidePage(
            @PathVariable UUID projectId,
            @PathVariable UUID pageId,
            @RequestBody SlidePageUpdateRequest request) {
        return ApiResponse.<SlidePageResponse>builder()
                .data(projectService.updateSlidePage(projectId, pageId, currentUserId(), request))
                .build();
    }

    @GetMapping("/projects/{id}/task-logs")
    public ApiResponse<List<AITaskLogResponse>> getProjectTaskLogs(@PathVariable UUID id) {
        return ApiResponse.<List<AITaskLogResponse>>builder()
                .data(projectService.getTaskLogs(id, currentUserId()))
                .build();
    }

    @GetMapping("/projects/{id}/exports")
    public ApiResponse<List<ProjectExportResponse>> getProjectExports(@PathVariable UUID id) {
        return ApiResponse.<List<ProjectExportResponse>>builder()
                .data(projectService.getExports(id, currentUserId()))
                .build();
    }

    @DeleteMapping("/projects")
    public ApiResponse<String> deleteProjects(@RequestBody List<UUID> ids) {
        projectService.deleteProjects(ids, currentUserId());
        return ApiResponse.<String>builder()
                .data("Projects deleted successfully")
                .build();
    }

    @PostMapping(value = "/source-documents/upload", consumes = "multipart/form-data")
    public ApiResponse<Map<String, Object>> uploadFile(@RequestParam("file") MultipartFile file) {
        return ApiResponse.<Map<String, Object>>builder()
                .data(sourceDocumentService.uploadFileOnly(currentUserId(), file))
                .build();
    }

    @GetMapping("/source-documents")
    public ApiResponse<PageResponse<SourceDocumentResponse>> getAllDocuments(
            @RequestParam(required = false) String search,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "10") int size
    ) {
        return ApiResponse.<PageResponse<SourceDocumentResponse>>builder()
                .data(sourceDocumentService.getDocumentsByUser(currentUserId(), search, page, size))
                .build();
    }

    @GetMapping("/source-documents/{id}")
    public ApiResponse<SourceDocumentResponse> getDocumentById(@PathVariable UUID id) {
        return ApiResponse.<SourceDocumentResponse>builder()
                .data(sourceDocumentService.getDocument(id, currentUserId()))
                .build();
    }

    @GetMapping("/source-documents/{id}/view")
    public ApiResponse<String> getPresignedViewUrl(@PathVariable UUID id) {
        return ApiResponse.<String>builder()
                .data(sourceDocumentService.generatePresignedViewUrl(id, currentUserId()))
                .build();
    }

    @DeleteMapping("/source-documents")
    public ApiResponse<String> deleteDocuments(@RequestBody List<UUID> ids) {
        sourceDocumentService.deleteDocuments(ids, currentUserId());
        return ApiResponse.<String>builder()
                .data("Documents deleted successfully")
                .build();
    }
}
