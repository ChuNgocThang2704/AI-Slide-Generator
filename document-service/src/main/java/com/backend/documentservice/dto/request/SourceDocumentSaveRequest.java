package com.backend.documentservice.dto.request;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Positive;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class SourceDocumentSaveRequest {

    @NotBlank(message = "fileName is required")
    private String fileName;

    @NotBlank(message = "url is required")
    private String url;

    @Positive(message = "fileSize must be greater than zero")
    private Long fileSize;
}
