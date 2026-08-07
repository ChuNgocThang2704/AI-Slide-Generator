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
    private static final String DISPLAY_BACKGROUND = "#FFFFFF";
    private static final double MIN_TEXT_CONTRAST = 4.5;

    public TemplateMatchResponse match(TemplateManifest manifest, TemplateMatchRequest request) {
        String requestedType = requestedType(request);
        TemplateManifest.Layout layout = chooseLayout(manifest.getLayouts(), requestedType, request.getPageIndex());
        List<Map<String, Object>> elements = new ArrayList<>();

        elements.add(backgroundElement());
        List<TemplateManifest.Element> bodyPlaceholders = layout.getElements().stream()
                .filter(item -> item.isPlaceholder() && "body".equals(item.getRole()))
                .toList();
        int bodyIndex = 0;
        for (TemplateManifest.Element source : layout.getElements()) {
            if (!source.isPlaceholder()) continue;

            String role = source.getRole();
            if ("title".equals(role) && notBlank(request.getTitle())) {
                elements.add(toElement(source, escapeHtml(request.getTitle()), null, null, false));
            } else if ("body".equals(role)) {
                List<String> bullets = request.getBullets() == null ? List.of() : request.getBullets();
                List<String> assigned = splitBullets(bullets, bodyIndex++, bodyPlaceholders.size());
                if (!assigned.isEmpty()) {
                    elements.add(toElement(source, bulletsHtml(assigned), null, null, false));
                }
            } else if ("image".equals(role)) {
                elements.add(toElement(source, null, emptyToNull(request.getImageUrl()), null, false));
            } else if ("chart".equals(role) && request.getChart() != null) {
                elements.add(toElement(source, null, null, request.getChart(), false));
            } else if ("table".equals(role) && request.getTable() != null) {
                elements.add(toElement(source, null, null, request.getTable(), false));
            }
        }

        ensureSemanticElements(elements, request, manifest);
        ensureReadableTextColors(elements, manifest);
        return TemplateMatchResponse.builder()
                .layoutId(layout.getId())
                .layoutType(layout.getType())
                .backgroundColor(DISPLAY_BACKGROUND)
                .elements(elements)
                .build();
    }

    private TemplateManifest.Layout chooseLayout(
            List<TemplateManifest.Layout> layouts,
            String type,
            Integer pageIndex
    ) {
        List<TemplateManifest.Layout> candidates = layouts.stream()
                .filter(layout -> type.equals(layout.getType()))
                .toList();
        if (candidates.isEmpty()) {
            candidates = layouts.stream()
                    .filter(layout -> "content".equals(layout.getType()))
                    .toList();
        }
        if (candidates.isEmpty()) return layouts.getFirst();
        int rotation = pageIndex == null ? 0 : Math.max(0, pageIndex - ("title".equals(type) ? 0 : 1));
        return candidates.get(rotation % candidates.size());
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

    private Map<String, Object> backgroundElement() {
        Map<String, Object> element = new LinkedHashMap<>();
        element.put("id", "template-background-" + UUID.randomUUID());
        element.put("type", "shape");
        element.put("role", "background");
        element.put("x", 0);
        element.put("y", 0);
        element.put("width", 960);
        element.put("height", 540);
        element.put("rotation", 0);
        element.put("fill", DISPLAY_BACKGROUND);
        element.put("borderColor", "transparent");
        element.put("locked", true);
        return element;
    }

    private void ensureReadableTextColors(
            List<Map<String, Object>> elements,
            TemplateManifest manifest
    ) {
        String replacement = mostReadableThemeColor(manifest, DISPLAY_BACKGROUND);
        for (Map<String, Object> element : elements) {
            if (!"text".equals(element.get("type"))) continue;
            Map<String, Object> style = copyStyle(element.get("style"));
            String current = String.valueOf(style.getOrDefault("color", ""));
            if (contrastRatio(current, DISPLAY_BACKGROUND) < MIN_TEXT_CONTRAST) {
                style.put("color", replacement);
                element.put("style", style);
            }
        }
    }

    private Map<String, Object> copyStyle(Object value) {
        Map<String, Object> result = new LinkedHashMap<>();
        if (value instanceof Map<?, ?> source) {
            source.forEach((key, item) -> result.put(String.valueOf(key), item));
        }
        return result;
    }

    private String mostReadableThemeColor(TemplateManifest manifest, String background) {
        Map<String, String> colors = manifest.getTheme() == null || manifest.getTheme().getColors() == null
                ? Map.of()
                : manifest.getTheme().getColors();
        List<String> candidates = List.of(
                defaultColor(colors.get("tx1"), "#000000"),
                defaultColor(colors.get("dk1"), "#000000"),
                defaultColor(colors.get("tx2"), "#1F2937"),
                defaultColor(colors.get("dk2"), "#1F2937"),
                "#000000",
                "#FFFFFF"
        );
        String themeMatch = candidates.stream()
                .filter(candidate -> contrastRatio(candidate, background) >= MIN_TEXT_CONTRAST)
                .findFirst()
                .orElse(null);
        if (themeMatch != null) return themeMatch;
        return candidates.stream()
                .max((left, right) -> Double.compare(
                        contrastRatio(left, background),
                        contrastRatio(right, background)
                ))
                .orElse("#000000");
    }

    private double contrastRatio(String foreground, String background) {
        double foregroundLuminance = relativeLuminance(foreground);
        double backgroundLuminance = relativeLuminance(background);
        double lighter = Math.max(foregroundLuminance, backgroundLuminance);
        double darker = Math.min(foregroundLuminance, backgroundLuminance);
        return (lighter + 0.05) / (darker + 0.05);
    }

    private double relativeLuminance(String color) {
        if (color == null || !color.matches("#[0-9A-Fa-f]{6}")) return 1;
        double red = linearChannel(Integer.parseInt(color.substring(1, 3), 16) / 255d);
        double green = linearChannel(Integer.parseInt(color.substring(3, 5), 16) / 255d);
        double blue = linearChannel(Integer.parseInt(color.substring(5, 7), 16) / 255d);
        return 0.2126 * red + 0.7152 * green + 0.0722 * blue;
    }

    private double linearChannel(double channel) {
        return channel <= 0.04045
                ? channel / 12.92
                : Math.pow((channel + 0.055) / 1.055, 2.4);
    }

    private String defaultColor(String value, String fallback) {
        return value == null || !value.matches("#[0-9A-Fa-f]{6}") ? fallback : value.toUpperCase();
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
        if (source.getOpacity() != null) element.put("opacity", source.getOpacity());
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

    private String emptyToNull(String value) {
        return notBlank(value) ? value : null;
    }
}
