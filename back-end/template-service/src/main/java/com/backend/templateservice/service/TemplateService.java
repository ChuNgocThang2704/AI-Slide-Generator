package com.backend.templateservice.service;

import com.backend.templateservice.dto.manifest.TemplateManifest;
import com.backend.templateservice.dto.request.TemplateMatchRequest;
import com.backend.templateservice.dto.request.TemplateRequest;
import com.backend.templateservice.dto.response.PageResponse;
import com.backend.templateservice.dto.response.TemplateMatchResponse;
import com.backend.templateservice.dto.response.TemplateResponse;
import com.backend.templateservice.entity.Category;
import com.backend.templateservice.entity.Template;
import com.backend.templateservice.exception.CustomException;
import com.backend.templateservice.exception.ErrorCode;
import com.backend.templateservice.mapper.TemplateMapper;
import com.backend.templateservice.repository.CategoryRepository;
import com.backend.templateservice.repository.TemplateRepository;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.AuditorAware;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
@Slf4j
public class TemplateService {

    private final TemplateRepository templateRepository;
    private final CategoryRepository categoryRepository;
    private final S3Service s3Service;
    private final PowerPointTemplateParser templateParser;
    private final TemplateLayoutMatcher layoutMatcher;
    private final ObjectMapper objectMapper;
    private final AuditorAware<String> auditorProvider;

    public Map<String, Object> uploadFileOnly(MultipartFile file) {
        log.info("[template-service] upload file lên S3: {}", file.getOriginalFilename());
        
        String originalFilename = file.getOriginalFilename();
        if (!isPowerPointTemplate(originalFilename)) {
            throw new CustomException(ErrorCode.INVALID_FILE_FORMAT);
        }

        try {
            String url = s3Service.uploadFile(file, "templates");
            Map<String, Object> result = new HashMap<>();
            result.put("url", url);
            result.put("fileName", file.getOriginalFilename());
            result.put("fileSize", file.getSize());
            return result;
        } catch (IOException e) {
            log.error("Failed to upload template file", e);
            throw new CustomException(ErrorCode.UNCATEGORIZED_EXCEPTION);
        }
    }

    @Transactional
    public TemplateResponse uploadCustomTemplate(MultipartFile file, String requestedName) {
        String originalFilename = file.getOriginalFilename();
        if (!isPowerPointTemplate(originalFilename)) {
            throw new CustomException(ErrorCode.INVALID_FILE_FORMAT);
        }

        try {
            PowerPointTemplateParser.ParsedTemplate parsed = templateParser.parseWithAssets(file.getBytes());
            TemplateManifest manifest = parsed.manifest();
            String url = s3Service.uploadFile(file, "templates/custom");
            Template template = new Template();
            template.setName(firstNonBlank(requestedName, stripExtension(originalFilename), "Custom template"));
            template.setDescription("Uploaded PowerPoint template");
            template.setS3Url(url);
            template.setNumSlides(manifest.getLayouts().size());
            template.setIsPremium(false);
            template.setSourceType("CUSTOM_PPTX");
            template.setParseStatus("READY");
            template.setPrimaryColor(manifest.getTheme().getPrimaryColor());
            template.setBackgroundColor(manifest.getTheme().getBackgroundColor());
            template.setManifestJson(objectMapper.writeValueAsString(manifest));
            Template saved = templateRepository.save(template);
            parsed.assets().forEach((name, bytes) -> {
                try {
                    s3Service.putBytes(assetKey(saved.getId(), name), bytes, PowerPointTemplateParser.contentTypeFor(name));
                } catch (RuntimeException exception) {
                    log.warn("Cannot store template asset {}: {}", name, exception.getMessage());
                }
            });
            return TemplateMapper.toResponse(saved);
        } catch (CustomException exception) {
            throw exception;
        } catch (IOException | RuntimeException exception) {
            log.error("Failed to parse or upload custom template", exception);
            throw new CustomException(ErrorCode.INVALID_TEMPLATE_FILE);
        }
    }

