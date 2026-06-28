package com.backend.documentservice.service;

import com.backend.documentservice.dto.request.ProjectCreateRequest;
import com.backend.documentservice.dto.request.ProjectUpdateRequest;
import com.backend.documentservice.dto.response.ProjectResponse;
import com.backend.documentservice.dto.response.ProjectProgressResponse;
import com.backend.documentservice.dto.response.PageResponse;
import com.backend.documentservice.entity.Project;
import com.backend.documentservice.entity.SourceDocument;
import com.backend.documentservice.exception.AppException;
import com.backend.documentservice.exception.ErrorCode;
import com.backend.documentservice.dto.response.AITaskLogResponse;
import com.backend.documentservice.dto.response.ProjectExportResponse;
import com.backend.documentservice.entity.AITaskLog;
import com.backend.documentservice.dto.request.SlidePageUpdateRequest;
import com.backend.documentservice.dto.response.SlidePageResponse;
import com.backend.documentservice.entity.SlidePage;
import com.backend.documentservice.repository.SlidePageRepository;
import com.backend.documentservice.repository.AITaskLogRepository;
import com.backend.documentservice.repository.ProjectExportRepository;
import com.backend.documentservice.client.SubscriptionClient;
import com.backend.documentservice.dto.request.InternalQuotaRequest;
import com.backend.documentservice.dto.response.ApiResponse;
import com.backend.documentservice.dto.response.QuotaCheckResponse;
import com.backend.documentservice.mapper.ProjectMapper;
import com.backend.documentservice.repository.ProjectRepository;
import com.backend.documentservice.repository.SourceDocumentRepository;
import com.backend.documentservice.util.Constants;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.fasterxml.jackson.databind.node.TextNode;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.cache.annotation.CacheConfig;
import org.springframework.cache.annotation.CacheEvict;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.scheduling.annotation.Async;

import java.nio.ByteBuffer;
import java.nio.CharBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.CharsetDecoder;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
@Slf4j
@CacheConfig(cacheNames = "projects")
public class ProjectService {

    private final ProjectRepository projectRepository;
    private final SourceDocumentRepository sourceDocumentRepository;
    private final AITaskLogRepository aiTaskLogRepository;
    private final ProjectExportRepository projectExportRepository;
    private final SlidePageRepository slidePageRepository;
    private final ProjectMapper projectMapper;
    private final AiService aiService;
    private final ObjectMapper objectMapper;
    private final SubscriptionClient subscriptionClient;

    @Value("${app.ai.url}")
    private String aiUrl;

    @Transactional
    @CacheEvict(allEntries = true)
    public ProjectResponse createProject(ProjectCreateRequest request, String userRole) {
        log.info("[document-service] tạo project mới cho user: {}, role: {}", request.getOwnerId(), userRole);

        // 1. Kiểm tra hạn mức (Quota) của user trước khi tạo project
        ApiResponse<QuotaCheckResponse> quotaCheckResponse = subscriptionClient.checkQuota(request.getOwnerId(), "MAX_SLIDES_PER_DAY");
        if (quotaCheckResponse == null || quotaCheckResponse.getData() == null || !quotaCheckResponse.getData().isAllowed()) {
            throw new AppException(ErrorCode.QUOTA_EXCEEDED);
        }

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

        Project project = Project.builder()
                .name(generatedName)
                .ownerId(request.getOwnerId())
                .sourceDocId(request.getSourceDocId())
                .templateId(request.getTemplateId())
                .initialPrompt(request.getPrompt())
                .status(Constants.PROJECT_STATUS.CREATE)
                .build();

        project = projectRepository.save(project);
        log.info("[document-service] lưu project thành công, id: {}, tên: {}", project.getId(), project.getName());

        return projectMapper.toDto(project);
    }

