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
public class SlidePageResponse {
    private UUID id;
    private UUID projectId;
    private Integer pageIndex;
    private String title;
    private String content;
    private String imagePrompt;
    private String imageUrl;
}