    /**
     * Parses a real PowerPoint deck to open it for editing (not to file it away as a reusable
     * template): every slide's own real text, pictures and shapes are kept in order, 1-to-1,
     * rather than being reduced to one reusable, blanked-out sample layout. The result also
     * becomes a normal custom template of its own (so the same asset-storage and re-parse
     * plumbing as `uploadCustomTemplate` applies), the caller just doesn't have to use it that way.
     */
    @Transactional
    public com.backend.templateservice.dto.response.TemplateImportResponse importSlides(MultipartFile file) {
        String originalFilename = file.getOriginalFilename();
        if (!isPowerPointTemplate(originalFilename)) {
            throw new CustomException(ErrorCode.INVALID_FILE_FORMAT);
        }

        try {
            PowerPointTemplateParser.ParsedTemplate parsed = templateParser.parseWithAssets(file.getBytes(), true);
            TemplateManifest manifest = parsed.manifest();
            String url = s3Service.uploadFile(file, "templates/imports");
            Template template = new Template();
            template.setName(firstNonBlank(stripExtension(originalFilename), "Imported presentation"));
            template.setDescription("Opened from an uploaded PowerPoint file");
            template.setS3Url(url);
            template.setNumSlides(manifest.getLayouts().size());
            template.setIsPremium(false);
            template.setSourceType("IMPORT_PPTX");
            template.setParseStatus("READY");
            template.setPrimaryColor(manifest.getTheme().getPrimaryColor());
            template.setBackgroundColor(manifest.getTheme().getBackgroundColor());
            template.setManifestJson(objectMapper.writeValueAsString(manifest));
            Template saved = templateRepository.save(template);
            parsed.assets().forEach((name, bytes) -> {
                try {
                    s3Service.putBytes(assetKey(saved.getId(), name), bytes, PowerPointTemplateParser.contentTypeFor(name));
                } catch (RuntimeException exception) {
                    log.warn("Cannot store imported asset {}: {}", name, exception.getMessage());
                }
            });
            rewriteAssetUrls(manifest, saved.getId());
            return com.backend.templateservice.dto.response.TemplateImportResponse.builder()
                    .templateId(saved.getId())
                    .manifest(manifest)
                    .build();
        } catch (CustomException exception) {
            throw exception;
        } catch (IOException | RuntimeException exception) {
            log.error("Failed to parse uploaded presentation", exception);
            throw new CustomException(ErrorCode.INVALID_TEMPLATE_FILE);
        }
    }

    /** Turns every "asset:name" placeholder this manifest's elements carry into a servable URL. */
    private void rewriteAssetUrls(TemplateManifest manifest, UUID templateId) {
        manifest.getLayouts().forEach(layout -> {
            rewriteAssetUrls(layout.getElements(), templateId);
            rewriteAssetUrls(layout.getDecor(), templateId);
        });
    }

    private void rewriteAssetUrls(List<TemplateManifest.Element> elements, UUID templateId) {
        if (elements == null) return;
        elements.forEach(element -> {
            String src = element.getSrc();
            if (src != null && src.startsWith("asset:")) {
                element.setSrc("/template/public/assets/" + templateId + "/" + src.substring("asset:".length()));
            }
        });
    }

    public TemplateMatchResponse matchLayout(UUID id, TemplateMatchRequest request) {
        Template template = getAccessibleTemplate(id);
        if (template.getManifestJson() == null || template.getManifestJson().isBlank()) {
            throw new CustomException(ErrorCode.INVALID_TEMPLATE_FILE);
        }
        try {
            TemplateManifest manifest = objectMapper.readValue(template.getManifestJson(), TemplateManifest.class);
            TemplateMatchResponse response = layoutMatcher.match(manifest, request);
            response.getElements().forEach(element -> {
                Object src = element.get("src");
                if (src instanceof String value && value.startsWith("asset:")) {
                    element.put("src", "/template/public/assets/" + id + "/" + value.substring(6));
                }
            });
            return response;
        } catch (JsonProcessingException exception) {
            log.error("Cannot read template manifest {}", id, exception);
            throw new CustomException(ErrorCode.INVALID_TEMPLATE_FILE);
        }
    }

