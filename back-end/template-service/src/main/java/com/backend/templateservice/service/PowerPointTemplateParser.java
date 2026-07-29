package com.backend.templateservice.service;

import com.backend.templateservice.dto.manifest.TemplateManifest;
import com.backend.templateservice.exception.CustomException;
import com.backend.templateservice.exception.ErrorCode;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.Node;
import org.w3c.dom.NodeList;

import javax.xml.XMLConstants;
import javax.xml.parsers.DocumentBuilderFactory;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Base64;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

@Component
@Slf4j
public class PowerPointTemplateParser {
    private static final long DEFAULT_WIDTH = 12_192_000L;
    private static final long DEFAULT_HEIGHT = 6_858_000L;
    private static final long MAX_UNCOMPRESSED_BYTES = 150L * 1024 * 1024;
    private static final long MAX_ENTRY_BYTES = 25L * 1024 * 1024;
    private static final int MAX_ENTRIES = 2_000;
    private static final int MAX_EMBEDDED_IMAGE_BYTES = 750 * 1024;

    public TemplateManifest parse(byte[] fileBytes) {
        try {
            Map<String, byte[]> entries = unzip(fileBytes);
            if (!entries.containsKey("ppt/presentation.xml")) {
                throw new CustomException(ErrorCode.INVALID_TEMPLATE_FILE);
            }

            long[] pageSize = readPageSize(entries.get("ppt/presentation.xml"));
            TemplateManifest.Theme theme = readTheme(entries);
            MasterData master = readMaster(entries, pageSize, theme);
            List<TemplateManifest.Layout> layouts = readLayouts(entries, pageSize, theme, master);
            if (layouts.isEmpty()) {
                layouts.add(defaultLayout(theme));
            }

            String background = layouts.stream()
                    .map(TemplateManifest.Layout::getBackgroundColor)
                    .filter(Objects::nonNull)
                    .findFirst()
                    .orElse(defaultColor(theme.getBackgroundColor(), "#FFFFFF"));
            theme.setBackgroundColor(background);
            theme.setPrimaryColor(defaultColor(theme.getPrimaryColor(), "#4F46E5"));

            return TemplateManifest.builder()
                    .width(960)
                    .height(540)
                    .aspectRatio(aspectRatio(pageSize[0], pageSize[1]))
                    .theme(theme)
                    .layouts(layouts)
                    .build();
        } catch (CustomException exception) {
            throw exception;
        } catch (Exception exception) {
            log.warn("Cannot parse PowerPoint template", exception);
            throw new CustomException(ErrorCode.INVALID_TEMPLATE_FILE);
        }
    }

    private Map<String, byte[]> unzip(byte[] bytes) throws Exception {
        Map<String, byte[]> entries = new HashMap<>();
        long total = 0;
        int count = 0;
        try (ZipInputStream zip = new ZipInputStream(new ByteArrayInputStream(bytes))) {
            ZipEntry entry;
            while ((entry = zip.getNextEntry()) != null) {
                if (entry.isDirectory()) continue;
                count++;
                if (count > MAX_ENTRIES) throw new CustomException(ErrorCode.INVALID_TEMPLATE_FILE);

                String name = entry.getName().replace('\\', '/');
                if (name.startsWith("/") || name.contains("../")) {
                    throw new CustomException(ErrorCode.INVALID_TEMPLATE_FILE);
                }

                ByteArrayOutputStream output = new ByteArrayOutputStream();
                byte[] buffer = new byte[8192];
                int read;
                long entrySize = 0;
                while ((read = zip.read(buffer)) >= 0) {
                    entrySize += read;
                    total += read;
                    if (entrySize > MAX_ENTRY_BYTES || total > MAX_UNCOMPRESSED_BYTES) {
                        throw new CustomException(ErrorCode.INVALID_TEMPLATE_FILE);
                    }
                    output.write(buffer, 0, read);
                }
                entries.put(name, output.toByteArray());
            }
        }
        return entries;
    }

    private long[] readPageSize(byte[] xml) throws Exception {
        Document document = parseXml(xml);
        Element size = firstDescendant(document.getDocumentElement(), "sldSz");
        if (size == null) return new long[]{DEFAULT_WIDTH, DEFAULT_HEIGHT};
        return new long[]{
                longAttr(size, "cx", DEFAULT_WIDTH),
                longAttr(size, "cy", DEFAULT_HEIGHT)
        };
    }

