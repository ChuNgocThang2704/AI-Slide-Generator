package com.backend.documentservice.service;

import com.backend.documentservice.dto.request.ProjectCreateRequest;
import com.backend.documentservice.dto.response.ProjectResponse;
import com.backend.documentservice.dto.response.SourceDocumentResponse;
import com.backend.documentservice.entity.AiConfig;
import com.backend.documentservice.entity.Project;
import com.backend.documentservice.exception.AppException;
import com.backend.documentservice.exception.ErrorCode;
import com.backend.documentservice.mapper.ProjectMapper;
import com.backend.documentservice.repository.AiConfigRepository;
import com.backend.documentservice.repository.ProjectRepository;
import com.backend.documentservice.repository.SlidePageRepository;
import com.backend.documentservice.util.Constants;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.util.UUID;

@Service
@RequiredArgsConstructor
@Slf4j
public class ProjectService {

    private final ProjectRepository projectRepository;
    private final SourceDocumentService sourceDocumentService;
    private final AiConfigRepository aiConfigRepository;
    private final ProjectMapper projectMapper;

    @Transactional
    public ProjectResponse createProject(ProjectCreateRequest request) {
        log.info("Creating new project for user: {}", request.getOwnerId());

        UUID sourceDocId = null;
        String fileName = null;
        if (request.getFile() != null && !request.getFile().isEmpty()) {
            SourceDocumentResponse doc = sourceDocumentService.saveFileMetadata(request.getOwnerId(), request.getFile());
            sourceDocId = doc.getId();
            fileName = doc.getFileName();
        }

        String generatedName = generateProjectName(request.getPrompt(), fileName);

        UUID configId = request.getAiConfigId();
        if (configId == null) {
            configId = aiConfigRepository.findByRoleCode(Constants.USER_ROLES.USER_FREE)
                    .map(AiConfig::getId)
                    .orElseThrow(() -> new AppException(ErrorCode.CONFIG_NOT_FOUND));
        } else {
            if (!aiConfigRepository.existsById(configId)) {
                throw new AppException(ErrorCode.CONFIG_NOT_FOUND);
            }
        }

        Project project = Project.builder()
                .name(generatedName)
                .ownerId(request.getOwnerId())
                .sourceDocId(sourceDocId)
                .templateId(request.getTemplateId())
                .aiConfigId(configId)
                .initialPrompt(request.getPrompt())
                .status(Constants.PROJECT_STATUS.PROCESSING)
                .build();

        project = projectRepository.save(project);
        
        // TODO: Push to RabbitMQ
        
        return projectMapper.toDto(project);
    }

    public List<ProjectResponse> getProjectsByUser(UUID userId) {
        List<Project> entities = projectRepository.findByOwnerId(userId);
        return projectMapper.toDto(entities);
    }

    public ProjectResponse getProjectDetail(UUID id, UUID userId) {
        Project entity = projectRepository.findById(id)
                .orElseThrow(() -> new AppException(ErrorCode.PROJECT_NOT_FOUND));
        
        if (!entity.getOwnerId().equals(userId)) {
            throw new AppException(ErrorCode.ACCESS_DENIED);
        }
        
        return projectMapper.toDto(entity);
    }

    @Transactional
    public void deleteProjects(List<UUID> ids, UUID userId) {
        List<Project> projects = projectRepository.findAllById(ids);
        
        for (Project project : projects) {
            if (!project.getOwnerId().equals(userId)) {
                throw new AppException(ErrorCode.ACCESS_DENIED);
            }
        }
        
        projectRepository.deleteAllById(ids);
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
}
