package com.backend.templateservice.dto.response;

import lombok.AccessLevel;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.experimental.FieldDefaults;

import java.time.Instant;
import java.util.UUID;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class TemplateResponse {
    private UUID id;
    private String name;
    private String description;
    private String s3Url;
    private Integer numSlides;
    private Boolean isPremium;
    private CategoryResponse category;
    private Instant createdAt;
    private Instant updatedAt;
}
