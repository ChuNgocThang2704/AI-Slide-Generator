package com.backend.templateservice.dto.request;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.ArrayList;
import java.util.List;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class TemplateMatchRequest {
    private String title;
    @Builder.Default
    private List<String> bullets = new ArrayList<>();
    private String imageUrl;
    private String layout;
    private Object chart;
    private Object table;
    private Integer pageIndex;
}