    @Async
    public void generateSlidesAsync(UUID projectId, String userRole) {
        try {
            Project project = projectRepository.findById(projectId)
                    .orElseThrow(() -> new AppException(ErrorCode.PROJECT_NOT_FOUND));

            String documentUrl = "";
            String fileName = "";
            if (project.getSourceDocId() != null) {
                SourceDocument doc = sourceDocumentRepository.findById(project.getSourceDocId())
                        .orElseThrow(() -> new AppException(ErrorCode.DOCUMENT_NOT_FOUND));
                documentUrl = doc.getUrl();
                fileName = doc.getFileName();
            }

            // Khởi tạo Task Log EXTRACT_TEXT ban đầu
            AITaskLog textTaskLog = AITaskLog.builder()
                    .projectId(projectId)
                    .taskType(Constants.TASK_TYPE.EXTRACT_TEXT)
                    .status(Constants.TASK_STATUS.PROCESSING)
                    .startedAt(Instant.now())
                    .build();
            aiTaskLogRepository.save(textTaskLog);

            final String finalDocumentUrl = documentUrl;
            final String finalFileName = fileName;

            try {
                JsonNode aiResponse = aiService.generateSlides(
                    project.getInitialPrompt(), 
                    finalDocumentUrl, 
                    finalFileName, 
                    userRole,
                    taskId -> {
                        Project proj = projectRepository.findById(projectId).orElse(project);
                        proj.setAiTaskId(taskId);
                        projectRepository.save(proj);
                    }
                );

                JsonNode parsedResponse = fixJsonNodeEncoding(aiResponse);
                
                Project proj = projectRepository.findById(projectId).orElse(project);
                
                String deckTitle = parsedResponse.path("deck").path("title").asText("");
                if (!deckTitle.isEmpty()) {
                    proj.setName(deckTitle);
                }

                // Cập nhật cả 2 task log sang SUCCESS khi hoàn thành
                updateAiTaskLogsFromProgress(proj.getId(), "completed", null);

                JsonNode generatedSlides = parsedResponse.path("deck").path("slides");
                log.info("[document-service] AI sinh thành công {} slide cho project ID: {}", generatedSlides.size(), proj.getId());

                ObjectMapper mapper = new ObjectMapper();
                List<SlidePage> slidePagesToSave = new java.util.ArrayList<>();

                for (int i = 0; i < generatedSlides.size(); i++) {
                    JsonNode slideNode = generatedSlides.get(i);
                    
                    int index = slideNode.path("index").asInt(i);
                    String title = slideNode.path("title").asText("");
                    String notes = slideNode.path("notes").asText("");
                    String script = slideNode.path("script").asText("");
                    String layout = slideNode.path("layout").asText("text_only");
                    String primaryVisual = slideNode.path("primary_visual").asText("");
                    boolean likelyMulti = slideNode.path("likely_multi_pptx_slides").asBoolean(false);

                    String imageUrl = "";
                    JsonNode imageNode = slideNode.path("image");
                    if (imageNode.isObject()) {
                        imageUrl = imageNode.path("url").asText("");
                    }

                    if (imageUrl != null && imageUrl.startsWith("/")) {
                        imageUrl = aiUrl + imageUrl;
                    }

                    String bulletsJson = mapper.writeValueAsString(slideNode.path("bullets"));
                    String chartJson = slideNode.hasNonNull("chart") && !slideNode.path("chart").isNull() 
                            ? mapper.writeValueAsString(slideNode.path("chart")) : null;
                    String tableJson = slideNode.hasNonNull("table") && !slideNode.path("table").isNull() 
                            ? mapper.writeValueAsString(slideNode.path("table")) : null;

                    SlidePage slidePage = SlidePage.builder()
                            .projectId(proj.getId())
                            .pageIndex(index)
                            .title(title)
                            .bullets(bulletsJson)
                            .notes(notes)
                            .script(script)
                            .chart(chartJson)
                            .table(tableJson)
                            .imageUrl(imageUrl)
                            .layout(layout)
                            .primaryVisual(primaryVisual)
                            .likelyMultiPptxSlides(likelyMulti)
                            .build();
                    slidePagesToSave.add(slidePage);
                }
                slidePageRepository.saveAll(slidePagesToSave);
                proj.setStatus(Constants.PROJECT_STATUS.DONE);
                projectRepository.save(proj);
                log.info("[document-service] Đã lưu thành công các slide.");

                try {
                    InternalQuotaRequest quotaRequest = InternalQuotaRequest.builder()
                            .userId(proj.getOwnerId())
                            .featureKey("MAX_SLIDES_PER_DAY")
                            .amount(1)
                            .build();
                    subscriptionClient.consumeQuota(quotaRequest);
                } catch (Exception ex) {
                    log.error("[document-service] Lỗi khi trừ hạn mức của user {}", proj.getOwnerId(), ex);
                }
            } catch (AppException e) {
                log.error("[document-service] Lỗi ứng dụng khi sinh slide từ AI cho project ID: {}", projectId, e);
                updateAiTaskLogsFromProgress(projectId, "failed", null);
                Project proj = projectRepository.findById(projectId).orElse(project);
                proj.setStatus(Constants.PROJECT_STATUS.FAILED);
                projectRepository.save(proj);
            } catch (Exception e) {
                log.error("[document-service] Thất bại khi sinh slide từ AI cho project ID: {}", projectId, e);
                updateAiTaskLogsFromProgress(projectId, "failed", null);
                Project proj = projectRepository.findById(projectId).orElse(project);
                proj.setStatus(Constants.PROJECT_STATUS.FAILED);
                projectRepository.save(proj);
            }
        } catch (Exception e) {
            log.error("[document-service] Lỗi nghiêm trọng trong luồng xử lý bất đồng bộ project ID: {}", projectId, e);
        }
    }