    @Transactional
    public TemplateResponse saveTemplate(TemplateRequest request) {
        Template template;

        if (request.getId() != null) {
            template = getAccessibleTemplate(request.getId());
        } else {
            template = new Template();
            template.setNumSlides(0);
        }

        if (request.getCategoryId() != null) {
            Category category = categoryRepository.findById(request.getCategoryId())
                    .orElseThrow(() -> new CustomException(ErrorCode.CATEGORY_NOT_FOUND));
            template.setCategory(category);
        }

        if (request.getName() != null) template.setName(request.getName());
        if (request.getDescription() != null) template.setDescription(request.getDescription());
        if (request.getIsPremium() != null) template.setIsPremium(request.getIsPremium());
        if (request.getS3Url() != null) template.setS3Url(request.getS3Url());

        template = templateRepository.save(template);
        return TemplateMapper.toResponse(template);
    }

    @Transactional
    public void deleteTemplates(List<UUID> ids) {
        if (ids == null || ids.isEmpty()) {
            return;
        }
        List<Template> templates = templateRepository.findAllById(ids);
        if (!templates.isEmpty()) {
            templates.forEach(this::verifyCustomTemplateOwner);
            for (Template template : templates) {
                if (template.getS3Url() != null) {
                    s3Service.deleteFile(template.getS3Url());
                }
            }
            templateRepository.deleteAll(templates);
        }
    }

    @Transactional
    public void deleteCustomTemplate(UUID id) {
        Template template = templateRepository.findById(id)
                .orElseThrow(() -> new CustomException(ErrorCode.TEMPLATE_NOT_FOUND));
        verifyCustomTemplateOwner(template);
        if (template.getS3Url() != null) {
            s3Service.deleteFile(template.getS3Url());
        }
        deleteAssets(template);
        templateRepository.delete(template);
    }

    /** Re-reads the stored PowerPoint with the current parser (backgrounds, pictures, shapes). */
    @Transactional
    public TemplateResponse reparseCustomTemplate(UUID id) {
        Template template = templateRepository.findById(id)
                .orElseThrow(() -> new CustomException(ErrorCode.TEMPLATE_NOT_FOUND));
        verifyCustomTemplateOwner(template);
        byte[] file = s3Service.getBytesFromUrl(template.getS3Url());
        if (file == null) throw new CustomException(ErrorCode.INVALID_TEMPLATE_FILE);
        try {
            PowerPointTemplateParser.ParsedTemplate parsed = templateParser.parseWithAssets(file);
            deleteAssets(template);
            parsed.assets().forEach((name, bytes) ->
                    s3Service.putBytes(assetKey(template.getId(), name), bytes, PowerPointTemplateParser.contentTypeFor(name)));
            template.setNumSlides(parsed.manifest().getLayouts().size());
            template.setPrimaryColor(parsed.manifest().getTheme().getPrimaryColor());
            template.setBackgroundColor(parsed.manifest().getTheme().getBackgroundColor());
            template.setManifestJson(objectMapper.writeValueAsString(parsed.manifest()));
            return TemplateMapper.toResponse(templateRepository.save(template));
        } catch (CustomException exception) {
            throw exception;
        } catch (IOException | RuntimeException exception) {
            log.error("Failed to re-parse template {}", id, exception);
            throw new CustomException(ErrorCode.INVALID_TEMPLATE_FILE);
        }
    }

    private static String assetKey(UUID templateId, String name) {
        return "templates/custom-assets/" + templateId + "/" + name;
    }

    private void deleteAssets(Template template) {
        if (template.getManifestJson() == null) return;
        try {
            TemplateManifest manifest = objectMapper.readValue(template.getManifestJson(), TemplateManifest.class);
            manifest.getAssets().keySet().forEach(name -> s3Service.deleteKey(assetKey(template.getId(), name)));
        } catch (Exception exception) {
            log.warn("Cannot delete assets of template {}: {}", template.getId(), exception.getMessage());
        }
    }

    /** A template picture, addressed by the template's unguessable id. Null when it does not exist. */
    public byte[] getAssetBytes(UUID templateId, String name) {
        if (name == null || !name.matches("[A-Za-z0-9._-]{1,120}")) return null;
        return s3Service.getBytes(assetKey(templateId, name));
    }

    public TemplateResponse getTemplate(UUID id) {
        Template template = getAccessibleTemplate(id);
        return TemplateMapper.toResponse(template);
    }

    public String getPresignedViewUrl(UUID id) {
        Template template = getAccessibleTemplate(id);
        if (template.getS3Url() == null) {
            throw new CustomException(ErrorCode.UNCATEGORIZED_EXCEPTION); // Could create FILE_NOT_FOUND
        }
        return s3Service.generatePresignedUrl(template.getS3Url());
    }

