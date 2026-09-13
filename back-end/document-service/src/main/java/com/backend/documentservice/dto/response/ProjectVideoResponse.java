package com.backend.documentservice.dto.response;

import lombok.Builder;
import lombok.Data;

import java.time.Instant;
import java.util.UUID;

@Data
@Builder
public class ProjectVideoResponse {
    private UUID id;
    private UUID projectId;
    private String phase;
    private String status;
    private Integer progress;
    private Integer currentSlide;
    private Integer totalSlides;
    private String videoUrl;
    private String temporaryVideoUrl;
    private String error;
    private Instant createdAt;
    private Instant updatedAt;
}