    private TemplateManifest.Theme readTheme(Map<String, byte[]> entries) throws Exception {
        String path = entries.keySet().stream()
                .filter(name -> name.startsWith("ppt/theme/theme") && name.endsWith(".xml"))
                .sorted()
                .findFirst()
                .orElse(null);
        TemplateManifest.Theme theme = TemplateManifest.Theme.builder()
                .colors(new LinkedHashMap<>())
                .backgroundColor("#FFFFFF")
                .primaryColor("#4F46E5")
                .headingFont("Arial")
                .bodyFont("Arial")
                .build();
        if (path == null) return theme;

        Document document = parseXml(entries.get(path));
        Element colorScheme = firstDescendant(document.getDocumentElement(), "clrScheme");
        if (colorScheme != null) {
            for (Element colorNode : childElements(colorScheme)) {
                String value = colorFromNode(colorNode, theme.getColors());
                if (value != null) theme.getColors().put(colorNode.getLocalName(), value);
            }
        }
        theme.setBackgroundColor(defaultColor(theme.getColors().get("lt1"), "#FFFFFF"));
        theme.setPrimaryColor(defaultColor(theme.getColors().get("accent1"), "#4F46E5"));

        Element majorFont = firstDescendant(document.getDocumentElement(), "majorFont");
        Element minorFont = firstDescendant(document.getDocumentElement(), "minorFont");
        theme.setHeadingFont(fontFromScheme(majorFont, "Arial"));
        theme.setBodyFont(fontFromScheme(minorFont, theme.getHeadingFont()));
        return theme;
    }

    private MasterData readMaster(
            Map<String, byte[]> entries,
            long[] pageSize,
            TemplateManifest.Theme theme
    ) throws Exception {
        String path = entries.keySet().stream()
                .filter(name -> name.startsWith("ppt/slideMasters/slideMaster") && name.endsWith(".xml"))
                .sorted()
                .findFirst()
                .orElse(null);
        if (path == null) return new MasterData();

        Document document = parseXml(entries.get(path));
        Map<String, String> relationships = readRelationships(entries, path);
        MasterData result = new MasterData();
        result.backgroundColor = readBackground(document, theme);
        List<TemplateManifest.Element> shapes = parseShapeTree(
                document, path, entries, relationships, pageSize, theme, Map.of()
        );
        for (TemplateManifest.Element shape : shapes) {
            if (shape.isPlaceholder()) {
                result.placeholders.put(placeholderKey(shape), shape);
                result.placeholders.putIfAbsent(shape.getRole(), shape);
            } else {
                result.decorations.add(shape);
            }
        }
        return result;
    }

    private List<TemplateManifest.Layout> readLayouts(
            Map<String, byte[]> entries,
            long[] pageSize,
            TemplateManifest.Theme theme,
            MasterData master
    ) throws Exception {
        List<String> paths = entries.keySet().stream()
                .filter(name -> name.startsWith("ppt/slideLayouts/slideLayout") && name.endsWith(".xml"))
                .sorted(Comparator.naturalOrder())
                .toList();
        List<TemplateManifest.Layout> layouts = new ArrayList<>();
        int index = 0;
        for (String path : paths) {
            Document document = parseXml(entries.get(path));
            Element root = document.getDocumentElement();
            Element commonSlideData = firstDescendant(root, "cSld");
            String name = firstNonBlank(
                    commonSlideData == null ? null : commonSlideData.getAttribute("name"),
                    root.getAttribute("matchingName"),
                    "Layout " + (index + 1)
            );
            Map<String, String> relationships = readRelationships(entries, path);
            List<TemplateManifest.Element> ownElements = parseShapeTree(
                    document, path, entries, relationships, pageSize, theme, master.placeholders
            );
            List<TemplateManifest.Element> elements = new ArrayList<>();
            master.decorations.stream().map(this::copyElement).forEach(elements::add);
            elements.addAll(ownElements);

            String background = firstNonBlank(readBackground(document, theme), master.backgroundColor, theme.getBackgroundColor());
            layouts.add(TemplateManifest.Layout.builder()
                    .id("layout-" + (++index))
                    .name(name)
                    .type(classifyLayout(name, elements))
                    .backgroundColor(background)
                    .elements(elements)
                    .build());
        }
        return layouts;
    }

