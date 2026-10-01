package com.backend.documentservice.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

/**
 * Puts a revised slide's new title and bullets into the boxes of the slide it replaces.
 *
 * <p>A slide opened from a PPTX is a faithful copy: each box sits where the file put it, in the
 * file's own font and alignment. When the AI rewrites such a slide, rebuilding it from the deck's
 * template would give it a different look from every slide around it. Pouring the new words into
 * the old boxes keeps the slide looking like the rest of the deck.
 *
 * <p>Only the title and the main text box take the new words. Short side notes such as a footer
 * address stay where they are; a longer text box other than the main one held content that the
 * revision has replaced, so it is dropped rather than left showing the old words.
 */
final class ImportedSlideReviser {

    /** A short note is at most one line this long; anything bigger counts as slide content. */
    private static final int SHORT_NOTE_CHARS = 40;

    /** The slide's new boxes, and the bullets that read the same as the body boxes it now has. */
    record Poured(String elementsJson, List<String> bullets) {}

    private final ObjectMapper mapper;

    ImportedSlideReviser(ObjectMapper mapper) {
        this.mapper = mapper;
    }

    /**
     * @return the revised slide laid out in the previous slide's boxes, or null when the previous
     *         slide is not an opened PPTX or has no body box to put the bullets in, in which case
     *         the caller lays the slide out as usual
     */
    Poured pour(String previousRichText, String previousElements, String title, List<String> revisedBullets) {
        JsonNode richText = read(previousRichText);
        if (richText == null || !richText.path("_imported").asBoolean(false)) return null;
        JsonNode stored = read(previousElements);
        if (stored == null || !stored.isArray()) return null;

        List<String> lines = revisedBullets == null ? List.of() : revisedBullets.stream()
                .map(String::trim).filter(line -> !line.isEmpty()).toList();
        if (lines.isEmpty()) return null;

        JsonNode main = null;
        int mainLength = 0;
        for (JsonNode element : stored) {
            if (!isBodyText(element)) continue;
            int length = String.join("", plainLines(element.path("content").asText(""))).length();
            if (length > mainLength) {
                main = element;
                mainLength = length;
            }
        }
        if (main == null) return null;

        ArrayNode boxes = mapper.createArrayNode();
        List<String> bullets = new ArrayList<>();
        boolean replacedTitle = false;
        for (JsonNode element : stored) {
            if (!element.isObject()) continue;
            ObjectNode box = element.deepCopy();
            if (isText(element) && "title".equals(element.path("role").asText("")) && !replacedTitle
                    && title != null && !title.isBlank()) {
                box.put("content", "<p>" + escape(title.trim()) + "</p>");
                replacedTitle = true;
            } else if (isBodyText(element)) {
                if (element == main) {
                    String old = element.path("content").asText("");
                    boolean list = lines.size() > 1 || old.contains("<ul") || old.contains("<ol");
                    box.put("content", list ? list(lines) : "<p>" + escape(lines.get(0)) + "</p>");
                    bullets.addAll(lines);
                } else {
                    List<String> own = plainLines(element.path("content").asText(""));
                    if (own.size() > 1 || String.join("", own).length() > SHORT_NOTE_CHARS) continue;
                    bullets.addAll(own);
                }
            }
            boxes.add(box);
        }
        try {
            return new Poured(mapper.writeValueAsString(boxes), bullets);
        } catch (Exception exception) {
            return null;
        }
    }

    private JsonNode read(String json) {
        if (json == null || json.isBlank()) return null;
        try {
            JsonNode node = mapper.readTree(json);
            return node == null || node.isNull() ? null : node;
        } catch (Exception exception) {
            return null;
        }
    }

    private static boolean isText(JsonNode element) {
        return "text".equals(element.path("type").asText(""));
    }

    private static boolean isBodyText(JsonNode element) {
        return isText(element) && "body".equals(element.path("role").asText(""));
    }

    private static String list(List<String> lines) {
        StringBuilder html = new StringBuilder("<ul>");
        lines.forEach(line -> html.append("<li>").append(escape(line)).append("</li>"));
        return html.append("</ul>").toString();
    }

    private static String escape(String value) {
        return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;");
    }

    /** The visible lines of a box's HTML, one per paragraph or list item. */
    static List<String> plainLines(String html) {
        if (html == null || html.isBlank()) return List.of();
        String text = html
                .replaceAll("(?i)</(?:li|p|div|h[1-6])>", "\n")
                .replaceAll("(?i)<br\s*/?>", "\n")
                .replaceAll("<[^>]+>", "")
                .replaceAll("(?i)&nbsp;|&#160;", " ")
                .replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", "\"")
                .replace("&#39;", "'").replace("&amp;", "&");
        return Arrays.stream(text.split("\r?\n")).map(String::trim).filter(line -> !line.isEmpty()).toList();
    }
}
