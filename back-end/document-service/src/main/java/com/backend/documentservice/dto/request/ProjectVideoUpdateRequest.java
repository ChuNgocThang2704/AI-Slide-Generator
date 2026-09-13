package com.backend.documentservice.dto.request;

import lombok.Data;

@Data
public class ProjectVideoUpdateRequest {
    private String phase;
    private String status;
    private Integer progress;
    private Integer currentSlide;
    private Integer totalSlides;
    private String videoUrl;
    private String temporaryVideoUrl;
    private String error;
    private Boolean startNew;
}
