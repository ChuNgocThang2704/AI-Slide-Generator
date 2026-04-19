package com.backend.documentservice.dto.request;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import org.springframework.web.multipart.MultipartFile;

import java.util.UUID;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ProjectCreateRequest {

    private String prompt;

    private UUID templateId;

    private UUID aiConfigId;

    private MultipartFile file;

    // Set by controller from SecurityContext
    private UUID ownerId;
}
