package com.backend.documentservice.service;

import com.backend.documentservice.dto.request.ProjectCreateRequest;
import com.backend.documentservice.dto.request.ProjectReviseRequest;
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
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.scheduling.annotation.Async;
import org.springframework.web.client.RestTemplate;

import java.net.URI;
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
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicReference;
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
    private final RestTemplate imageProxyClient = new RestTemplate();

    @Value("${app.ai.url}")
    private String aiUrl;

    public record ProxiedImage(byte[] bytes, MediaType contentType) {}

    public ProxiedImage proxyProjectImage(UUID projectId, UUID userId, String requestedUrl) {
        Project project = projectRepository.findById(projectId)
                .orElseThrow(() -> new AppException(ErrorCode.PROJECT_NOT_FOUND));
        if (!project.getOwnerId().equals(userId)) {
            throw new AppException(ErrorCode.ACCESS_DENIED);
        }

        String normalizedRequestedUrl = normalizeImageUrl(requestedUrl);
        if (normalizedRequestedUrl == null) {
            throw new AppException(ErrorCode.ACCESS_DENIED);
        }

        Set<String> allowedUrls = new HashSet<>();
        for (SlidePage page : slidePageRepository.findByProjectIdOrderByPageIndexAsc(projectId)) {
            addAllowedImageUrl(allowedUrls, page.getImageUrl());
            collectImageUrls(allowedUrls, page.getElements());
        }
        if (!allowedUrls.contains(normalizedRequestedUrl)) {
            throw new AppException(ErrorCode.ACCESS_DENIED);
        }

        URI proxyTarget = resolveImageProxyTarget(requestedUrl);
        ResponseEntity<byte[]> response = imageProxyClient.getForEntity(proxyTarget, byte[].class);
        byte[] body = response.getBody();
        if (!response.getStatusCode().is2xxSuccessful() || body == null || body.length == 0) {
            throw new AppException(ErrorCode.DOCUMENT_NOT_FOUND);
        }
        MediaType contentType = response.getHeaders().getContentType();
        if (contentType == null || !"image".equalsIgnoreCase(contentType.getType())) {
            contentType = MediaType.APPLICATION_OCTET_STREAM;
        }
        return new ProxiedImage(body, contentType);
    }

    private URI resolveImageProxyTarget(String requestedUrl) {
        URI requested = URI.create(requestedUrl);
        String host = requested.getHost();
        boolean localAiAlias = host != null
                && ("localhost".equalsIgnoreCase(host)
                || "127.0.0.1".equals(host)
                || "host.docker.internal".equalsIgnoreCase(host))
                && (requested.getPort() == 8000 || requested.getPort() == -1);
        if (!localAiAlias) return requested;

        URI configuredAi = URI.create(aiUrl);
        String basePath = configuredAi.getPath() == null ? "" : configuredAi.getPath().replaceAll("/+$", "");
        String requestedPath = requested.getRawPath() == null ? "" : requested.getRawPath();
        return URI.create(new StringBuilder()
                .append(configuredAi.getScheme())
                .append("://")
                .append(configuredAi.getRawAuthority())
                .append(basePath)
                .append(requestedPath)
                .append(requested.getRawQuery() == null ? "" : "?" + requested.getRawQuery())
                .toString());
    }

    private void collectImageUrls(Set<String> urls, String elementsJson) {
        if (elementsJson == null || elementsJson.isBlank()) return;
        try {
            collectImageUrls(urls, objectMapper.readTree(elementsJson));
        } catch (Exception exception) {
            log.warn("Khong the doc elements khi proxy anh", exception);
        }
    }

    private void collectImageUrls(Set<String> urls, JsonNode node) {
        if (node == null || node.isNull()) return;
        if (node.isObject()) {
            node.fields().forEachRemaining(entry -> {
                String key = entry.getKey();
                JsonNode value = entry.getValue();
                if (value.isTextual() && ("src".equals(key) || "storageUrl".equals(key) || "imageUrl".equals(key))) {
                    addAllowedImageUrl(urls, value.asText());
                } else {
                    collectImageUrls(urls, value);
                }
            });
        } else if (node.isArray()) {
            node.forEach(child -> collectImageUrls(urls, child));
        }
    }

    private void addAllowedImageUrl(Set<String> urls, String url) {
        String normalized = normalizeImageUrl(url);
        if (normalized == null && url != null && url.startsWith("/")) {
            normalized = normalizeImageUrl(aiUrl.replaceAll("/+$", "") + url);
        }
        if (normalized != null) urls.add(normalized);
    }

    private String normalizeImageUrl(String value) {
        if (value == null || value.isBlank()) return null;
        try {
            URI uri = URI.create(value);
            if (!"http".equalsIgnoreCase(uri.getScheme()) && !"https".equalsIgnoreCase(uri.getScheme())) return null;
            if (uri.getHost() == null) return null;
            String host = uri.getHost();
            boolean localAiAlias = ("localhost".equalsIgnoreCase(host)
                    || "127.0.0.1".equals(host)
                    || "host.docker.internal".equalsIgnoreCase(host))
                    && (uri.getPort() == 8000 || uri.getPort() == -1);
            if (localAiAlias) {
                uri = resolveImageProxyTarget(value);
            }
            return new URI(
                    uri.getScheme().toLowerCase(),
                    uri.getUserInfo(),
                    uri.getHost().toLowerCase(),
                    uri.getPort(),
                    uri.getPath(),
                    null,
                    null
            ).toString();
        } catch (Exception exception) {
            return null;
        }
    }

    @Transactional
    @CacheEvict(allEntries = true)
    public ProjectResponse createProject(ProjectCreateRequest request, String userRole) {
        log.info("[document-service] tạo project mới cho user: {}, role: {}", request.getOwnerId(), userRole);
        validateGenerationPrompt(request);

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

    private void validateGenerationPrompt(ProjectCreateRequest request) {
        String prompt = request.getPrompt() == null ? "" : request.getPrompt().trim();
        long meaningfulWords = java.util.Arrays.stream(prompt.split("\\s+"))
                .map(word -> word.replaceAll("[^\\p{L}\\p{N}]", ""))
                .filter(word -> word.length() >= 2)
                .count();
        boolean hasDocument = (request.getFileUrl() != null && !request.getFileUrl().isBlank())
                || request.getSourceDocId() != null;

        if (prompt.length() < 10 || meaningfulWords < 3) {
            throw new AppException(
                    ErrorCode.INVALID_GENERATION_PROMPT,
                    hasDocument
                            ? "Vui lòng mô tả mục đích và phạm vi nội dung cần tạo từ tài liệu."
                            : "Vui lòng mô tả rõ chủ đề hoặc mục tiêu của bài trình chiếu."
            );
        }

        String folded = java.text.Normalizer.normalize(prompt, java.text.Normalizer.Form.NFD)
                .replaceAll("\\p{M}", "")
                .toLowerCase(java.util.Locale.ROOT)
                .replaceAll("\\s+", " ")
                .trim();
        if (hasDocument && folded.matches(
                "^(?:hay )?(?:tao|lam|create|make)\\s+(?:slide|slides|presentation)"
                        + "(?:\\s+(?:tu|from)\\s+(?:file|tep|tai lieu).*)?$"
        )) {
            throw new AppException(
                    ErrorCode.INVALID_GENERATION_PROMPT,
                    "Yêu cầu còn quá chung chung. Hãy nêu mục đích và phạm vi như toàn bộ tài liệu hoặc chương cụ thể."
            );
        }
    }

    @Async
    public void generateSlidesAsync(UUID projectId, String userRole) {
        try {
            Project project = projectRepository.findById(projectId)
                    .orElseThrow(() -> new AppException(ErrorCode.PROJECT_NOT_FOUND));
            String effectiveUserRole = resolveUserRole(project.getOwnerId(), userRole);

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
                    effectiveUserRole,
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
                applyDeckMetadata(proj, parsedResponse.path("deck"));

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
                    String layout = slideNode.path("layout").asText("text_only");
                    String primaryVisual = slideNode.path("primary_visual").asText("");
                    boolean likelyMulti = slideNode.path("likely_multi_pptx_slides").asBoolean(false);
                    String pedagogicalRole = slideNode.path("pedagogical_role").asText("");

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
                    String sourcePagesJson = slideNode.hasNonNull("source_pages")
                            ? mapper.writeValueAsString(slideNode.path("source_pages")) : null;

                    SlidePage slidePage = SlidePage.builder()
                            .projectId(proj.getId())
                            .pageIndex(index)
                            .title(title)
                            .bullets(bulletsJson)
                            .notes(notes)
                            .chart(chartJson)
                            .table(tableJson)
                            .imageUrl(imageUrl)
                            .layout(layout)
                            .primaryVisual(primaryVisual)
                            .likelyMultiPptxSlides(likelyMulti)
                            .pedagogicalRole(pedagogicalRole)
                            .sourcePages(sourcePagesJson)
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
                updateAiTaskLogsFromProgress(
                        projectId,
                        "failed",
                        objectMapper.createObjectNode().put("error", e.getMessage()));
                Project proj = projectRepository.findById(projectId).orElse(project);
                proj.setStatus(Constants.PROJECT_STATUS.FAILED);
                projectRepository.save(proj);
            } catch (Exception e) {
                log.error("[document-service] Thất bại khi sinh slide từ AI cho project ID: {}", projectId, e);
                String errorMessage = e.getMessage() == null || e.getMessage().isBlank()
                        ? "Unknown error while generating slides"
                        : e.getMessage();
                updateAiTaskLogsFromProgress(
                        projectId,
                        "failed",
                        objectMapper.createObjectNode().put("error", errorMessage));
                Project proj = projectRepository.findById(projectId).orElse(project);
                proj.setStatus(Constants.PROJECT_STATUS.FAILED);
                projectRepository.save(proj);
            }
        } catch (Exception e) {
            log.error("[document-service] Lỗi nghiêm trọng trong luồng xử lý bất đồng bộ project ID: {}", projectId, e);
            String errorMessage = e.getMessage() == null || e.getMessage().isBlank()
                    ? "Unexpected error while preparing slide generation"
                    : e.getMessage();
            updateAiTaskLogsFromProgress(
                    projectId,
                    "failed",
                    objectMapper.createObjectNode().put("error", errorMessage));
            projectRepository.findById(projectId).ifPresent(project -> {
                project.setStatus(Constants.PROJECT_STATUS.FAILED);
                projectRepository.save(project);
            });
        }
    }

    @Transactional
    @CacheEvict(allEntries = true)
    public ProjectResponse requestSlideRevision(UUID projectId, UUID userId, ProjectReviseRequest request, String userRole) {
        Project project = projectRepository.findById(projectId)
                .orElseThrow(() -> new AppException(ErrorCode.PROJECT_NOT_FOUND));

        if (!project.getOwnerId().equals(userId)) {
            throw new AppException(ErrorCode.ACCESS_DENIED);
        }

        if (project.getAiTaskId() == null || project.getAiTaskId().isBlank()) {
            throw new AppException(ErrorCode.AI_API_ERROR, "Project chua co AI task hoan thanh de sua.");
        }

        String revisionQuotaKey = "MAX_REVISIONS_PER_DAY";
        ApiResponse<QuotaCheckResponse> quotaResponse = subscriptionClient.checkQuota(userId, revisionQuotaKey);
        if (quotaResponse == null || quotaResponse.getData() == null || !quotaResponse.getData().isAllowed()) {
            throw new AppException(ErrorCode.QUOTA_EXCEEDED, "Da het luot sua slide trong ngay.");
        }
        subscriptionClient.consumeQuota(InternalQuotaRequest.builder()
                .userId(userId)
                .featureKey(revisionQuotaKey)
                .amount(1)
                .build());

        project.setStatus(Constants.PROJECT_STATUS.CREATE);
        project = projectRepository.save(project);

        AITaskLog reviseLog = AITaskLog.builder()
                .projectId(projectId)
                .taskType(Constants.TASK_TYPE.EXTRACT_TEXT)
                .status(Constants.TASK_STATUS.PROCESSING)
                .startedAt(Instant.now())
                .build();
        aiTaskLogRepository.save(reviseLog);

        return projectMapper.toDto(project);
    }

    public String getCurrentAiTaskId(UUID projectId, UUID userId) {
        Project project = projectRepository.findById(projectId)
                .orElseThrow(() -> new AppException(ErrorCode.PROJECT_NOT_FOUND));

        if (!project.getOwnerId().equals(userId)) {
            throw new AppException(ErrorCode.ACCESS_DENIED);
        }

        String taskId = project.getAiTaskId();
        if (taskId == null || taskId.isBlank()) {
            throw new AppException(ErrorCode.AI_API_ERROR, "Project chua co AI task hoan thanh de sua.");
        }
        return taskId;
    }

    @Async
    public void reviseSlidesAsync(UUID projectId, UUID userId, String sourceTaskId, ProjectReviseRequest request, String userRole) {
        AtomicReference<String> submittedRevisionTaskId = new AtomicReference<>();
        try {
            Project project = projectRepository.findById(projectId)
                    .orElseThrow(() -> new AppException(ErrorCode.PROJECT_NOT_FOUND));
            String effectiveUserRole = resolveUserRole(project.getOwnerId(), userRole);

            JsonNode aiResponse = aiService.reviseSlides(
                    sourceTaskId,
                    request.getRevisionPrompt(),
                    effectiveUserRole,
                    request.getGenerateImages(),
                    request.getRevisionScope(),
                    request.getSlideIndex(),
                    request.getSlideNumber(),
                    request.getContextSlideNumber(),
                    request.getImageLimit(),
                    taskId -> {
                        submittedRevisionTaskId.set(taskId);
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

            replaceSlidePagesFromDeck(proj, parsedResponse);
            updateAiTaskLogsFromProgress(proj.getId(), "completed", null);
            proj.setStatus(Constants.PROJECT_STATUS.DONE);
            projectRepository.save(proj);
            log.info("[document-service] Da cap nhat slide sau khi revise, project ID: {}", projectId);
        } catch (AppException e) {
            revertRevisionQuota(userId);
            log.error("[document-service] Loi ung dung khi revise slide tu AI cho project ID: {}", projectId, e);
            updateAiTaskLogsFromProgress(projectId, "failed", objectMapper.createObjectNode().put("error", e.getMessage()));
            restoreRevisionSourceTask(projectId, sourceTaskId, submittedRevisionTaskId.get());
        } catch (Exception e) {
            revertRevisionQuota(userId);
            log.error("[document-service] That bai khi revise slide tu AI cho project ID: {}", projectId, e);
            updateAiTaskLogsFromProgress(projectId, "failed", objectMapper.createObjectNode().put("error", e.getMessage()));
            restoreRevisionSourceTask(projectId, sourceTaskId, submittedRevisionTaskId.get());
        }
    }

    private void restoreRevisionSourceTask(UUID projectId, String sourceTaskId, String failedRevisionTaskId) {
        Project project = projectRepository.findById(projectId).orElse(null);
        if (project == null) {
            return;
        }

        String currentTaskId = project.getAiTaskId();
        boolean stillOwnsProjectTask = failedRevisionTaskId == null
                ? sourceTaskId.equals(currentTaskId)
                : failedRevisionTaskId.equals(currentTaskId);
        if (!stillOwnsProjectTask) {
            log.warn(
                    "[document-service] Skip restoring source task for project {} because a newer task is active: {}",
                    projectId,
                    currentTaskId
            );
            return;
        }

        project.setAiTaskId(sourceTaskId);
        // A failed revision must not invalidate the last successfully generated deck.
        project.setStatus(Constants.PROJECT_STATUS.DONE);
        projectRepository.save(project);
        log.info(
                "[document-service] Restored last successful AI task {} after revision task {} failed for project {}",
                sourceTaskId,
                failedRevisionTaskId,
                projectId
        );
    }

    private void revertRevisionQuota(UUID userId) {
        try {
            subscriptionClient.revertQuota(InternalQuotaRequest.builder()
                    .userId(userId)
                    .featureKey("MAX_REVISIONS_PER_DAY")
                    .amount(1)
                    .build());
        } catch (Exception quotaError) {
            log.error("Khong the hoan lai quota sua slide cho user {}", userId, quotaError);
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
            AITaskLog latestTask = findLatestProjectTask(projectId);
            if (latestTask != null && latestTask.getStatus() == Constants.TASK_STATUS.FAILED) {
                return ProjectProgressResponse.builder()
                        .projectId(projectId)
                        .aiTaskId(project.getAiTaskId())
                        .projectStatus(project.getStatus())
                        .aiStatus("failed")
                        .progress(0)
                        .errorMessage(latestTask.getErrorMessage())
                        .build();
            }
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
                    .errorMessage(findProjectFailureMessage(projectId))
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

    private String findProjectFailureMessage(UUID projectId) {
        return aiTaskLogRepository.findByProjectIdOrderByStartedAtDesc(projectId).stream()
                .filter(taskLog -> taskLog.getErrorMessage() != null
                        && !taskLog.getErrorMessage().isBlank())
                .findFirst()
                .map(AITaskLog::getErrorMessage)
                .orElse("Lỗi từ AI Engine");
    }

    private AITaskLog findLatestProjectTask(UUID projectId) {
        return aiTaskLogRepository.findByProjectIdOrderByStartedAtDesc(projectId).stream()
                .findFirst()
                .orElse(null);
    }

    private String resolveUserRole(UUID userId, String fallbackRole) {
        try {
            ApiResponse<com.backend.documentservice.dto.response.InternalUserStatusResponse> response =
                    subscriptionClient.getUserStatus(userId);
            String roleName = response != null && response.getData() != null
                    ? response.getData().getRoleName()
                    : null;
            if (roleName != null && !roleName.isBlank()) {
                log.info("[document-service] Resolved active subscription role {} for user {}", roleName, userId);
                return roleName;
            }
        } catch (Exception e) {
            log.warn(
                    "[document-service] Cannot resolve active subscription for user {}; using token role {}",
                    userId,
                    fallbackRole,
                    e);
        }
        return fallbackRole == null || fallbackRole.isBlank()
                ? Constants.USER_ROLES.USER_FREE
                : fallbackRole;
    }

    private void updateAiTaskLogsFromProgress(UUID projectId, String aiStatus, JsonNode resultNode) {
        try {
            List<AITaskLog> taskLogs = aiTaskLogRepository.findByProjectIdOrderByStartedAtDesc(projectId);
            
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

    private void replaceSlidePagesFromDeck(Project project, JsonNode aiResponse) {
        JsonNode deckNode = aiResponse.path("deck");
        JsonNode generatedSlides = deckNode.path("slides");
        if (!generatedSlides.isArray()) {
            throw new AppException(ErrorCode.AI_API_ERROR, "AI response khong co deck.slides hop le.");
        }
        applyDeckMetadata(project, deckNode);

        List<SlidePage> currentPages = slidePageRepository.findByProjectIdOrderByPageIndexAsc(project.getId());
        if (!currentPages.isEmpty()) {
            slidePageRepository.deleteAll(currentPages);
        }

        List<SlidePage> slidePagesToSave = new java.util.ArrayList<>();
        for (int i = 0; i < generatedSlides.size(); i++) {
            JsonNode slideNode = generatedSlides.get(i);

            int index = slideNode.path("index").asInt(i);
            String title = slideNode.path("title").asText("");
            String notes = slideNode.path("notes").asText("");
            String layout = slideNode.path("layout").asText("text_only");
            String primaryVisual = slideNode.path("primary_visual").asText("");
            boolean likelyMulti = slideNode.path("likely_multi_pptx_slides").asBoolean(false);
            String pedagogicalRole = slideNode.path("pedagogical_role").asText("");

            String imageUrl = "";
            JsonNode imageNode = slideNode.path("image");
            if (imageNode.isObject()) {
                imageUrl = imageNode.path("url").asText("");
            }

            if (imageUrl != null && imageUrl.startsWith("/")) {
                imageUrl = normalizeBaseUrl(aiUrl) + imageUrl;
            }

            try {
                String bulletsJson = objectMapper.writeValueAsString(slideNode.path("bullets"));
                String chartJson = slideNode.hasNonNull("chart") && !slideNode.path("chart").isNull()
                        ? objectMapper.writeValueAsString(slideNode.path("chart")) : null;
                String tableJson = slideNode.hasNonNull("table") && !slideNode.path("table").isNull()
                        ? objectMapper.writeValueAsString(slideNode.path("table")) : null;
                String sourcePagesJson = slideNode.hasNonNull("source_pages")
                        ? objectMapper.writeValueAsString(slideNode.path("source_pages")) : null;

                SlidePage slidePage = SlidePage.builder()
                        .projectId(project.getId())
                        .pageIndex(index)
                        .title(title)
                        .bullets(bulletsJson)
                        .notes(notes)
                        .chart(chartJson)
                        .table(tableJson)
                        .imageUrl(imageUrl)
                        .layout(layout)
                        .primaryVisual(primaryVisual)
                        .likelyMultiPptxSlides(likelyMulti)
                        .pedagogicalRole(pedagogicalRole)
                        .sourcePages(sourcePagesJson)
                        .build();
                slidePagesToSave.add(slidePage);
            } catch (Exception e) {
                throw new AppException(ErrorCode.AI_API_ERROR, "Khong the luu du lieu slide tu AI: " + e.getMessage());
            }
        }

        slidePageRepository.saveAll(slidePagesToSave);
        projectRepository.save(project);
    }

    private void applyDeckMetadata(Project project, JsonNode deckNode) {
        if (project == null || deckNode == null || !deckNode.isObject()) return;

        String presentationMode = deckNode.path("presentation_mode").asText("").trim();
        if (!presentationMode.isEmpty()) {
            project.setPresentationMode(presentationMode);
        }

        JsonNode objectivesNode = deckNode.path("learning_objectives");
        if (objectivesNode.isArray()) {
            List<String> objectives = new java.util.ArrayList<>();
            objectivesNode.forEach(item -> {
                String objective = item.asText("").trim();
                if (!objective.isEmpty()) objectives.add(objective);
            });
            project.setLearningObjectives(objectives);
        }
    }

    private String normalizeBaseUrl(String baseUrl) {
        String base = baseUrl == null || baseUrl.isBlank() ? "" : baseUrl.trim();
        while (base.endsWith("/")) {
            base = base.substring(0, base.length() - 1);
        }
        return base;
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
        if (request.getTemplateId() != null) project.setTemplateId(request.getTemplateId());
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
                    Object richTextObj = null;
                    Object elementsObj = null;
                    Object sourcePagesObj = null;
                    
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
                        if (page.getRichText() != null && !page.getRichText().isEmpty()) {
                            richTextObj = objectMapper.readTree(page.getRichText());
                        }
                        if (page.getElements() != null && !page.getElements().isEmpty()) {
                            elementsObj = objectMapper.readTree(page.getElements());
                        }
                        if (page.getSourcePages() != null && !page.getSourcePages().isEmpty()) {
                            sourcePagesObj = objectMapper.readTree(page.getSourcePages());
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
                            .chart(chartObj)
                            .table(tableObj)
                            .richText(richTextObj)
                            .elements(elementsObj)
                            .imageUrl(page.getImageUrl())
                            .layout(page.getLayout())
                            .primaryVisual(page.getPrimaryVisual())
                            .likelyMultiPptxSlides(page.getLikelyMultiPptxSlides())
                            .pedagogicalRole(page.getPedagogicalRole())
                            .sourcePages(sourcePagesObj)
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
        if (request.getLayout() != null) page.setLayout(request.getLayout());
        if (request.getPrimaryVisual() != null) page.setPrimaryVisual(request.getPrimaryVisual());
        if (request.getLikelyMultiPptxSlides() != null) page.setLikelyMultiPptxSlides(request.getLikelyMultiPptxSlides());
        if (request.getPedagogicalRole() != null) page.setPedagogicalRole(request.getPedagogicalRole());
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
            if (request.getRichText() != null) {
                page.setRichText(objectMapper.writeValueAsString(request.getRichText()));
            }
            if (request.getElements() != null) {
                page.setElements(objectMapper.writeValueAsString(request.getElements()));
            }
            if (request.getSourcePages() != null) {
                page.setSourcePages(objectMapper.writeValueAsString(request.getSourcePages()));
            }
        } catch (Exception e) {
            log.error("Lỗi khi chuyển đổi các thuộc tính JSON sang chuỗi DB trong updateSlidePage", e);
            throw new AppException(ErrorCode.UNCATEGORIZED_EXCEPTION, "Không thể lưu dữ liệu chỉnh sửa slide");
        }

        page = slidePageRepository.save(page);
        
        Object bulletsObj = null;
        Object chartObj = null;
        Object tableObj = null;
        Object richTextObj = null;
        Object elementsObj = null;
        Object sourcePagesObj = null;
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
            if (page.getRichText() != null && !page.getRichText().isEmpty()) {
                richTextObj = objectMapper.readTree(page.getRichText());
            }
            if (page.getElements() != null && !page.getElements().isEmpty()) {
                elementsObj = objectMapper.readTree(page.getElements());
            }
            if (page.getSourcePages() != null && !page.getSourcePages().isEmpty()) {
                sourcePagesObj = objectMapper.readTree(page.getSourcePages());
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
                .chart(chartObj)
                .table(tableObj)
                .richText(richTextObj)
                .elements(elementsObj)
                .imageUrl(page.getImageUrl())
                .layout(page.getLayout())
                .primaryVisual(page.getPrimaryVisual())
                .likelyMultiPptxSlides(page.getLikelyMultiPptxSlides())
                .pedagogicalRole(page.getPedagogicalRole())
                .sourcePages(sourcePagesObj)
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
            String richTextJson = null;
            String elementsJson = null;
            String sourcePagesJson = null;
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
                if (req.getRichText() != null) {
                    richTextJson = objectMapper.writeValueAsString(req.getRichText());
                }
                if (req.getElements() != null) {
                    elementsJson = objectMapper.writeValueAsString(req.getElements());
                }
                if (req.getSourcePages() != null) {
                    sourcePagesJson = objectMapper.writeValueAsString(req.getSourcePages());
                }
                if (req.getImageUrl() != null) {
                    imageUrl = req.getImageUrl();
                }
            } catch (Exception e) {
                log.error("Lỗi khi serialize thuộc tính JSON trong syncSlidePages", e);
                throw new AppException(ErrorCode.UNCATEGORIZED_EXCEPTION, "Không thể lưu dữ liệu chỉnh sửa slide");
            }

            if (req.getId() != null && currentPagesMap.containsKey(req.getId())) {
                page = currentPagesMap.get(req.getId());
                page.setTitle(req.getTitle());
                page.setBullets(bulletsJson);
                page.setNotes(req.getNotes());
                page.setChart(chartJson);
                page.setTable(tableJson);
                page.setRichText(richTextJson);
                page.setElements(elementsJson);
                if (req.getImageUrl() != null) {
                    page.setImageUrl(imageUrl);
                }
                page.setLayout(req.getLayout());
                page.setPrimaryVisual(req.getPrimaryVisual());
                page.setLikelyMultiPptxSlides(req.getLikelyMultiPptxSlides());
                page.setPedagogicalRole(req.getPedagogicalRole());
                page.setSourcePages(sourcePagesJson);
                page.setPageIndex(i);
            } else {
                page = SlidePage.builder()
                        .projectId(projectId)
                        .title(req.getTitle())
                        .bullets(bulletsJson)
                        .notes(req.getNotes())
                        .chart(chartJson)
                        .table(tableJson)
                        .richText(richTextJson)
                        .elements(elementsJson)
                        .imageUrl(imageUrl)
                        .layout(req.getLayout())
                        .primaryVisual(req.getPrimaryVisual())
                        .likelyMultiPptxSlides(req.getLikelyMultiPptxSlides())
                        .pedagogicalRole(req.getPedagogicalRole())
                        .sourcePages(sourcePagesJson)
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
            Object richTextObj = null;
            Object elementsObj = null;
            Object sourcePagesObj = null;
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
                if (page.getRichText() != null && !page.getRichText().isEmpty()) {
                    richTextObj = objectMapper.readTree(page.getRichText());
                }
                if (page.getElements() != null && !page.getElements().isEmpty()) {
                    elementsObj = objectMapper.readTree(page.getElements());
                }
                if (page.getSourcePages() != null && !page.getSourcePages().isEmpty()) {
                    sourcePagesObj = objectMapper.readTree(page.getSourcePages());
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
                    .chart(chartObj)
                    .table(tableObj)
                    .richText(richTextObj)
                    .elements(elementsObj)
                    .imageUrl(page.getImageUrl())
                    .layout(page.getLayout())
                    .primaryVisual(page.getPrimaryVisual())
                    .likelyMultiPptxSlides(page.getLikelyMultiPptxSlides())
                    .pedagogicalRole(page.getPedagogicalRole())
                    .sourcePages(sourcePagesObj)
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

        for (Project project : projects) {
            if (
                    project.getStatus() == Constants.PROJECT_STATUS.CREATE
                    && project.getAiTaskId() != null
                    && !project.getAiTaskId().isBlank()
            ) {
                try {
                    aiService.cancelAiTask(project.getAiTaskId());
                    log.info(
                            "[document-service] hủy AI task {} trước khi xóa project {}",
                            project.getAiTaskId(),
                            project.getId()
                    );
                } catch (Exception e) {
                    // Project deletion remains available even if the remote task already ended.
                    log.warn(
                            "[document-service] không thể hủy AI task {} trước khi xóa project {}: {}",
                            project.getAiTaskId(),
                            project.getId(),
                            e.getMessage()
                    );
                }
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

    public long countTotalProjects() {
        return projectRepository.count();
    }

    public long countProjectsBefore(java.time.Instant date) {
        return projectRepository.countProjectsBefore(date);
    }

    public long countProjectsBetween(java.time.Instant startDate, java.time.Instant endDate) {
        return projectRepository.countProjectsBetween(startDate, endDate);
    }

    public java.util.List<Object[]> getTopActiveUsers(int limit) {
        return projectRepository.findTopActiveUsers(org.springframework.data.domain.PageRequest.of(0, limit));
    }

    public java.util.List<Object[]> getProjectsCountByMonth(int year, java.time.Instant startDate, java.time.Instant endDate) {
        return projectRepository.countProjectsByMonth(year, startDate, endDate);
    }

    public long countDistinctOwners() {
        return projectRepository.countDistinctOwners();
    }

    public long countUserProjectsBefore(UUID ownerId, java.time.Instant date) {
        return projectRepository.countByOwnerIdAndCreatedAtBefore(ownerId, date);
    }

    public long countUserProjectsBetween(UUID ownerId, java.time.Instant startDate, java.time.Instant endDate) {
        return projectRepository.countByOwnerIdAndCreatedAtBetween(ownerId, startDate, endDate);
    }

    public java.util.Map<String, Object> getProjectDashboardStats(java.time.Instant startDate, java.time.Instant endDate, int year, int topUsersLimit) {
        log.info("[document-service] Đang tính toán thống kê dashboard dự án slide tổng hợp...");

        long prevCount = projectRepository.countProjectsBefore(startDate);
        long currentCount = projectRepository.countProjectsBetween(startDate, endDate);
        long totalCount = projectRepository.count();

        java.util.Map<String, Long> rangeCountMap = new java.util.HashMap<>();
        rangeCountMap.put("previous_value", prevCount);
        rangeCountMap.put("current_value", currentCount);
        rangeCountMap.put("total_value", totalCount);

        long distinctOwners = projectRepository.countDistinctOwners();

        java.util.List<Object[]> monthlyCounts = projectRepository.countProjectsByMonth(year, startDate, endDate);

        java.util.List<Object[]> rawTop = projectRepository.findTopActiveUsers(org.springframework.data.domain.PageRequest.of(0, topUsersLimit));
        java.util.List<UUID> topUserIds = new java.util.ArrayList<>();
        for (Object[] row : rawTop) {
            topUserIds.add((UUID) row[0]);
        }

        java.util.Map<String, java.util.Map<String, Long>> topUserStats = new java.util.HashMap<>();
        if (!topUserIds.isEmpty()) {
            java.util.List<Object[]> prevCountsList = projectRepository.countProjectsBeforeForUsers(topUserIds, startDate);
            java.util.List<Object[]> currentCountsList = projectRepository.countProjectsBetweenForUsers(topUserIds, startDate, endDate);

            java.util.Map<String, Long> prevCountsMap = new java.util.HashMap<>();
            for (Object[] row : prevCountsList) {
                prevCountsMap.put(row[0].toString(), ((Number) row[1]).longValue());
            }

            java.util.Map<String, Long> currentCountsMap = new java.util.HashMap<>();
            for (Object[] row : currentCountsList) {
                currentCountsMap.put(row[0].toString(), ((Number) row[1]).longValue());
            }

            for (UUID uId : topUserIds) {
                String uIdStr = uId.toString();
                java.util.Map<String, Long> uMap = new java.util.HashMap<>();
                uMap.put("previous_value", prevCountsMap.getOrDefault(uIdStr, 0L));
                uMap.put("current_value", currentCountsMap.getOrDefault(uIdStr, 0L));
                topUserStats.put(uIdStr, uMap);
            }
        }

        java.util.List<Object[]> dailyCounts = projectRepository.countProjectsByDay(startDate, endDate);

        java.util.Map<String, Object> result = new java.util.HashMap<>();
        result.put("range_count", rangeCountMap);
        result.put("distinct_owners_count", distinctOwners);
        result.put("monthly_counts", monthlyCounts);
        result.put("top_users_stats", topUserStats);
        result.put("daily_counts", dailyCounts);

        return result;
    }
}