    private List<TemplateManifest.Element> parseShapeTree(
            Document document,
            String documentPath,
            Map<String, byte[]> entries,
            Map<String, String> relationships,
            long[] pageSize,
            TemplateManifest.Theme theme,
            Map<String, TemplateManifest.Element> inheritedPlaceholders
    ) {
        Element shapeTree = firstDescendant(document.getDocumentElement(), "spTree");
        if (shapeTree == null) return List.of();

        List<TemplateManifest.Element> result = new ArrayList<>();
        int sequence = 0;
        for (Element shape : childElements(shapeTree)) {
            String kind = shape.getLocalName();
            if (!List.of("sp", "pic", "graphicFrame").contains(kind)) continue;

            PlaceholderInfo placeholder = readPlaceholder(shape);
            String role = roleForPlaceholder(placeholder.type);
            if (placeholder.ignore) continue;
            TemplateManifest.Element inherited = inheritedPlaceholders.getOrDefault(
                    placeholder.key(), inheritedPlaceholders.get(role)
            );
            double[] anchor = readAnchor(shape, pageSize);
            if (anchor == null && inherited != null) {
                anchor = new double[]{inherited.getX(), inherited.getY(), inherited.getWidth(), inherited.getHeight()};
            }
            if (anchor == null) continue;

            String elementType = "text";
            String src = null;
            if ("pic".equals(kind)) {
                elementType = "image";
                role = placeholder.present ? role : "decoration";
                src = embeddedImage(shape, documentPath, entries, relationships);
            } else if ("graphicFrame".equals(kind)) {
                elementType = switch (role) {
                    case "chart" -> "chart";
                    case "table" -> "table";
                    default -> "shape";
                };
            } else if (!placeholder.present && !hasText(shape)) {
                elementType = "shape";
                role = "decoration";
            }

            Map<String, Object> style = readTextStyle(shape, role, theme);
            if (inherited != null && inherited.getStyle() != null) {
                Map<String, Object> merged = new LinkedHashMap<>(inherited.getStyle());
                merged.putAll(style);
                style = merged;
            }
            String fill = readShapeFill(shape, theme);
            String border = readLineColor(shape, theme);
            String content = placeholder.present ? "" : readText(shape);

            if ("image".equals(elementType) && src == null && !placeholder.present) continue;
            result.add(TemplateManifest.Element.builder()
                    .id("tpl-" + sequence++ + "-" + UUID.randomUUID().toString().substring(0, 8))
                    .type(elementType)
                    .role(role)
                    .x(anchor[0])
                    .y(anchor[1])
                    .width(anchor[2])
                    .height(anchor[3])
                    .rotation(readRotation(shape))
                    .placeholder(placeholder.present)
                    .locked(!placeholder.present)
                    .content(content)
                    .src(src)
                    .fill(fill)
                    .borderColor(border)
                    .style(style)
                    .build());
        }
        return result;
    }

    private Map<String, Object> readTextStyle(
            Element shape,
            String role,
            TemplateManifest.Theme theme
    ) {
        Map<String, Object> style = new LinkedHashMap<>();
        Element runProperties = firstDescendant(shape, "rPr");
        if (runProperties == null) runProperties = firstDescendant(shape, "defRPr");
        String font = null;
        Double size = null;
        String color = null;
        boolean bold = "title".equals(role);
        if (runProperties != null) {
            Element latin = firstDescendant(runProperties, "latin");
            if (latin != null) font = emptyToNull(latin.getAttribute("typeface"));
            long rawSize = longAttr(runProperties, "sz", 0);
            if (rawSize > 0) size = rawSize / 100d;
            bold = "1".equals(runProperties.getAttribute("b")) || Boolean.parseBoolean(runProperties.getAttribute("b"));
            color = colorFromNode(runProperties, theme.getColors());
        }
        style.put("fontFamily", firstNonBlank(font, "title".equals(role) ? theme.getHeadingFont() : theme.getBodyFont(), "Arial"));
        style.put("fontSize", size == null ? ("title".equals(role) ? 32 : 18) : size);
        style.put("fontWeight", bold ? 700 : 400);
        style.put("color", defaultColor(color, "#1F2937"));
        style.put("textAlign", readTextAlign(shape));
        style.put("verticalAlign", readVerticalAlign(shape));
        style.put("lineHeight", 1.2);
        return style;
    }

