package com.backend.documentservice.dto.response;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.UUID;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class AiConfigResponse {
    private UUID id;
    private String roleCode;
    private String configName;
    private String language;
    private String tone;
    private Integer maxProjectsPerDay;
    private Integer minPagesPerProject;
    private Integer maxPagesPerProject;
}
