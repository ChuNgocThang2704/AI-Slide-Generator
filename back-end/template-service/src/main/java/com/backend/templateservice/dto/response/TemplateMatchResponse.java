package com.backend.templateservice.dto.response;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class TemplateMatchResponse {
    private String layoutId;
    private String layoutType;
    private String backgroundColor;
    @Builder.Default
    private List<Map<String, Object>> elements = new ArrayList<>();
}