    private PlaceholderInfo readPlaceholder(Element shape) {
        Element placeholder = firstDescendant(shape, "ph");
        if (placeholder == null) return PlaceholderInfo.none();
        String type = firstNonBlank(placeholder.getAttribute("type"), "obj");
        String index = placeholder.getAttribute("idx");
        boolean ignored = List.of("dt", "ftr", "sldNum", "hdr").contains(type);
        return new PlaceholderInfo(true, type, index, ignored);
    }

    private String embeddedImage(
            Element shape,
            String documentPath,
            Map<String, byte[]> entries,
            Map<String, String> relationships
    ) {
        Element blip = firstDescendant(shape, "blip");
        if (blip == null) return null;
        String relationshipId = attributeByLocalName(blip, "embed");
        String target = relationships.get(relationshipId);
        if (target == null) return null;
        byte[] image = entries.get(target);
        if (image == null || image.length > MAX_EMBEDDED_IMAGE_BYTES) return null;
        return "data:" + imageContentType(target) + ";base64," + Base64.getEncoder().encodeToString(image);
    }

    private Map<String, String> readRelationships(Map<String, byte[]> entries, String documentPath) throws Exception {
        Path path = Path.of(documentPath);
        String relationshipsPath = path.getParent().resolve("_rels").resolve(path.getFileName() + ".rels")
                .toString().replace('\\', '/');
        byte[] xml = entries.get(relationshipsPath);
        if (xml == null) return Map.of();

        Document document = parseXml(xml);
        Map<String, String> result = new HashMap<>();
        for (Element relationship : descendants(document.getDocumentElement(), "Relationship")) {
            String id = relationship.getAttribute("Id");
            String target = relationship.getAttribute("Target");
            if (id.isBlank() || target.isBlank() || target.startsWith("http")) continue;
            Path resolved = path.getParent().resolve(target).normalize();
            result.put(id, resolved.toString().replace('\\', '/'));
        }
        return result;
    }

    private String readBackground(Document document, TemplateManifest.Theme theme) {
        Element background = firstDescendant(document.getDocumentElement(), "bg");
        return background == null ? null : colorFromNode(background, theme.getColors());
    }

    private String readShapeFill(Element shape, TemplateManifest.Theme theme) {
        Element shapeProperties = firstDescendant(shape, "spPr");
        if (shapeProperties == null) return null;
        return colorFromNode(shapeProperties, theme.getColors());
    }

    private String readLineColor(Element shape, TemplateManifest.Theme theme) {
        Element line = firstDescendant(shape, "ln");
        return line == null ? null : colorFromNode(line, theme.getColors());
    }

    private double[] readAnchor(Element shape, long[] pageSize) {
        Element transform = firstDescendant(shape, "xfrm");
        if (transform == null) return null;
        Element offset = firstDescendant(transform, "off");
        Element extent = firstDescendant(transform, "ext");
        if (offset == null || extent == null) return null;
        return new double[]{
                scale(longAttr(offset, "x", 0), pageSize[0], 960),
                scale(longAttr(offset, "y", 0), pageSize[1], 540),
                Math.max(1, scale(longAttr(extent, "cx", 0), pageSize[0], 960)),
                Math.max(1, scale(longAttr(extent, "cy", 0), pageSize[1], 540))
        };
    }

    private double readRotation(Element shape) {
        Element transform = firstDescendant(shape, "xfrm");
        return transform == null ? 0 : longAttr(transform, "rot", 0) / 60_000d;
    }

    private String classifyLayout(String name, List<TemplateManifest.Element> elements) {
        String normalized = name.toLowerCase(Locale.ROOT);
        if (normalized.matches(".*(title slide|cover|trang bìa|bìa).*")) return "title";
        if (normalized.matches(".*(thank|closing|end|kết thúc).*")) return "thankyou";
        if (normalized.matches(".*(two|comparison|2 content|hai cột).*")) return "twoColumn";
        if (normalized.matches(".*(picture|image|photo|ảnh).*")) return "imageText";
        if (normalized.contains("chart")) return "chart";
        if (normalized.contains("table")) return "table";

        long bodies = elements.stream().filter(item -> item.isPlaceholder() && "body".equals(item.getRole())).count();
        boolean image = elements.stream().anyMatch(item -> item.isPlaceholder() && "image".equals(item.getRole()));
        boolean chart = elements.stream().anyMatch(item -> item.isPlaceholder() && "chart".equals(item.getRole()));
        boolean table = elements.stream().anyMatch(item -> item.isPlaceholder() && "table".equals(item.getRole()));
        if (chart) return "chart";
        if (table) return "table";
        if (image) return "imageText";
        if (bodies >= 2) return "twoColumn";
        if (bodies == 0) return "title";
        return "content";
    }