    @Transactional
    public ProjectProgressResponse getProjectProgress(UUID projectId, UUID userId) {
        log.info("[document-service] Lấy tiến trình project id: {} của user: {}", projectId, userId);
        Project project = projectRepository.findById(projectId)
                .orElseThrow(() -> new AppException(ErrorCode.PROJECT_NOT_FOUND));

        if (!project.getOwnerId().equals(userId)) {
            throw new AppException(ErrorCode.ACCESS_DENIED);
        }

        if (project.getStatus() == Constants.PROJECT_STATUS.DONE) {
            return ProjectProgressResponse.builder()
                    .projectId(projectId)
                    .aiTaskId(project.getAiTaskId())
                    .projectStatus(project.getStatus())
                    .aiStatus("completed")
                    .progress(100)
                    .build();
        }

        if (project.getStatus() == Constants.PROJECT_STATUS.FAILED) {
            return ProjectProgressResponse.builder()
                    .projectId(projectId)
                    .aiTaskId(project.getAiTaskId())
                    .projectStatus(project.getStatus())
                    .aiStatus("failed")
                    .progress(0)
                    .build();
        }

        if (project.getAiTaskId() == null || project.getAiTaskId().isBlank()) {
            return ProjectProgressResponse.builder()
                    .projectId(projectId)
                    .projectStatus(project.getStatus())
                    .aiStatus("processing")
                    .progress(0)
                    .build();
        }

        try {
            JsonNode aiStatusResponse = aiService.checkAiTaskStatus(project.getAiTaskId());
            String aiStatus = aiStatusResponse.path("status").asText("processing");
            int progress = aiStatusResponse.path("progress").asInt(0);
            JsonNode resultNode = aiStatusResponse.path("result");

            // Đồng bộ trạng thái vào bảng ai_task_logs thực tế theo tiến trình AI
            updateAiTaskLogsFromProgress(projectId, aiStatus, resultNode);

            ProjectProgressResponse.ProjectProgressResponseBuilder responseBuilder = ProjectProgressResponse.builder()
                    .projectId(projectId)
                    .aiTaskId(project.getAiTaskId())
                    .aiStatus(aiStatus)
                    .progress(progress);

            if (resultNode != null && !resultNode.isNull()) {
                try {
                    Object resultObj = objectMapper.treeToValue(resultNode, Object.class);
                    responseBuilder.result(resultObj);
                } catch (Exception ex) {
                    log.warn("[document-service] Lỗi khi parse result node từ AI status", ex);
                }
            }

            if ("completed".equalsIgnoreCase(aiStatus)) {
                responseBuilder.projectStatus(Constants.PROJECT_STATUS.CREATE);
            } else if ("error".equalsIgnoreCase(aiStatus) || "failed".equalsIgnoreCase(aiStatus)) {
                String errorMsg = resultNode.path("error").asText("Lỗi từ AI Engine");
                project.setStatus(Constants.PROJECT_STATUS.FAILED);
                projectRepository.save(project);

                responseBuilder.projectStatus(Constants.PROJECT_STATUS.FAILED);
                responseBuilder.errorMessage(errorMsg);
            } else {
                responseBuilder.projectStatus(Constants.PROJECT_STATUS.CREATE);
            }

            return responseBuilder.build();
        } catch (Exception e) {
            log.error("[document-service] Lỗi gọi AI Engine check status cho project: {}", projectId, e);
            return ProjectProgressResponse.builder()
                    .projectId(projectId)
                    .aiTaskId(project.getAiTaskId())
                    .projectStatus(project.getStatus())
                    .aiStatus("processing")
                    .progress(0)
                    .errorMessage("Lỗi kết nối AI Engine: " + e.getMessage())
                    .build();
        }
    }

