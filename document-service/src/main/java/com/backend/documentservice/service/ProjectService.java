package com.backend.documentservice.service;

import com.backend.documentservice.dto.request.ProjectCreateRequest;
import com.backend.documentservice.dto.request.ProjectUpdateRequest;
import com.backend.documentservice.dto.response.ProjectResponse;
import com.backend.documentservice.dto.response.PageResponse;
import com.backend.documentservice.entity.AIConfig;
import com.backend.documentservice.entity.Project;
import com.backend.documentservice.entity.SourceDocument;
import com.backend.documentservice.exception.AppException;
import com.backend.documentservice.exception.ErrorCode;
import com.backend.documentservice.dto.response.AITaskLogResponse;
import com.backend.documentservice.dto.response.ProjectExportResponse;
import com.backend.documentservice.entity.AITaskLog;
import com.backend.documentservice.entity.ProjectExport;
import com.backend.documentservice.dto.request.SlidePageUpdateRequest;
import com.backend.documentservice.dto.response.SlidePageResponse;
import com.backend.documentservice.entity.SlidePage;
import com.backend.documentservice.repository.SlidePageRepository;
import com.backend.documentservice.repository.AITaskLogRepository;
import com.backend.documentservice.repository.ProjectExportRepository;
import com.backend.documentservice.mapper.ProjectMapper;
import com.backend.documentservice.repository.AiConfigRepository;
import com.backend.documentservice.repository.ProjectRepository;
import com.backend.documentservice.repository.SourceDocumentRepository;
import com.backend.documentservice.util.Constants;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.cache.annotation.CacheConfig;
import org.springframework.cache.annotation.CacheEvict;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.util.UUID;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
@Slf4j
@CacheConfig(cacheNames = "projects")
public class ProjectService {

    private final ProjectRepository projectRepository;
    private final AiConfigRepository aiConfigRepository;
    private final SourceDocumentRepository sourceDocumentRepository;
    private final AITaskLogRepository aiTaskLogRepository;
    private final ProjectExportRepository projectExportRepository;
    private final SlidePageRepository slidePageRepository;
    private final ProjectMapper projectMapper;

    @Transactional
    @CacheEvict(allEntries = true)
    public ProjectResponse createProject(ProjectCreateRequest request, String userRole) {
        log.info("[document-service] tạo project mới cho user: {}, role: {}", request.getOwnerId(), userRole);

        String fileNameForName = null;

        if (request.getFileUrl() != null && !request.getFileUrl().isBlank()) {
            SourceDocument doc = SourceDocument.builder()
                    .userId(request.getOwnerId())
                    .fileName(request.getFileName())
                    .url(request.getFileUrl())
                    .fileSize(request.getFileSize())
                    .fileType(determineFileType(request.getFileName()))
                    .build();
            doc = sourceDocumentRepository.save(doc);
            request.setSourceDocId(doc.getId());
            fileNameForName = request.getFileName();
        } 

        else if (request.getSourceDocId() != null) {
            SourceDocument doc = sourceDocumentRepository.findById(request.getSourceDocId())
                    .orElseThrow(() -> new AppException(ErrorCode.DOCUMENT_NOT_FOUND));
            
            if (!doc.getUserId().equals(request.getOwnerId())) {
                log.warn("[document-service] user {} sử dụng tài liệu {} của người khác", request.getOwnerId(), request.getSourceDocId());
                throw new AppException(ErrorCode.ACCESS_DENIED);
            }
            fileNameForName = doc.getFileName();
        }

        String generatedName = generateProjectName(request.getPrompt(), fileNameForName);

        log.info("[document-service] lấy config mặc định cho role: {}", userRole);
        UUID configId = aiConfigRepository.findByRoleCode(userRole)
                .map(AIConfig::getId)
                .orElseGet(() -> aiConfigRepository.findByRoleCode(Constants.USER_ROLES.USER_FREE)
                        .map(AIConfig::getId)
                        .orElseThrow(() -> new AppException(ErrorCode.CONFIG_NOT_FOUND)));

        Project project = Project.builder()
                .name(generatedName)
                .ownerId(request.getOwnerId())
                .sourceDocId(request.getSourceDocId())
                .templateId(request.getTemplateId())
                .aiConfigId(configId)
                .initialPrompt(request.getPrompt())
                .status(Constants.PROJECT_STATUS.PROCESSING)
                .build();

        project = projectRepository.save(project);
        log.info("[document-service] lưu project thành công, id: {}, tên: {}", project.getId(), project.getName());

        return projectMapper.toDto(project);
    }