    public PageResponse<TemplateResponse> getAllTemplates(String search, int page, int size) {
        Page<Template> templatePage = templateRepository.searchVisibleTemplates(
                search,
                currentAuditor(),
                PageRequest.of(page, size, Sort.by("createdAt").descending())
        );

        return toPageResponse(templatePage);
    }

    public PageResponse<TemplateResponse> getPublicTemplates(String search, int page, int size) {
        Page<Template> templatePage = templateRepository.searchPublicTemplates(
                search,
                PageRequest.of(page, size, Sort.by("createdAt").descending())
        );

        return toPageResponse(templatePage);
    }

    private PageResponse<TemplateResponse> toPageResponse(Page<Template> templatePage) {
        return PageResponse.<TemplateResponse>builder()
                .page(templatePage.getNumber())
                .size(templatePage.getSize())
                .totalElements(templatePage.getTotalElements())
                .totalPages(templatePage.getTotalPages())
                .items(templatePage.getContent().stream()
                        .map(TemplateMapper::toResponse)
                        .collect(Collectors.toList()))
                .build();
    }

    private Template getAccessibleTemplate(UUID id) {
        Template template = templateRepository.findById(id)
                .orElseThrow(() -> new CustomException(ErrorCode.TEMPLATE_NOT_FOUND));
        verifyAccess(template);
        return template;
    }

    private void verifyAccess(Template template) {
        if (isPrivateSource(template.getSourceType())
                && !Objects.equals(template.getCreatedBy(), currentAuditor())) {
            throw new CustomException(ErrorCode.TEMPLATE_NOT_FOUND);
        }
    }

    private void verifyCustomTemplateOwner(Template template) {
        if (!isPrivateSource(template.getSourceType())
                || !Objects.equals(template.getCreatedBy(), currentAuditor())) {
            throw new CustomException(ErrorCode.TEMPLATE_NOT_FOUND);
        }
    }

    // IMPORT_PPTX = a real deck the user opened for editing: its manifest holds that deck's own
    // text, so it must never be visible to (or deletable by) anyone but its owner.
    private static boolean isPrivateSource(String sourceType) {
        return "CUSTOM_PPTX".equals(sourceType) || "GENERATED_THEME".equals(sourceType) || "IMPORT_PPTX".equals(sourceType);
    }

    /**
     * Saves a prompt-generated template. The whole design is the short code, kept in
     * `description`, so nothing else has to be stored. Saving the same code twice returns
     * the entry the user already has.
     */
    @Transactional
    public TemplateResponse saveGeneratedTheme(String name, String code) {
        if (code == null || !code.matches("gen[0-9]+(\\.[0-9]{1,4}){5,20}")) {
            throw new CustomException(ErrorCode.INVALID_TEMPLATE_FILE);
        }
        String owner = currentAuditor();
        Template existing = templateRepository
                .findFirstBySourceTypeAndCreatedByAndDescription("GENERATED_THEME", owner, code)
                .orElse(null);
        if (existing != null) return TemplateMapper.toResponse(existing);

        Template template = new Template();
        template.setName(firstNonBlank(name == null ? null : name.trim(), "Template tạo theo prompt"));
        template.setDescription(code);
        template.setSourceType("GENERATED_THEME");
        template.setParseStatus("READY");
        template.setNumSlides(0);
        template.setIsPremium(false);
        return TemplateMapper.toResponse(templateRepository.save(template));
    }

    private String currentAuditor() {
        return auditorProvider.getCurrentAuditor().orElse("SYSTEM");
    }

    private boolean isPowerPointTemplate(String filename) {
        if (filename == null) return false;
        String lower = filename.toLowerCase();
        return lower.endsWith(".pptx") || lower.endsWith(".potx");
    }

    private String stripExtension(String filename) {
        if (filename == null) return null;
        int separator = filename.lastIndexOf('.');
        return separator > 0 ? filename.substring(0, separator) : filename;
    }

    private String firstNonBlank(String... values) {
        for (String value : values) {
            if (value != null && !value.isBlank()) return value.trim();
        }
        return null;
    }
}