    private void updateAiTaskLogsFromProgress(UUID projectId, String aiStatus, JsonNode resultNode) {
        try {
            List<AITaskLog> taskLogs = aiTaskLogRepository.findByProjectId(projectId);
            
            AITaskLog textLog = taskLogs.stream()
                    .filter(l -> l.getTaskType() != null && l.getTaskType() == Constants.TASK_TYPE.EXTRACT_TEXT)
                    .findFirst()
                    .orElseGet(() -> {
                        AITaskLog log = AITaskLog.builder()
                                .projectId(projectId)
                                .taskType(Constants.TASK_TYPE.EXTRACT_TEXT)
                                .status(Constants.TASK_STATUS.PROCESSING)
                                .startedAt(Instant.now())
                                .build();
                        return aiTaskLogRepository.save(log);
                    });

            AITaskLog imageLog = taskLogs.stream()
                    .filter(l -> l.getTaskType() != null && l.getTaskType() == Constants.TASK_TYPE.GEN_IMAGE)
                    .findFirst()
                    .orElse(null);

            if ("completed".equalsIgnoreCase(aiStatus)) {
                if (textLog.getStatus() != Constants.TASK_STATUS.SUCCESS) {
                    textLog.setStatus(Constants.TASK_STATUS.SUCCESS);
                    if (textLog.getCompletedAt() == null) textLog.setCompletedAt(Instant.now());
                    aiTaskLogRepository.save(textLog);
                }
                if (imageLog == null) {
                    imageLog = AITaskLog.builder()
                            .projectId(projectId)
                            .taskType(Constants.TASK_TYPE.GEN_IMAGE)
                            .status(Constants.TASK_STATUS.SUCCESS)
                            .startedAt(Instant.now())
                            .completedAt(Instant.now())
                            .build();
                    aiTaskLogRepository.save(imageLog);
                } else if (imageLog.getStatus() != Constants.TASK_STATUS.SUCCESS) {
                    imageLog.setStatus(Constants.TASK_STATUS.SUCCESS);
                    if (imageLog.getCompletedAt() == null) imageLog.setCompletedAt(Instant.now());
                    aiTaskLogRepository.save(imageLog);
                }
                return;
            }

            if ("error".equalsIgnoreCase(aiStatus) || "failed".equalsIgnoreCase(aiStatus)) {
                String errorMsg = resultNode != null && resultNode.hasNonNull("error") ? resultNode.path("error").asText() : "Lỗi từ AI Engine";
                if (textLog.getStatus() == Constants.TASK_STATUS.PROCESSING) {
                    textLog.setStatus(Constants.TASK_STATUS.FAILED);
                    textLog.setErrorMessage(errorMsg);
                    textLog.setCompletedAt(Instant.now());
                    aiTaskLogRepository.save(textLog);
                }
                if (imageLog != null && imageLog.getStatus() == Constants.TASK_STATUS.PROCESSING) {
                    imageLog.setStatus(Constants.TASK_STATUS.FAILED);
                    imageLog.setErrorMessage(errorMsg);
                    imageLog.setCompletedAt(Instant.now());
                    aiTaskLogRepository.save(imageLog);
                }
                return;
            }

            if (resultNode != null && !resultNode.isNull() && resultNode.isObject()) {
                if (resultNode.has("images")) {
                    if (textLog.getStatus() != Constants.TASK_STATUS.SUCCESS) {
                        textLog.setStatus(Constants.TASK_STATUS.SUCCESS);
                        if (textLog.getCompletedAt() == null) textLog.setCompletedAt(Instant.now());
                        aiTaskLogRepository.save(textLog);
                    }
                    if (imageLog == null) {
                        imageLog = AITaskLog.builder()
                                .projectId(projectId)
                                .taskType(Constants.TASK_TYPE.GEN_IMAGE)
                                .status(Constants.TASK_STATUS.PROCESSING)
                                .startedAt(Instant.now())
                                .build();
                        aiTaskLogRepository.save(imageLog);
                    } else if (imageLog.getStatus() == Constants.TASK_STATUS.PENDING) {
                        imageLog.setStatus(Constants.TASK_STATUS.PROCESSING);
                        if (imageLog.getStartedAt() == null) imageLog.setStartedAt(Instant.now());
                        aiTaskLogRepository.save(imageLog);
                    }
                } else if (resultNode.has("chunks")) {
                    if (textLog.getStatus() == Constants.TASK_STATUS.PENDING) {
                        textLog.setStatus(Constants.TASK_STATUS.PROCESSING);
                        aiTaskLogRepository.save(textLog);
                    }
                }
            }
        } catch (Exception e) {
            log.warn("[document-service] Lỗi khi cập nhật ai_task_logs từ tiến trình AI", e);
        }
    }