    private TemplateManifest.Layout defaultLayout(TemplateManifest.Theme theme) {
        List<TemplateManifest.Element> elements = new ArrayList<>();
        elements.add(TemplateManifest.Element.builder()
                .id("default-title").type("text").role("title")
                .x(64).y(44).width(832).height(70).placeholder(true)
                .style(Map.of(
                        "fontFamily", theme.getHeadingFont(),
                        "fontSize", 32,
                        "fontWeight", 700,
                        "color", "#1F2937",
                        "textAlign", "left"
                )).build());
        elements.add(TemplateManifest.Element.builder()
                .id("default-body").type("text").role("body")
                .x(64).y(130).width(832).height(340).placeholder(true)
                .style(Map.of(
                        "fontFamily", theme.getBodyFont(),
                        "fontSize", 18,
                        "fontWeight", 400,
                        "color", "#374151",
                        "textAlign", "left"
                )).build());
        return TemplateManifest.Layout.builder()
                .id("layout-default")
                .name("Title and content")
                .type("content")
                .backgroundColor(theme.getBackgroundColor())
                .elements(elements)
                .build();
    }

    private TemplateManifest.Element copyElement(TemplateManifest.Element source) {
        return TemplateManifest.Element.builder()
                .id(source.getId() + "-copy")
                .type(source.getType())
                .role(source.getRole())
                .x(source.getX()).y(source.getY())
                .width(source.getWidth()).height(source.getHeight())
                .rotation(source.getRotation())
                .placeholder(source.isPlaceholder())
                .locked(source.isLocked())
                .content(source.getContent())
                .src(source.getSrc())
                .fill(source.getFill())
                .borderColor(source.getBorderColor())
                .style(new LinkedHashMap<>(source.getStyle()))
                .build();
    }

    private Document parseXml(byte[] xml) throws Exception {
        DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
        factory.setNamespaceAware(true);
        factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
        factory.setFeature("http://xml.org/sax/features/external-general-entities", false);
        factory.setFeature("http://xml.org/sax/features/external-parameter-entities", false);
        factory.setAttribute(XMLConstants.ACCESS_EXTERNAL_DTD, "");
        factory.setAttribute(XMLConstants.ACCESS_EXTERNAL_SCHEMA, "");
        return factory.newDocumentBuilder().parse(new ByteArrayInputStream(xml));
    }

    private Element firstDescendant(Node root, String localName) {
        if (root instanceof Element element && localName.equals(element.getLocalName())) return element;
        NodeList children = root.getChildNodes();
        for (int index = 0; index < children.getLength(); index++) {
            Element found = firstDescendant(children.item(index), localName);
            if (found != null) return found;
        }
        return null;
    }

    private List<Element> descendants(Node root, String localName) {
        List<Element> result = new ArrayList<>();
        collectDescendants(root, localName, result);
        return result;
    }

    private void collectDescendants(Node root, String localName, List<Element> result) {
        if (root instanceof Element element && localName.equals(element.getLocalName())) result.add(element);
        NodeList children = root.getChildNodes();
        for (int index = 0; index < children.getLength(); index++) {
            collectDescendants(children.item(index), localName, result);
        }
    }

    private List<Element> childElements(Node node) {
        List<Element> result = new ArrayList<>();
        NodeList children = node.getChildNodes();
        for (int index = 0; index < children.getLength(); index++) {
            if (children.item(index) instanceof Element element) result.add(element);
        }
        return result;
    }

    private String colorFromNode(Element node, Map<String, String> themeColors) {
        Element srgb = firstDescendant(node, "srgbClr");
        if (srgb != null && !srgb.getAttribute("val").isBlank()) {
            return "#" + srgb.getAttribute("val").toUpperCase(Locale.ROOT);
        }
        Element system = firstDescendant(node, "sysClr");
        if (system != null) {
            String value = firstNonBlank(system.getAttribute("lastClr"), system.getAttribute("val"));
            if (value != null && value.matches("[0-9A-Fa-f]{6}")) return "#" + value.toUpperCase(Locale.ROOT);
        }
        Element scheme = firstDescendant(node, "schemeClr");
        if (scheme != null) return themeColors.get(scheme.getAttribute("val"));
        return null;
    }