    @Cacheable(key = "#userId.toString() + #search + #page + #size")
    public PageResponse<ProjectResponse> getProjectsByUser(UUID userId, String search, int page, int size) {
        log.info("[document-service] lấy danh sách project phân trang cho user: {}, search: {}, page: {}, size: {}", userId, search, page, size);
        Pageable pageable = PageRequest.of(page, size, Sort.by("createdAt").descending());
        
        Page<Project> projectPage;
        if (search != null && !search.isBlank()) {
            projectPage = projectRepository.findByOwnerIdAndNameContainingIgnoreCase(userId, search, pageable);
        } else {
            projectPage = projectRepository.findByOwnerId(userId, pageable);
        }
        
        return PageResponse.<ProjectResponse>builder()
                .page(projectPage.getNumber())
                .size(projectPage.getSize())
                .totalElements(projectPage.getTotalElements())
                .totalPages(projectPage.getTotalPages())
                .items(projectPage.getContent().stream().map(projectMapper::toDto).collect(Collectors.toList()))
                .build();
    }

    public ProjectResponse getProjectDetail(UUID id, UUID userId) {
        log.info("[document-service] lấy chi tiết project id: {} của user: {}", id, userId);
        Project entity = projectRepository.findById(id)
                .orElseThrow(() -> new AppException(ErrorCode.PROJECT_NOT_FOUND));

        if (!entity.getOwnerId().equals(userId)) {
            throw new AppException(ErrorCode.ACCESS_DENIED);
        }

        return projectMapper.toDto(entity);
    }

    @Transactional
    @CacheEvict(allEntries = true)
    public ProjectResponse updateProject(UUID id, UUID userId, ProjectUpdateRequest request) {
        log.info("[document-service] cập nhật project id: {} cho user: {}", id, userId);
        Project project = projectRepository.findById(id)
                .orElseThrow(() -> new AppException(ErrorCode.PROJECT_NOT_FOUND));

        if (!project.getOwnerId().equals(userId)) {
            throw new AppException(ErrorCode.ACCESS_DENIED);
        }

        if (request.getName() != null) project.setName(request.getName());
        if (request.getStatus() != null) project.setStatus(request.getStatus());
        if (request.getSlideUrl() != null) project.setSlideUrl(request.getSlideUrl());

        project = projectRepository.save(project);
        return projectMapper.toDto(project);
    }

    public List<SlidePageResponse> getSlidePages(UUID projectId, UUID userId) {
        log.info("[document-service] lấy danh sách slide page của project id: {} cho user: {}", projectId, userId);
        getProjectDetail(projectId, userId);
        
        return slidePageRepository.findByProjectIdOrderByPageIndexAsc(projectId).stream()
                .map(page -> SlidePageResponse.builder()
                        .id(page.getId())
                        .projectId(page.getProjectId())
                        .pageIndex(page.getPageIndex())
                        .title(page.getTitle())
                        .content(page.getContent())
                        .imagePrompt(page.getImagePrompt())
                        .imageUrl(page.getImageUrl())
                        .build())
                .collect(Collectors.toList());
    }