    @Transactional
    public void cancelProjectTask(UUID projectId, UUID userId) {
        log.info("[document-service] Hủy tác vụ project id: {} cho user: {}", projectId, userId);
        Project project = projectRepository.findById(projectId)
                .orElseThrow(() -> new AppException(ErrorCode.PROJECT_NOT_FOUND));

        if (!project.getOwnerId().equals(userId)) {
            throw new AppException(ErrorCode.ACCESS_DENIED);
        }

        if (project.getStatus() != Constants.PROJECT_STATUS.CREATE) {
            log.warn("[document-service] Project {} không ở trạng thái PROCESSING, không thể hủy", projectId);
            return;
        }

        if (project.getAiTaskId() != null && !project.getAiTaskId().isBlank()) {
            try {
                aiService.cancelAiTask(project.getAiTaskId());
                log.info("[document-service] Đã gửi yêu cầu hủy AI task thành công: {}", project.getAiTaskId());
            } catch (Exception e) {
                log.error("[document-service] Lỗi khi gọi hủy AI task: {}", project.getAiTaskId(), e);
            }
        }

        project.setStatus(Constants.PROJECT_STATUS.FAILED);
        projectRepository.save(project);
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
                .map(page -> {
                    Object bulletsObj = null;
                    Object chartObj = null;
                    Object tableObj = null;
                    
                    try {
                        if (page.getBullets() != null && !page.getBullets().isEmpty()) {
                            bulletsObj = objectMapper.readTree(page.getBullets());
                        }
                        if (page.getChart() != null && !page.getChart().isEmpty()) {
                            chartObj = objectMapper.readTree(page.getChart());
                        }
                        if (page.getTable() != null && !page.getTable().isEmpty()) {
                            tableObj = objectMapper.readTree(page.getTable());
                        }
                    } catch (Exception e) {
                        log.error("Lỗi khi parse các thuộc tính cho slide ID: {}", page.getId(), e);
                    }

                    return SlidePageResponse.builder()
                            .id(page.getId())
                            .projectId(page.getProjectId())
                            .pageIndex(page.getPageIndex())
                            .title(page.getTitle())
                            .bullets(bulletsObj)
                            .notes(page.getNotes())
                            .script(page.getScript())
                            .chart(chartObj)
                            .table(tableObj)
                            .imageUrl(page.getImageUrl())
                            .layout(page.getLayout())
                            .primaryVisual(page.getPrimaryVisual())
                            .likelyMultiPptxSlides(page.getLikelyMultiPptxSlides())
                            .createdAt(page.getCreatedAt())
                            .updatedAt(page.getUpdatedAt())
                            .build();
                })
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
        if (request.getNotes() != null) page.setNotes(request.getNotes());
        if (request.getScript() != null) page.setScript(request.getScript());
        if (request.getLayout() != null) page.setLayout(request.getLayout());
        if (request.getPrimaryVisual() != null) page.setPrimaryVisual(request.getPrimaryVisual());
        if (request.getLikelyMultiPptxSlides() != null) page.setLikelyMultiPptxSlides(request.getLikelyMultiPptxSlides());
        if (request.getImageUrl() != null) page.setImageUrl(request.getImageUrl());

        try {
            if (request.getBullets() != null) {
                page.setBullets(objectMapper.writeValueAsString(request.getBullets()));
            }
            if (request.getChart() != null) {
                page.setChart(objectMapper.writeValueAsString(request.getChart()));
            }
            if (request.getTable() != null) {
                page.setTable(objectMapper.writeValueAsString(request.getTable()));
            }
        } catch (Exception e) {
            log.error("Lỗi khi chuyển đổi các thuộc tính JSON sang chuỗi DB trong updateSlidePage", e);
        }

        page = slidePageRepository.save(page);
        
        Object bulletsObj = null;
        Object chartObj = null;
        Object tableObj = null;
        try {
            if (page.getBullets() != null && !page.getBullets().isEmpty()) {
                bulletsObj = objectMapper.readTree(page.getBullets());
            }
            if (page.getChart() != null && !page.getChart().isEmpty()) {
                chartObj = objectMapper.readTree(page.getChart());
            }
            if (page.getTable() != null && !page.getTable().isEmpty()) {
                tableObj = objectMapper.readTree(page.getTable());
            }
        } catch (Exception e) {
            log.error("Lỗi khi parse các thuộc tính JSON cho response", e);
        }

        return SlidePageResponse.builder()
                .id(page.getId())
                .projectId(page.getProjectId())
                .pageIndex(page.getPageIndex())
                .title(page.getTitle())
                .bullets(bulletsObj)
                .notes(page.getNotes())
                .script(page.getScript())
                .chart(chartObj)
                .table(tableObj)
                .imageUrl(page.getImageUrl())
                .layout(page.getLayout())
                .primaryVisual(page.getPrimaryVisual())
                .likelyMultiPptxSlides(page.getLikelyMultiPptxSlides())
                .createdAt(page.getCreatedAt())
                .updatedAt(page.getUpdatedAt())
                .build();
    }