    private String fontFromScheme(Element fontNode, String fallback) {
        if (fontNode == null) return fallback;
        Element latin = firstDescendant(fontNode, "latin");
        return latin == null ? fallback : firstNonBlank(latin.getAttribute("typeface"), fallback);
    }

    private String readText(Element shape) {
        return descendants(shape, "t").stream()
                .map(Element::getTextContent)
                .filter(value -> value != null && !value.isBlank())
                .reduce((left, right) -> left + " " + right)
                .orElse("");
    }

    private boolean hasText(Element shape) {
        return !readText(shape).isBlank();
    }

    private String readTextAlign(Element shape) {
        Element paragraphProperties = firstDescendant(shape, "pPr");
        if (paragraphProperties == null) return "left";
        return switch (paragraphProperties.getAttribute("algn")) {
            case "ctr" -> "center";
            case "r" -> "right";
            case "just", "dist" -> "justify";
            default -> "left";
        };
    }

    private String readVerticalAlign(Element shape) {
        Element bodyProperties = firstDescendant(shape, "bodyPr");
        if (bodyProperties == null) return "top";
        return switch (bodyProperties.getAttribute("anchor")) {
            case "ctr" -> "middle";
            case "b" -> "bottom";
            default -> "top";
        };
    }

    private String roleForPlaceholder(String type) {
        return switch (type) {
            case "title", "ctrTitle" -> "title";
            case "pic", "media" -> "image";
            case "chart" -> "chart";
            case "tbl" -> "table";
            default -> "body";
        };
    }

    private String placeholderKey(TemplateManifest.Element element) {
        return element.getRole();
    }

    private String attributeByLocalName(Element element, String localName) {
        for (int index = 0; index < element.getAttributes().getLength(); index++) {
            Node attribute = element.getAttributes().item(index);
            if (localName.equals(attribute.getLocalName()) || localName.equals(attribute.getNodeName())) {
                return attribute.getNodeValue();
            }
        }
        return "";
    }

    private long longAttr(Element element, String name, long fallback) {
        try {
            String value = element.getAttribute(name);
            return value.isBlank() ? fallback : Long.parseLong(value);
        } catch (NumberFormatException exception) {
            return fallback;
        }
    }

    private double scale(long value, long source, double target) {
        return Math.round((value / (double) source * target) * 100d) / 100d;
    }

    private String aspectRatio(long width, long height) {
        double ratio = width / (double) height;
        if (Math.abs(ratio - 16d / 9d) < 0.04) return "16:9";
        if (Math.abs(ratio - 4d / 3d) < 0.04) return "4:3";
        return String.format(Locale.ROOT, "%.2f:1", ratio);
    }

    private String imageContentType(String path) {
        String lower = path.toLowerCase(Locale.ROOT);
        if (lower.endsWith(".jpg") || lower.endsWith(".jpeg")) return "image/jpeg";
        if (lower.endsWith(".gif")) return "image/gif";
        if (lower.endsWith(".svg")) return "image/svg+xml";
        if (lower.endsWith(".webp")) return "image/webp";
        return "image/png";
    }

    private String firstNonBlank(String... values) {
        for (String value : values) {
            if (value != null && !value.isBlank()) return value;
        }
        return null;
    }

    private String defaultColor(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value;
    }

    private String emptyToNull(String value) {
        return value == null || value.isBlank() ? null : value;
    }

    private static class MasterData {
        private String backgroundColor;
        private final Map<String, TemplateManifest.Element> placeholders = new HashMap<>();
        private final List<TemplateManifest.Element> decorations = new ArrayList<>();
    }

    private record PlaceholderInfo(boolean present, String type, String index, boolean ignore) {
        private static PlaceholderInfo none() {
            return new PlaceholderInfo(false, "", "", false);
        }

        private String key() {
            return index == null || index.isBlank() ? roleKey() : roleKey() + ":" + index;
        }

        private String roleKey() {
            return switch (type) {
                case "title", "ctrTitle" -> "title";
                case "pic", "media" -> "image";
                case "chart" -> "chart";
                case "tbl" -> "table";
                default -> "body";
            };
        }
    }
}
