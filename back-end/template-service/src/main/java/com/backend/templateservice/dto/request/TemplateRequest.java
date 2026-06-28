package com.backend.templateservice.dto.request;

import lombok.AccessLevel;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.experimental.FieldDefaults;

import java.util.UUID;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class TemplateRequest {
    private UUID id;
    private String name;
    private String description;
    private Boolean isPremium;
    private UUID categoryId;
    private String s3Url;
}