    @Transactional
    public List<SlidePageResponse> syncSlidePages(UUID projectId, UUID userId, List<SlidePageUpdateRequest> requests) {
        log.info("[document-service] đồng bộ slide pages cho project id: {} cho user: {}", projectId, userId);
        getProjectDetail(projectId, userId);

        List<SlidePage> currentPages = slidePageRepository.findByProjectIdOrderByPageIndexAsc(projectId);
        java.util.Map<UUID, SlidePage> currentPagesMap = currentPages.stream()
                .collect(Collectors.toMap(SlidePage::getId, page -> page));

        List<UUID> requestIds = requests.stream()
                .filter(req -> req.getId() != null)
                .map(SlidePageUpdateRequest::getId)
                .collect(Collectors.toList());

        List<SlidePage> pagesToDelete = currentPages.stream()
                .filter(page -> !requestIds.contains(page.getId()))
                .collect(Collectors.toList());
        if (!pagesToDelete.isEmpty()) {
            slidePageRepository.deleteAll(pagesToDelete);
        }

        List<SlidePage> pagesToSave = new java.util.ArrayList<>();
        for (int i = 0; i < requests.size(); i++) {
            SlidePageUpdateRequest req = requests.get(i);
            SlidePage page;
            
            String bulletsJson = null;
            String chartJson = null;
            String tableJson = null;
            String imageUrl = null;
            
            try {
                if (req.getBullets() != null) {
                    bulletsJson = objectMapper.writeValueAsString(req.getBullets());
                }
                if (req.getChart() != null) {
                    chartJson = objectMapper.writeValueAsString(req.getChart());
                }
                if (req.getTable() != null) {
                    tableJson = objectMapper.writeValueAsString(req.getTable());
                }
                if (req.getImageUrl() != null) {
                    imageUrl = req.getImageUrl();
                }
            } catch (Exception e) {
                log.error("Lỗi khi serialize thuộc tính JSON trong syncSlidePages", e);
            }

            if (req.getId() != null && currentPagesMap.containsKey(req.getId())) {
                page = currentPagesMap.get(req.getId());
                page.setTitle(req.getTitle());
                page.setBullets(bulletsJson);
                page.setNotes(req.getNotes());
                page.setScript(req.getScript());
                page.setChart(chartJson);
                page.setTable(tableJson);
                if (req.getImageUrl() != null) {
                    page.setImageUrl(imageUrl);
                }
                page.setLayout(req.getLayout());
                page.setPrimaryVisual(req.getPrimaryVisual());
                page.setLikelyMultiPptxSlides(req.getLikelyMultiPptxSlides());
                page.setPageIndex(i);
            } else {
                page = SlidePage.builder()
                        .projectId(projectId)
                        .title(req.getTitle())
                        .bullets(bulletsJson)
                        .notes(req.getNotes())
                        .script(req.getScript())
                        .chart(chartJson)
                        .table(tableJson)
                        .imageUrl(imageUrl)
                        .layout(req.getLayout())
                        .primaryVisual(req.getPrimaryVisual())
                        .likelyMultiPptxSlides(req.getLikelyMultiPptxSlides())
                        .pageIndex(i)
                        .build();
            }
            pagesToSave.add(page);
        }

        List<SlidePage> updatedPages = slidePageRepository.saveAll(pagesToSave);

        return updatedPages.stream().map(page -> {
            Object bulletsObj = null;
            Object chartObj = null;
            Object tableObj = null;
            try {
                if (page.getBullets() != null && !page.getBullets().isEmpty()) {
                    bulletsObj = objectMapper.readTree(page.getBullets());
                }
                if (page.getChart() != null && !page.getChart().isEmpty()) {
                    chartObj = objectMapper.readTree(page.getChart());
                }
                if (page.getTable() != null && !page.getTable().isEmpty()) {
                    tableObj = objectMapper.readTree(page.getTable());
                }
            } catch (Exception e) {
                log.error("Lỗi khi parse JSON content cho response đồng bộ", e);
            }

            return SlidePageResponse.builder()
                    .id(page.getId())
                    .projectId(page.getProjectId())
                    .pageIndex(page.getPageIndex())
                    .title(page.getTitle())
                    .bullets(bulletsObj)
                    .notes(page.getNotes())
                    .script(page.getScript())
                    .chart(chartObj)
                    .table(tableObj)
                    .imageUrl(page.getImageUrl())
                    .layout(page.getLayout())
                    .primaryVisual(page.getPrimaryVisual())
                    .likelyMultiPptxSlides(page.getLikelyMultiPptxSlides())
                    .createdAt(page.getCreatedAt())
                    .updatedAt(page.getUpdatedAt())
                    .build();
        }).collect(Collectors.toList());
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
            String name = prompt.trim().replaceAll("\\s+", " ");
            
            String[] stopPhrases = {
                "tạo slide về", "tạo bài thuyết trình về", "làm slide về", 
                "hãy tạo slide về", "viết slide về", "thuyết trình về", 
                "bài thuyết trình về", "tạo slide", "tạo bài"
            };
            
            String lowerName = name.toLowerCase();
            for (String phrase : stopPhrases) {
                if (lowerName.startsWith(phrase)) {
                    name = name.substring(phrase.length()).trim();
                    break;
                }
            }
            
            if (!name.isEmpty()) {
                name = Character.toUpperCase(name.charAt(0)) + name.substring(1);
            }
            
            if (name.length() > 40) {
                int lastSpace = name.lastIndexOf(' ', 37);
                if (lastSpace != -1) {
                    name = name.substring(0, lastSpace) + "...";
                } else {
                    name = name.substring(0, 37) + "...";
                }
            }
            
            return name.isEmpty() ? "Dự án không tên" : name;
        }

