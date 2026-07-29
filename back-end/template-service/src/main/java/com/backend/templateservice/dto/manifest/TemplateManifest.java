package com.backend.templateservice.dto.manifest;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class TemplateManifest {
    private double width;
    private double height;
    private String aspectRatio;
    @Builder.Default
    private Theme theme = new Theme();
    @Builder.Default
    private List<Layout> layouts = new ArrayList<>();

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class Theme {
        private String primaryColor;
        private String backgroundColor;
        private String headingFont;
        private String bodyFont;
        @Builder.Default
        private Map<String, String> colors = new LinkedHashMap<>();
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class Layout {
        private String id;
        private String name;
        private String type;
        private String backgroundColor;
        @Builder.Default
        private List<Element> elements = new ArrayList<>();
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class Element {
        private String id;
        private String type;
        private String role;
        private double x;
        private double y;
        private double width;
        private double height;
        private double rotation;
        private boolean placeholder;
        private boolean locked;
        private String content;
        private String src;
        private String fill;
        private String borderColor;
        @Builder.Default
        private Map<String, Object> style = new LinkedHashMap<>();
    }
}
