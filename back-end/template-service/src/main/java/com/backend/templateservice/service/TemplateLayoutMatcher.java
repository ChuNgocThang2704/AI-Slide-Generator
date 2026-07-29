package com.backend.templateservice.service;

import com.backend.templateservice.dto.manifest.TemplateManifest;
import com.backend.templateservice.dto.request.TemplateMatchRequest;
import com.backend.templateservice.dto.response.TemplateMatchResponse;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Component
public class TemplateLayoutMatcher {

    public TemplateMatchResponse match(TemplateManifest manifest, TemplateMatchRequest request) {
        String requestedType = requestedType(request);
        TemplateManifest.Layout layout = chooseLayout(manifest.getLayouts(), requestedType);
        List<Map<String, Object>> elements = new ArrayList<>();

        elements.add(backgroundElement(layout.getBackgroundColor()));
        List<TemplateManifest.Element> bodyPlaceholders = layout.getElements().stream()
                .filter(item -> item.isPlaceholder() && "body".equals(item.getRole()))
                .toList();
        int bodyIndex = 0;
        for (TemplateManifest.Element source : layout.getElements()) {
            if (!source.isPlaceholder()) {
                elements.add(toElement(source, source.getContent(), source.getSrc(), null, true));
                continue;
            }

            String role = source.getRole();
            if ("title".equals(role) && notBlank(request.getTitle())) {
                elements.add(toElement(source, escapeHtml(request.getTitle()), null, null, false));
            } else if ("body".equals(role)) {
                List<String> bullets = request.getBullets() == null ? List.of() : request.getBullets();
                List<String> assigned = splitBullets(bullets, bodyIndex++, bodyPlaceholders.size());
                if (!assigned.isEmpty()) {
                    elements.add(toElement(source, bulletsHtml(assigned), null, null, false));
                }
            } else if ("image".equals(role) && notBlank(request.getImageUrl())) {
                elements.add(toElement(source, null, request.getImageUrl(), null, false));
            } else if ("chart".equals(role) && request.getChart() != null) {
                elements.add(toElement(source, null, null, request.getChart(), false));
            } else if ("table".equals(role) && request.getTable() != null) {
                elements.add(toElement(source, null, null, request.getTable(), false));
            }
        }

        ensureSemanticElements(elements, request, manifest);
        return TemplateMatchResponse.builder()
                .layoutId(layout.getId())
                .layoutType(layout.getType())
                .backgroundColor(layout.getBackgroundColor())
                .elements(elements)
                .build();
    }

    private TemplateManifest.Layout chooseLayout(List<TemplateManifest.Layout> layouts, String type) {
        return layouts.stream()
                .filter(layout -> type.equals(layout.getType()))
                .findFirst()
                .orElseGet(() -> layouts.stream()
                        .filter(layout -> "content".equals(layout.getType()))
                        .findFirst()
                        .orElse(layouts.getFirst()));
    }

    private String requestedType(TemplateMatchRequest request) {
        if (request.getTable() != null) return "table";
        if (request.getChart() != null) return "chart";
        String layout = String.valueOf(request.getLayout()).toLowerCase();
        if (layout.contains("thank")) return "thankyou";
        if (layout.contains("title") || layout.contains("intro") || Integer.valueOf(0).equals(request.getPageIndex())) {
            return "title";
        }
        if (notBlank(request.getImageUrl())) return "imageText";
        if (layout.contains("two") || layout.contains("split")) return "twoColumn";
        if (layout.contains("quote")) return "quote";
        return "content";
    }

    private Map<String, Object> backgroundElement(String color) {
        Map<String, Object> element = new LinkedHashMap<>();
        element.put("id", "template-background-" + UUID.randomUUID());
        element.put("type", "shape");
        element.put("role", "background");
        element.put("x", 0);
        element.put("y", 0);
        element.put("width", 960);
        element.put("height", 540);
        element.put("rotation", 0);
        element.put("fill", color == null ? "#FFFFFF" : color);
        element.put("borderColor", "transparent");
        element.put("locked", true);
        return element;
    }

    private Map<String, Object> toElement(
            TemplateManifest.Element source,
            String content,
            String src,
            Object data,
            boolean locked
    ) {
        Map<String, Object> element = new LinkedHashMap<>();
        element.put("id", "template-element-" + UUID.randomUUID());
        element.put("type", source.getType());
        element.put("role", source.getRole());
        element.put("x", source.getX());
        element.put("y", source.getY());
        element.put("width", source.getWidth());
        element.put("height", source.getHeight());
        element.put("rotation", source.getRotation());
        element.put("locked", locked);
        if (content != null) element.put("content", content);
        if (src != null) element.put("src", src);
        if (data != null) element.put("data", data);
        if (source.getFill() != null) element.put("fill", source.getFill());
        if (source.getBorderColor() != null) element.put("borderColor", source.getBorderColor());
        if (source.getStyle() != null && !source.getStyle().isEmpty()) {
            element.put("style", new LinkedHashMap<>(source.getStyle()));
        }
        return element;
    }