        if (fileName != null && !fileName.isBlank()) {
            return "Dự án từ file: " + fileName;
        }

        return "Dự án slide mới (" + LocalDateTime.now().format(DateTimeFormatter.ofPattern("dd/MM HH:mm")) + ")";
    }

    private Integer determineFileType(String fileName) {
        if (fileName == null) return Constants.DOCUMENT_TYPE.TEXT_PROMPT;
        String lower = fileName.toLowerCase();
        if (lower.endsWith(".pdf")) return Constants.DOCUMENT_TYPE.PDF;
        if (lower.endsWith(".docx")) return Constants.DOCUMENT_TYPE.DOCX;
        return Constants.DOCUMENT_TYPE.TEXT_PROMPT;
    }

    private JsonNode fixJsonNodeEncoding(JsonNode node) {
        if (node == null) {
            return null;
        }
        if (node.isTextual()) {
            return new TextNode(fixDoubleEncoding(node.asText()));
        } else if (node.isObject()) {
            ObjectNode objectNode = (ObjectNode) node;
            Iterator<Map.Entry<String, JsonNode>> fields = objectNode.fields();
            while (fields.hasNext()) {
                Map.Entry<String, JsonNode> field = fields.next();
                field.setValue(fixJsonNodeEncoding(field.getValue()));
            }
            return objectNode;
        } else if (node.isArray()) {
            ArrayNode arrayNode = (ArrayNode) node;
            for (int i = 0; i < arrayNode.size(); i++) {
                arrayNode.set(i, fixJsonNodeEncoding(arrayNode.get(i)));
            }
            return arrayNode;
        }
        return node;
    }

    private String fixDoubleEncoding(String text) {
        if (text == null || text.isEmpty()) {
            return text;
        }
        if (!containsIsoMisinterpretedChars(text)) {
            return text;
        }
        try {
            byte[] bytes = text.getBytes(StandardCharsets.ISO_8859_1);
            CharsetDecoder decoder = StandardCharsets.UTF_8.newDecoder();
            decoder.onMalformedInput(CodingErrorAction.REPORT);
            decoder.onUnmappableCharacter(CodingErrorAction.REPORT);
            CharBuffer charBuffer = decoder.decode(ByteBuffer.wrap(bytes));
            String decoded = charBuffer.toString();
            if (isValidVietnamese(decoded) && !containsIsoMisinterpretedChars(decoded)) {
                return decoded;
            }
        } catch (CharacterCodingException e) {
            // Not double encoded
        }
        return text;
    }

    private boolean containsIsoMisinterpretedChars(String text) {
        for (int i = 0; i < text.length(); i++) {
            char c = text.charAt(i);
            if ((c >= 0x00C0 && c <= 0x00FF) || c == 0x00BF || c == 0x00BD) {
                return true;
            }
        }
        return false;
    }

    private boolean isValidVietnamese(String text) {
        for (int i = 0; i < text.length(); i++) {
            char c = text.charAt(i);
            if ((c >= 0x0100 && c <= 0x017F) || (c >= 0x1EA0 && c <= 0x1EF9)) {
                return true;
            }
        }
        return false;
    }
}
