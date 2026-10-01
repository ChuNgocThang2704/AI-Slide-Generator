package com.backend.templateservice.dto.response;

import com.backend.templateservice.dto.manifest.TemplateManifest;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.UUID;

/**
 * A real PowerPoint deck parsed for editing (see TemplateService#importSlides): unlike a
 * template upload, `manifest.layouts` here is a faithful, ordered, 1-to-1 copy of the file's
 * own slides — real text, and every picture/shape as that slide's own background/decor —
 * meant to seed a new project's slides directly, not to be matched against later.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class TemplateImportResponse {
    private UUID templateId;
    private TemplateManifest manifest;
}
