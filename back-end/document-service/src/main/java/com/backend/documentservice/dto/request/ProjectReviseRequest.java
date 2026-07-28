package com.backend.documentservice.dto.request;

import jakarta.validation.constraints.NotBlank;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ProjectReviseRequest {
    @NotBlank
    private String revisionPrompt;
    private Boolean generateImages;
    private String revisionScope;
    private Integer slideIndex;
    private Integer slideNumber;
    private Integer contextSlideNumber;
    private Integer imageLimit;
}
