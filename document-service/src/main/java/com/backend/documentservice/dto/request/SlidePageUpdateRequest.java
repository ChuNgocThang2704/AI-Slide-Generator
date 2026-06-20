package com.backend.documentservice.dto.request;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.UUID;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class SlidePageUpdateRequest {
    private UUID id;
    private String title;
    private Object bullets;
    private String notes;
    private Object chart;
    private Object table;
    private String imageUrl;
    private String layout;
    private String primaryVisual;
    private Boolean likelyMultiPptxSlides;
}
