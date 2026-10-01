package com.backend.documentservice.dto.request;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/** Creates a project straight from an already-parsed file (see step 5: opening a real .pptx),
 *  with no AI generation step — the caller fills its slides right after via syncSlidePages. */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ProjectImportRequest {
    private String name;
    private String templateId;
}