    private void ensureSemanticElements(
            List<Map<String, Object>> elements,
            TemplateMatchRequest request,
            TemplateManifest manifest
    ) {
        boolean hasTitle = elements.stream().anyMatch(item -> "title".equals(item.get("role")));
        boolean hasBody = elements.stream().anyMatch(item -> "body".equals(item.get("role")));
        boolean hasImage = elements.stream().anyMatch(item -> "image".equals(item.get("role")));
        boolean hasChart = elements.stream().anyMatch(item -> "chart".equals(item.get("role")));
        boolean hasTable = elements.stream().anyMatch(item -> "table".equals(item.get("role")));
        String headingFont = manifest.getTheme().getHeadingFont();
        String bodyFont = manifest.getTheme().getBodyFont();

        if (!hasTitle && notBlank(request.getTitle())) {
            elements.add(textFallback("title", escapeHtml(request.getTitle()), 64, 44, 832, 68, headingFont, 32, 700));
        }
        if (!hasBody && request.getBullets() != null && !request.getBullets().isEmpty()
                && request.getChart() == null && request.getTable() == null) {
            double width = notBlank(request.getImageUrl()) ? 440 : 832;
            elements.add(textFallback("body", bulletsHtml(request.getBullets()), 64, 130, width, 340, bodyFont, 18, 400));
        }
        if (!hasImage && notBlank(request.getImageUrl())) {
            Map<String, Object> image = new LinkedHashMap<>();
            image.put("id", "template-image-" + UUID.randomUUID());
            image.put("type", "image");
            image.put("role", "image");
            image.put("x", 540);
            image.put("y", 130);
            image.put("width", 356);
            image.put("height", 330);
            image.put("rotation", 0);
            image.put("src", request.getImageUrl());
            image.put("locked", false);
            elements.add(image);
        }
        if (!hasChart && request.getChart() != null) {
            elements.add(structuredFallback("chart", request.getChart()));
        }
        if (!hasTable && request.getTable() != null) {
            elements.add(structuredFallback("table", request.getTable()));
        }
    }

    private Map<String, Object> structuredFallback(String type, Object data) {
        Map<String, Object> element = new LinkedHashMap<>();
        element.put("id", "template-" + type + "-" + UUID.randomUUID());
        element.put("type", type);
        element.put("role", type);
        element.put("x", 64);
        element.put("y", 130);
        element.put("width", 832);
        element.put("height", 340);
        element.put("rotation", 0);
        element.put("data", data);
        element.put("locked", false);
        return element;
    }

    private Map<String, Object> textFallback(
            String role,
            String content,
            double x,
            double y,
            double width,
            double height,
            String font,
            int fontSize,
            int fontWeight
    ) {
        Map<String, Object> element = new LinkedHashMap<>();
        element.put("id", "template-" + role + "-" + UUID.randomUUID());
        element.put("type", "text");
        element.put("role", role);
        element.put("x", x);
        element.put("y", y);
        element.put("width", width);
        element.put("height", height);
        element.put("rotation", 0);
        element.put("content", content);
        element.put("locked", false);
        element.put("style", Map.of(
                "fontFamily", font == null ? "Arial" : font,
                "fontSize", fontSize,
                "fontWeight", fontWeight,
                "color", "#1F2937",
                "textAlign", "left",
                "lineHeight", 1.2
        ));
        return element;
    }

    private List<String> splitBullets(List<String> bullets, int index, int count) {
        if (count <= 1) return bullets;
        int from = (int) Math.floor(index * bullets.size() / (double) count);
        int to = (int) Math.floor((index + 1) * bullets.size() / (double) count);
        return bullets.subList(Math.min(from, bullets.size()), Math.min(to, bullets.size()));
    }

    private String bulletsHtml(List<String> bullets) {
        return "<ul>" + bullets.stream()
                .filter(this::notBlank)
                .map(item -> "<li>" + escapeHtml(item) + "</li>")
                .reduce("", String::concat) + "</ul>";
    }

    private String escapeHtml(String value) {
        return value == null ? "" : value
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("\"", "&quot;")
                .replace("'", "&#39;");
    }

    private boolean notBlank(String value) {
        return value != null && !value.isBlank();
    }
}
