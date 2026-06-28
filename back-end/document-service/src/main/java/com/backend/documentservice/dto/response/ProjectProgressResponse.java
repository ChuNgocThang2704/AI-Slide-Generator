package com.backend.documentservice.dto.response;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;
import java.util.UUID;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ProjectProgressResponse implements Serializable {
    private UUID projectId;
    private String aiTaskId;
    private Integer projectStatus;
    private String aiStatus;
    private Integer progress;
    private Object result;
    private String errorMessage;
}
