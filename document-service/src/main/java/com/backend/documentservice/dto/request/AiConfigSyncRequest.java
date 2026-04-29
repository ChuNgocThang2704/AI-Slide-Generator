package com.backend.documentservice.dto.request;

import jakarta.validation.constraints.NotBlank;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.UUID;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class AiConfigSyncRequest {
    private UUID id;

    @NotBlank(message = "Mã vai trò không được để trống")
    private String roleCode;

    @NotBlank(message = "Tên cấu hình không được để trống")
    private String configName;

    private String language;
    private String tone;
    private Integer maxProjectsPerDay;
    private Integer minPagesPerProject;
    private Integer maxPagesPerProject;
}
