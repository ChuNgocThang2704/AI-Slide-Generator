package com.backend.templateservice.mapper;

import com.backend.templateservice.dto.response.TemplateResponse;
import com.backend.templateservice.entity.Template;

public class TemplateMapper {
    public static TemplateResponse toResponse(Template template) {
        if (template == null) return null;
        return TemplateResponse.builder()
                .id(template.getId())
                .name(template.getName())
                .description(template.getDescription())
                .s3Url(template.getS3Url())
                .numSlides(template.getNumSlides())
                .isPremium(template.getIsPremium())
                .category(CategoryMapper.toResponse(template.getCategory()))
                .createdAt(template.getCreatedAt())
                .updatedAt(template.getUpdatedAt())
                .build();
    }
}
