package com.backend.documentservice.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.UUID;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class AiConfigDTO {

    private UUID id;
    private String configName;
    private String language;
    private String tone;
    private Integer maxSlideCount;
}