    @Transactional
    public SlidePageResponse updateSlidePage(UUID projectId, UUID pageId, UUID userId, SlidePageUpdateRequest request) {
        log.info("[document-service] cập nhật slide page id: {} của project id: {} cho user: {}", pageId, projectId, userId);
        getProjectDetail(projectId, userId);

        SlidePage page = slidePageRepository.findById(pageId)
                .orElseThrow(() -> new AppException(ErrorCode.DOCUMENT_NOT_FOUND));

        if (!page.getProjectId().equals(projectId)) {
            throw new AppException(ErrorCode.ACCESS_DENIED);
        }

        if (request.getTitle() != null) page.setTitle(request.getTitle());
        if (request.getContent() != null) page.setContent(request.getContent());
        if (request.getImagePrompt() != null) page.setImagePrompt(request.getImagePrompt());

        page = slidePageRepository.save(page);
        
        return SlidePageResponse.builder()
                .id(page.getId())
                .projectId(page.getProjectId())
                .pageIndex(page.getPageIndex())
                .title(page.getTitle())
                .content(page.getContent())
                .imagePrompt(page.getImagePrompt())
                .imageUrl(page.getImageUrl())
                .build();
    }

    public List<AITaskLogResponse> getTaskLogs(UUID id, UUID userId) {
        log.info("[document-service] lấy danh sách task log của project id: {} cho user: {}", id, userId);
        getProjectDetail(id, userId);
        
        return aiTaskLogRepository.findByProjectId(id).stream().map(logEntity -> AITaskLogResponse.builder()
                .id(logEntity.getId())
                .projectId(logEntity.getProjectId())
                .taskType(logEntity.getTaskType())
                .status(logEntity.getStatus())
                .errorMessage(logEntity.getErrorMessage())
                .startedAt(logEntity.getStartedAt())
                .completedAt(logEntity.getCompletedAt())
                .createdAt(logEntity.getCreatedAt())
                .build()).collect(Collectors.toList());
    }

    public List<ProjectExportResponse> getExports(UUID id, UUID userId) {
        log.info("[document-service] lấy danh sách export của project id: {} cho user: {}", id, userId);
        getProjectDetail(id, userId);
        
        return projectExportRepository.findByProjectId(id).stream().map(export -> ProjectExportResponse.builder()
                .id(export.getId())
                .projectId(export.getProjectId())
                .exportType(export.getExportType())
                .s3Url(export.getS3Url())
                .createdAt(export.getCreatedAt())
                .build()).collect(Collectors.toList());
    }

    @Transactional
    @CacheEvict(allEntries = true)
    public void deleteProjects(List<UUID> ids, UUID userId) {
        log.info("[document-service] xóa {} project của user: {}", ids.size(), userId);
        List<Project> projects = projectRepository.findAllById(ids);

        for (Project project : projects) {
            if (!project.getOwnerId().equals(userId)) {
                throw new AppException(ErrorCode.ACCESS_DENIED);
            }
        }

        projectRepository.deleteAllById(ids);
        log.info("[document-service] xóa project thành công, ids: {}", ids);
    }

    private String generateProjectName(String prompt, String fileName) {
        if (prompt != null && !prompt.isBlank()) {
            String cleanPrompt = prompt.trim().replaceAll("\\s+", " ");
            if (cleanPrompt.length() > 30) {
                return cleanPrompt.substring(0, 27) + "...";
            }
            return cleanPrompt;
        }

        if (fileName != null && !fileName.isBlank()) {
            return "Slide: " + fileName;
        }

        return "Dự án mới_" + LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyyMMdd_HHmm"));
    }

    private Integer determineFileType(String fileName) {
        if (fileName == null) return Constants.DOCUMENT_TYPE.TEXT_PROMPT;
        String lower = fileName.toLowerCase();
        if (lower.endsWith(".pdf")) return Constants.DOCUMENT_TYPE.PDF;
        if (lower.endsWith(".docx")) return Constants.DOCUMENT_TYPE.DOCX;
        return Constants.DOCUMENT_TYPE.TEXT_PROMPT;
    }
}
