package com.backend.templateservice.service;

import com.backend.templateservice.dto.request.TemplateRequest;
import com.backend.templateservice.dto.response.PageResponse;
import com.backend.templateservice.dto.response.TemplateResponse;
import com.backend.templateservice.entity.Category;
import com.backend.templateservice.entity.Template;
import com.backend.templateservice.exception.CustomException;
import com.backend.templateservice.exception.ErrorCode;
import com.backend.templateservice.mapper.TemplateMapper;
import com.backend.templateservice.repository.CategoryRepository;
import com.backend.templateservice.repository.TemplateRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
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
import java.util.UUID;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
@Slf4j
public class TemplateService {

    private final TemplateRepository templateRepository;
    private final CategoryRepository categoryRepository;
    private final S3Service s3Service;

    public Map<String, Object> uploadFileOnly(MultipartFile file) {
        log.info("[template-service] upload file lên S3: {}", file.getOriginalFilename());
        
        String originalFilename = file.getOriginalFilename();
        if (originalFilename == null || !originalFilename.toLowerCase().endsWith(".pptx")) {
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
    public TemplateResponse saveTemplate(TemplateRequest request) {
        Template template;

        if (request.getId() != null) {
            template = templateRepository.findById(request.getId())
                    .orElseThrow(() -> new CustomException(ErrorCode.TEMPLATE_NOT_FOUND));
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
            for (Template template : templates) {
                if (template.getS3Url() != null) {
                    s3Service.deleteFile(template.getS3Url());
                }
            }
            templateRepository.deleteAll(templates);
        }
    }

    public TemplateResponse getTemplate(UUID id) {
        Template template = templateRepository.findById(id)
                .orElseThrow(() -> new CustomException(ErrorCode.TEMPLATE_NOT_FOUND));
        return TemplateMapper.toResponse(template);
    }

    public String getPresignedViewUrl(UUID id) {
        Template template = templateRepository.findById(id)
                .orElseThrow(() -> new CustomException(ErrorCode.TEMPLATE_NOT_FOUND));
        if (template.getS3Url() == null) {
            throw new CustomException(ErrorCode.UNCATEGORIZED_EXCEPTION); // Could create FILE_NOT_FOUND
        }
        return s3Service.generatePresignedUrl(template.getS3Url());
    }

    public PageResponse<TemplateResponse> getAllTemplates(String search, int page, int size) {
        Page<Template> templatePage = templateRepository.searchTemplates(
                search,
                PageRequest.of(page, size, Sort.by("createdAt").descending())
        );

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
}
