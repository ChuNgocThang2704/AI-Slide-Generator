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
import java.nio.file.Path;
import java.util.ArrayList;
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
    private static final String DISPLAY_BACKGROUND = "#FFFFFF";

    public record ParsedTemplate(TemplateManifest manifest, Map<String, byte[]> assets) {}

    public TemplateManifest parse(byte[] fileBytes) {
        return parseWithAssets(fileBytes).manifest();
    }

    public ParsedTemplate parseWithAssets(byte[] fileBytes) {
        return parseWithAssets(fileBytes, false);
    }

    /**
     * @param keepContent false (the default, used when a file is uploaded purely as a visual
     *                     template): each real slide's title/body text is blanked to an empty,
     *                     reusable placeholder, and only one representative picture is kept.
     *                     true (used to open a real deck for editing, see TemplateService#importSlides):
     *                     every text box keeps its real words and every picture/shape is kept, so
     *                     each returned "layout" is a faithful, 1-to-1 copy of that real slide.
     */
    public ParsedTemplate parseWithAssets(byte[] fileBytes, boolean keepContent) {
        Map<String, byte[]> assetsOut = new LinkedHashMap<>();
        try {
            Map<String, byte[]> entries = unzip(fileBytes);
            if (!entries.containsKey("ppt/presentation.xml")) {
                throw new CustomException(ErrorCode.INVALID_TEMPLATE_FILE);
            }

            long[] pageSize = readPageSize(entries.get("ppt/presentation.xml"));
            TemplateManifest.Theme theme = readTheme(entries);
            MasterData master = readMaster(entries, pageSize, theme);
            List<TemplateManifest.Layout> sampleLayouts = readSampleLayouts(entries, pageSize, theme, assetsOut, keepContent, master);
            List<TemplateManifest.Layout> layouts = sampleLayouts.isEmpty()
                    ? readLayouts(entries, pageSize, theme, master)
                    : sampleLayouts;
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

            TemplateManifest manifest = TemplateManifest.builder()
                    .width(960)
                    .height(540)
                    .aspectRatio(aspectRatio(pageSize[0], pageSize[1]))
                    .theme(theme)
                    .layouts(layouts)
                    .build();
            assetsOut.keySet().forEach(name -> manifest.getAssets().put(name, contentTypeFor(name)));
            return new ParsedTemplate(manifest, assetsOut);
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

                boolean keepEntry = !name.startsWith("ppt/media/") || isRasterMedia(name);
                ByteArrayOutputStream output = keepEntry ? new ByteArrayOutputStream() : null;
                byte[] buffer = new byte[8192];
                int read;
                long entrySize = 0;
                while ((read = zip.read(buffer)) >= 0) {
                    entrySize += read;
                    total += read;
                    if (entrySize > MAX_ENTRY_BYTES || total > MAX_UNCOMPRESSED_BYTES) {
                        throw new CustomException(ErrorCode.INVALID_TEMPLATE_FILE);
                    }
                    if (output != null && name.startsWith("ppt/media/") && entrySize > MAX_ASSET_BYTES) output = null;
                    if (output != null) output.write(buffer, 0, read);
                }
                if (output != null) entries.put(name, output.toByteArray());
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
        theme.getColors().put("bg1", theme.getBackgroundColor());
        theme.getColors().put("tx1", defaultColor(theme.getColors().get("dk1"), "#000000"));
        theme.getColors().put("bg2", defaultColor(theme.getColors().get("lt2"), theme.getBackgroundColor()));
        theme.getColors().put("tx2", defaultColor(theme.getColors().get("dk2"), theme.getColors().get("tx1")));

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
        MasterData result = new MasterData();
        List<TemplateManifest.Element> shapes = parseShapeTree(
                document, pageSize, theme, Map.of()
        );
        for (TemplateManifest.Element shape : shapes) {
            if (shape.isPlaceholder()) {
                result.placeholders.put(placeholderKey(shape), shape);
                result.placeholders.putIfAbsent(shape.getRole(), shape);
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
            List<TemplateManifest.Element> ownElements = parseShapeTree(
                    document, pageSize, theme, master.placeholders
            );
            List<TemplateManifest.Element> elements = new ArrayList<>();
            ownElements.stream()
                    .filter(TemplateManifest.Element::isPlaceholder)
                    .forEach(elements::add);

            layouts.add(TemplateManifest.Layout.builder()
                    .id("layout-" + (++index))
                    .name(name)
                    .type(classifyLayout(name, elements))
                    .backgroundColor(DISPLAY_BACKGROUND)
                    .elements(elements)
                    .build());
        }
        return layouts;
    }

    private List<TemplateManifest.Layout> readSampleLayouts(
            Map<String, byte[]> entries,
            long[] pageSize,
            TemplateManifest.Theme theme,
            Map<String, byte[]> assetsOut,
            boolean keepContent,
            MasterData master
    ) throws Exception {
        List<String> paths = entries.keySet().stream()
                .filter(name -> name.startsWith("ppt/slides/slide") && name.endsWith(".xml"))
                .sorted(Comparator.comparingInt(this::partNumber))
                .toList();
        List<TemplateManifest.Layout> layouts = new ArrayList<>();
        int index = 0;
        for (String path : paths) {
            Document document = parseXml(entries.get(path));
            // A real deck's own words live in its placeholders, and most of those boxes carry no
            // position of their own: they sit wherever the slide's layout puts them.
            Map<String, TemplateManifest.Element> layoutPlaceholders = keepContent
                    ? readLayoutPlaceholders(entries, path, pageSize, theme, master)
                    : Map.of();
            List<TemplateManifest.Element> elements = normalizeSampleElements(parseShapeTree(
                    document, pageSize, theme, layoutPlaceholders, keepContent, null
            ), keepContent);

            if (elements.isEmpty() && !keepContent) continue;

            String layoutType = layouts.isEmpty() ? "title" : classifyLayout("Sample slide", elements);
            SlideVisuals visuals = extractVisuals(path, document, entries, pageSize, theme, assetsOut);
            layouts.add(TemplateManifest.Layout.builder()
                    .id("sample-layout-" + (++index))
                    .name("Sample slide " + index)
                    .type(layoutType)
                    .backgroundColor(visuals.averageColor() == null ? DISPLAY_BACKGROUND : visuals.averageColor())
                    .background(visuals.background())
                    .elements(elements)
                    .decor(visuals.decor())
                    .build());
        }
        return layouts;
    }

    private List<TemplateManifest.Element> normalizeSampleElements(List<TemplateManifest.Element> source, boolean keepContent) {
        List<TemplateManifest.Element> visibleElements = source.stream()
                .filter(this::intersectsCanvas)
                .toList();
        List<TemplateManifest.Element> textElements = visibleElements.stream()
                .filter(item -> "text".equals(item.getType()))
                .toList();
        TemplateManifest.Element title = textElements.stream()
                .max(Comparator
                        .comparingDouble(this::fontSize)
                        .thenComparingDouble(item -> item.getWidth() * item.getHeight())
                        .thenComparingDouble(item -> -item.getY()))
                .orElse(null);

        // Opening a real deck: keep every real word, in its real box. Its pictures and plain
        // shapes are already captured faithfully as this layout's `decor` (extractVisuals /
        // collectVisuals resolve every one of them, not just a single representative one), so
        // they're dropped here rather than duplicated as a second, blanked copy.
        if (keepContent) {
            return textElements.stream()
                    .filter(element -> !String.valueOf(element.getContent()).isBlank())
                    .map(element -> {
                        TemplateManifest.Element copy = copyElement(element);
                        copy.setRole(element == title ? "title" : "body");
                        copy.setPlaceholder(false);
                        copy.setLocked(false);
                        return copy;
                    })
                    .toList();
        }

        TemplateManifest.Element imagePlaceholder = visibleElements.stream()
                .filter(item -> "image".equals(item.getType()))
                .filter(item -> !isBackgroundLike(item))
                .max(Comparator
                        .comparing(TemplateManifest.Element::isPlaceholder)
                        .thenComparingDouble(item -> item.getWidth() * item.getHeight()))
                .orElse(null);

        List<TemplateManifest.Element> normalized = new ArrayList<>();
        for (TemplateManifest.Element element : visibleElements) {
            if ("image".equals(element.getType())) {
                if (element != imagePlaceholder) continue;
                TemplateManifest.Element placeholder = copyElement(element);
                placeholder.setRole("image");
                placeholder.setPlaceholder(true);
                placeholder.setLocked(false);
                placeholder.setContent(null);
                placeholder.setSrc(null);
                normalized.add(placeholder);
                continue;
            }
            if ("shape".equals(element.getType())) continue;
            if (!"text".equals(element.getType())) {
                normalized.add(element);
                continue;
            }
            TemplateManifest.Element placeholder = copyElement(element);
            placeholder.setRole(element == title ? "title" : "body");
            placeholder.setPlaceholder(true);
            placeholder.setLocked(false);
            placeholder.setContent("");
            normalized.add(placeholder);
        }
        return normalized;
    }

    private boolean isBackgroundLike(TemplateManifest.Element element) {
        double area = element.getWidth() * element.getHeight();
        boolean coversCanvas = element.getX() <= 16 && element.getY() <= 16
                && element.getX() + element.getWidth() >= 944
                && element.getY() + element.getHeight() >= 524;
        return coversCanvas || area >= 960d * 540d * 0.85;
    }

    private boolean intersectsCanvas(TemplateManifest.Element element) {
        return element.getX() < 960 && element.getY() < 540
                && element.getX() + element.getWidth() > 0
                && element.getY() + element.getHeight() > 0;
    }

    private double fontSize(TemplateManifest.Element element) {
        Object value = element.getStyle() == null ? null : element.getStyle().get("fontSize");
        return value instanceof Number number ? number.doubleValue() : 0;
    }

    private List<TemplateManifest.Element> parseShapeTree(
            Document document,
            long[] pageSize,
            TemplateManifest.Theme theme,
            Map<String, TemplateManifest.Element> inheritedPlaceholders
    ) {
        return parseShapeTree(document, pageSize, theme, inheritedPlaceholders, false, null);
    }

    /**
     * @param keepText whether a placeholder's own text is read. A template wants its placeholders
     *                 blank; a deck being opened wants every word in them, since PowerPoint puts
     *                 titles and body text there.
     * @param placeholdersOut when given, receives each placeholder by its key (type and index), so
     *                        a slide can later find the layout placeholder it inherits from
     */
    private List<TemplateManifest.Element> parseShapeTree(
            Document document,
            long[] pageSize,
            TemplateManifest.Theme theme,
            Map<String, TemplateManifest.Element> inheritedPlaceholders,
            boolean keepText,
            Map<String, TemplateManifest.Element> placeholdersOut
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
            boolean hasImageFill = firstDescendant(shape, "blip") != null;
            if ("pic".equals(kind) || hasImageFill || "image".equals(role)) {
                elementType = "image";
                role = "image";
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
            String content = placeholder.present && !keepText ? "" : readTextHtml(shape, role);

            TemplateManifest.Element built = TemplateManifest.Element.builder()
                    .id("tpl-" + sequence++ + "-" + UUID.randomUUID().toString().substring(0, 8))
                    .type(elementType)
                    .role(role)
                    .x(anchor[0])
                    .y(anchor[1])
                    .width(anchor[2])
                    .height(anchor[3])
                    .rotation(readRotation(shape))
                    .opacity(readFillOpacity(shape))
                    .placeholder(placeholder.present)
                    .locked(!placeholder.present)
                    .content(content)
                    .fill(fill)
                    .borderColor(border)
                    .style(style)
                    .build();
            result.add(built);
            if (placeholdersOut != null && placeholder.present) {
                placeholdersOut.put(placeholder.key(), built);
                placeholdersOut.putIfAbsent(role, built);
            }
        }
        return result;
    }

    /** The placeholders of the layout a slide uses, by key, for the slide to inherit position and style from. */
    private Map<String, TemplateManifest.Element> readLayoutPlaceholders(
            Map<String, byte[]> entries,
            String slidePath,
            long[] pageSize,
            TemplateManifest.Theme theme,
            MasterData master
    ) {
        Map<String, TemplateManifest.Element> placeholders = new HashMap<>();
        String layoutPath = readRelationships(entries, slidePath).values().stream()
                .filter(target -> target.startsWith("ppt/slideLayouts/"))
                .findFirst().orElse(null);
        if (layoutPath == null || !entries.containsKey(layoutPath)) return placeholders;
        try {
            parseShapeTree(parseXml(entries.get(layoutPath)), pageSize, theme, master.placeholders, false, placeholders);
        } catch (Exception exception) {
            log.debug("Cannot read layout placeholders of {}: {}", slidePath, exception.getMessage());
        }
        return placeholders;
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

    private String readShapeFill(Element shape, TemplateManifest.Theme theme) {
        Element shapeProperties = firstDescendant(shape, "spPr");
        if (shapeProperties == null) return null;
        Element solidFill = firstDescendant(shapeProperties, "solidFill");
        return solidFill == null ? null : colorFromNode(solidFill, theme.getColors());
    }

    private Double readFillOpacity(Element shape) {
        Element shapeProperties = firstDescendant(shape, "spPr");
        if (shapeProperties == null) return null;
        Element solidFill = firstDescendant(shapeProperties, "solidFill");
        Element alpha = solidFill == null ? null : firstDescendant(solidFill, "alpha");
        if (alpha == null) return null;
        double opacity = longAttr(alpha, "val", 100_000) / 100_000d;
        return Math.max(0, Math.min(1, opacity));
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

    private int partNumber(String path) {
        String fileName = Path.of(path).getFileName().toString();
        String digits = fileName.replaceAll("\\D+", "");
        try {
            return digits.isBlank() ? Integer.MAX_VALUE : Integer.parseInt(digits);
        } catch (NumberFormatException exception) {
            return Integer.MAX_VALUE;
        }
    }

    private String classifyLayout(String name, List<TemplateManifest.Element> elements) {
        String normalized = name.toLowerCase(Locale.ROOT);
        if (normalized.matches(".*(title slide|cover|trang bìa|bìa).*")) return "title";
        if (normalized.matches(".*(thank|closing|end|kết thúc).*")) return "thankyou";
        if (normalized.matches(".*(two|comparison|2 content|hai cột).*")) return "twoColumn";
        if (normalized.matches(".*(picture|image|photo|ảnh).*")) return "imageText";
        if (normalized.contains("chart")) return "chart";
        if (normalized.contains("table")) return "table";

        // Not gated on isPlaceholder(): a faithfully-imported slide's elements (see
        // normalizeSampleElements' keepContent branch) are real, unlocked content, not
        // reusable placeholders, but they still carry the same role classification did.
        long bodies = elements.stream().filter(item -> "body".equals(item.getRole())).count();
        boolean image = elements.stream().anyMatch(item -> "image".equals(item.getRole()));
        boolean chart = elements.stream().anyMatch(item -> "chart".equals(item.getRole()));
        boolean table = elements.stream().anyMatch(item -> "table".equals(item.getRole()));
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
                .backgroundColor(DISPLAY_BACKGROUND)
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
                .opacity(source.getOpacity())
                .placeholder(source.isPlaceholder())
                .locked(source.isLocked())
                .content(source.getContent())
                .src(source.getSrc())
                .fill(source.getFill())
                .borderColor(source.getBorderColor())
                .style(new LinkedHashMap<>(source.getStyle()))
                .build();
    }

    /* ───────────── backgrounds, pictures and shapes of a sample slide ───────────── */

    private static final long MAX_ASSET_BYTES = 6L * 1024 * 1024;
    private static final int MAX_DECOR = 40;
    private static final String REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships";

    private record SlideVisuals(String background, String averageColor, List<TemplateManifest.Element> decor) {}

    private record Fill(String css, String averageColor) {}

    private static boolean isRasterMedia(String name) {
        String lower = name.toLowerCase(Locale.ROOT);
        return lower.endsWith(".png") || lower.endsWith(".jpg") || lower.endsWith(".jpeg")
                || lower.endsWith(".webp") || lower.endsWith(".gif");
    }

    public static String contentTypeFor(String name) {
        String lower = name.toLowerCase(Locale.ROOT);
        if (lower.endsWith(".png")) return "image/png";
        if (lower.endsWith(".jpg") || lower.endsWith(".jpeg")) return "image/jpeg";
        if (lower.endsWith(".webp")) return "image/webp";
        if (lower.endsWith(".gif")) return "image/gif";
        return "application/octet-stream";
    }

    private SlideVisuals extractVisuals(
            String slidePath,
            Document slide,
            Map<String, byte[]> entries,
            long[] pageSize,
            TemplateManifest.Theme theme,
            Map<String, byte[]> assetsOut
    ) {
        List<TemplateManifest.Element> decor = new ArrayList<>();
        try {
            Fill background = backgroundChain(slidePath, entries, theme, decor, assetsOut, 0);
            Element tree = firstDescendant(slide.getDocumentElement(), "spTree");
            if (tree != null) {
                List<double[]> textRects = new ArrayList<>();
                collectVisuals(tree, new double[]{1, 0, 1, 0}, readRelationships(entries, slidePath),
                        pageSize, theme, entries, assetsOut, decor, textRects);
                // A pill, label or button behind the sample's own text is meaningless once that text is gone.
                decor.removeIf(art -> !"background".equals(art.getRole())
                        && art.getWidth() * art.getHeight() < 0.12 * 960 * 540
                        && textRects.stream().anyMatch(rect -> mostlyInside(rect, art)));
            }
            return new SlideVisuals(
                    background == null ? null : background.css(),
                    background == null ? null : background.averageColor(),
                    decor);
        } catch (Exception exception) {
            log.warn("Cannot read visuals of {}: {}", slidePath, exception.getMessage());
            return new SlideVisuals(null, null, List.of());
        }
    }

    /** Relationship id -> package path of the target, for one part. */
    private Map<String, String> readRelationships(Map<String, byte[]> entries, String partPath) {
        Map<String, String> result = new HashMap<>();
        int slash = partPath.lastIndexOf('/');
        String dir = partPath.substring(0, slash + 1);
        byte[] xml = entries.get(dir + "_rels/" + partPath.substring(slash + 1) + ".rels");
        if (xml == null) return result;
        try {
            for (Element rel : descendants(parseXml(xml).getDocumentElement(), "Relationship")) {
                String target = rel.getAttribute("Target");
                if (target.isBlank() || "External".equals(rel.getAttribute("TargetMode"))) continue;
                result.put(rel.getAttribute("Id"), normalizePartPath(dir, target));
            }
        } catch (Exception exception) {
            log.debug("Cannot read relationships of {}", partPath);
        }
        return result;
    }

    private String normalizePartPath(String dir, String target) {
        String joined = target.startsWith("/") ? target.substring(1) : dir + target;
        java.util.ArrayDeque<String> parts = new java.util.ArrayDeque<>();
        for (String part : joined.split("/")) {
            if (part.isEmpty() || ".".equals(part)) continue;
            if ("..".equals(part)) {
                if (!parts.isEmpty()) parts.removeLast();
            } else {
                parts.addLast(part);
            }
        }
        return String.join("/", parts);
    }

    /** Slide background, falling back to its layout and then its master. */
    private Fill backgroundChain(
            String partPath,
            Map<String, byte[]> entries,
            TemplateManifest.Theme theme,
            List<TemplateManifest.Element> decor,
            Map<String, byte[]> assetsOut,
            int depth
    ) throws Exception {
        if (partPath == null || depth > 3 || !entries.containsKey(partPath)) return null;
        Document part = parseXml(entries.get(partPath));
        Map<String, String> rels = readRelationships(entries, partPath);
        Element props = firstDescendant(part.getDocumentElement(), "bgPr");
        if (props != null) {
            Fill fill = fillOf(props, theme);
            if (fill != null) return fill;
            Element picture = firstChild(props, "blipFill");
            Element blip = picture == null ? null : firstDescendant(picture, "blip");
            String asset = blip == null ? null : registerAsset(rels.get(blip.getAttributeNS(REL_NS, "embed")), entries, assetsOut);
            if (asset != null) {
                decor.add(0, imageElement("bg", asset, 0, 0, 960, 540, 0, Map.of()));
                return new Fill(null, null);
            }
        }
        if (partPath.startsWith("ppt/slideMasters/")) return null;
        String next = rels.values().stream()
                .filter(target -> target.startsWith("ppt/slideLayouts/") || target.startsWith("ppt/slideMasters/"))
                .findFirst().orElse(null);
        return backgroundChain(next, entries, theme, decor, assetsOut, depth + 1);
    }

    private boolean mostlyInside(double[] text, TemplateManifest.Element art) {
        double left = Math.max(text[0], art.getX());
        double top = Math.max(text[1], art.getY());
        double right = Math.min(text[0] + text[2], art.getX() + art.getWidth());
        double bottom = Math.min(text[1] + text[3], art.getY() + art.getHeight());
        if (right <= left || bottom <= top) return false;
        return (right - left) * (bottom - top) >= 0.6 * text[2] * text[3];
    }

    private Element firstChild(Element parent, String localName) {
        if (parent == null) return null;
        for (Element child : childElements(parent)) {
            if (localName.equals(child.getLocalName())) return child;
        }
        return null;
    }

    /** Solid or gradient fill that is a direct child of the given properties node. */
    private Fill fillOf(Element props, TemplateManifest.Theme theme) {
        Element solid = firstChild(props, "solidFill");
        if (solid != null) {
            String color = colorFromNode(solid, theme.getColors());
            if (color == null) return null;
            Element alpha = firstDescendant(solid, "alpha");
            double opacity = alpha == null ? 1 : longAttr(alpha, "val", 100_000) / 100_000d;
            return new Fill(cssColor(color, opacity), color);
        }
        Element gradient = firstChild(props, "gradFill");
        return gradient == null ? null : gradientFill(gradient, theme);
    }

    private Fill gradientFill(Element gradient, TemplateManifest.Theme theme) {
        Element list = firstChild(gradient, "gsLst");
        if (list == null) return null;
        List<String> stops = new ArrayList<>();
        double red = 0;
        double green = 0;
        double blue = 0;
        int counted = 0;
        for (Element stop : childElements(list)) {
            String color = colorFromNode(stop, theme.getColors());
            if (color == null) continue;
            Element alpha = firstDescendant(stop, "alpha");
            double opacity = alpha == null ? 1 : longAttr(alpha, "val", 100_000) / 100_000d;
            stops.add(cssColor(color, opacity) + " " + trimNumber(longAttr(stop, "pos", 0) / 1000d) + "%");
            int rgb = Integer.parseInt(color.substring(1), 16);
            red += (rgb >> 16) & 255;
            green += (rgb >> 8) & 255;
            blue += rgb & 255;
            counted++;
        }
        if (counted == 0) return null;
        String average = String.format("#%02X%02X%02X", Math.round(red / counted), Math.round(green / counted), Math.round(blue / counted));
        if (stops.size() == 1) return new Fill(stops.get(0).replaceAll(" [0-9.]+%$", ""), average);
        String joined = String.join(", ", stops);
        if (firstChild(gradient, "path") != null) {
            return new Fill("radial-gradient(circle at 50% 50%, " + joined + ")", average);
        }
        Element linear = firstChild(gradient, "lin");
        double angle = linear == null ? 90 : longAttr(linear, "ang", 0) / 60_000d;
        // OOXML measures 0deg as left-to-right; CSS measures 90deg that way.
        return new Fill("linear-gradient(" + trimNumber((angle + 90) % 360) + "deg, " + joined + ")", average);
    }

    private String cssColor(String hex, double opacity) {
        if (opacity >= 0.999) return hex;
        int rgb = Integer.parseInt(hex.substring(1), 16);
        return "rgba(" + ((rgb >> 16) & 255) + ", " + ((rgb >> 8) & 255) + ", " + (rgb & 255) + ", " + trimNumber(opacity) + ")";
    }

    private String trimNumber(double value) {
        return String.format(Locale.ROOT, "%.2f", value).replaceAll("0+$", "").replaceAll("\\.$", "");
    }

    private String registerAsset(String path, Map<String, byte[]> entries, Map<String, byte[]> assetsOut) {
        if (path == null || !path.startsWith("ppt/media/") || !isRasterMedia(path)) return null;
        byte[] bytes = entries.get(path);
        if (bytes == null) return null;
        String name = Path.of(path).getFileName().toString().replaceAll("[^A-Za-z0-9._-]", "_");
        assetsOut.putIfAbsent(name, bytes);
        return name;
    }

    private TemplateManifest.Element imageElement(
            String id, String asset, double x, double y, double width, double height, double rotation, Map<String, Object> style
    ) {
        return TemplateManifest.Element.builder()
                .id("decor-" + id)
                .type("image")
                .role("decoration")
                .x(x).y(y).width(width).height(height)
                .rotation(rotation)
                .locked(true)
                .src("asset:" + asset)
                .style(new LinkedHashMap<>(style))
                .build();
    }

    /** Child-space to slide-space mapping of a group: X = a * x + b (and the same for Y). */
    private double[] groupTransform(Element group, double[] parent) {
        Element properties = firstChild(group, "grpSpPr");
        Element transform = properties == null ? null : firstChild(properties, "xfrm");
        if (transform == null) return parent;
        Element offset = firstChild(transform, "off");
        Element extent = firstChild(transform, "ext");
        Element childOffset = firstChild(transform, "chOff");
        Element childExtent = firstChild(transform, "chExt");
        if (offset == null || extent == null || childOffset == null || childExtent == null) return parent;
        double childW = longAttr(childExtent, "cx", 0);
        double childH = longAttr(childExtent, "cy", 0);
        if (childW <= 0 || childH <= 0) return parent;
        double sx = longAttr(extent, "cx", 0) / childW;
        double sy = longAttr(extent, "cy", 0) / childH;
        double tx = longAttr(offset, "x", 0) - longAttr(childOffset, "x", 0) * sx;
        double ty = longAttr(offset, "y", 0) - longAttr(childOffset, "y", 0) * sy;
        return new double[]{parent[0] * sx, parent[0] * tx + parent[1], parent[2] * sy, parent[2] * ty + parent[3]};
    }

    private void collectVisuals(
            Element container,
            double[] tf,
            Map<String, String> rels,
            long[] pageSize,
            TemplateManifest.Theme theme,
            Map<String, byte[]> entries,
            Map<String, byte[]> assetsOut,
            List<TemplateManifest.Element> out,
            List<double[]> textRects
    ) {
        for (Element node : childElements(container)) {
            if (out.size() >= MAX_DECOR) return;
            String kind = node.getLocalName();
            if ("grpSp".equals(kind)) {
                collectVisuals(node, groupTransform(node, tf), rels, pageSize, theme, entries, assetsOut, out, textRects);
                continue;
            }
            if (!"sp".equals(kind) && !"pic".equals(kind)) continue;
            Element nonVisual = firstDescendant(node, "cNvPr");
            if (nonVisual != null && "1".equals(nonVisual.getAttribute("hidden"))) continue;
            Element properties = firstChild(node, "spPr");
            Element transform = properties == null ? null : firstChild(properties, "xfrm");
            Element offset = firstChild(transform, "off");
            Element extent = firstChild(transform, "ext");
            if (offset == null || extent == null) continue;

            double x = (tf[0] * longAttr(offset, "x", 0) + tf[1]) / pageSize[0] * 960;
            double y = (tf[2] * longAttr(offset, "y", 0) + tf[3]) / pageSize[1] * 540;
            double width = tf[0] * longAttr(extent, "cx", 0) / pageSize[0] * 960;
            double height = tf[2] * longAttr(extent, "cy", 0) / pageSize[1] * 540;
            if (width < 3 || height < 3 || x > 960 || y > 540 || x + width < 0 || y + height < 0) continue;

            boolean textBox = "sp".equals(kind) && firstChild(properties, "blipFill") == null
                    && (firstDescendant(node, "ph") != null || hasText(node));
            if (textBox) {
                textRects.add(new double[]{x, y, width, height});
                continue;
            }
            if (firstDescendant(node, "ph") != null) continue; // picture placeholders are filled by the app
            // Small marks away from the slide edge (logos, brand stamps) would land on top of the text.
            boolean smallMark = width * height < 4_500;
            boolean nearEdge = x < 48 || y < 48 || x + width > 960 - 48 || y + height > 540 - 48;
            if (smallMark && !nearEdge) continue;

            Element geometry = firstChild(properties, "prstGeom");
            String preset = geometry == null ? "rect" : geometry.getAttribute("prst");
            Map<String, Object> style = new LinkedHashMap<>();
            if ("1".equals(transform.getAttribute("flipH"))) style.put("flipX", true);
            if ("1".equals(transform.getAttribute("flipV"))) style.put("flipY", true);
            if ("ellipse".equals(preset)) style.put("borderRadius", "50%");
            if ("roundRect".equals(preset)) style.put("borderRadius", "12px");
            double rotation = longAttr(transform, "rot", 0) / 60_000d;
            String id = "d" + out.size() + "-" + UUID.randomUUID().toString().substring(0, 6);

            Element pictureFill = "pic".equals(kind) ? firstChild(node, "blipFill") : firstChild(properties, "blipFill");
            if (pictureFill != null) {
                Element blip = firstDescendant(pictureFill, "blip");
                String asset = blip == null ? null : registerAsset(rels.get(blip.getAttributeNS(REL_NS, "embed")), entries, assetsOut);
                if (asset == null) continue;
                Element crop = firstChild(pictureFill, "srcRect");
                if (crop != null) {
                    style.put("cropL", longAttr(crop, "l", 0) / 100_000d);
                    style.put("cropT", longAttr(crop, "t", 0) / 100_000d);
                    style.put("cropR", longAttr(crop, "r", 0) / 100_000d);
                    style.put("cropB", longAttr(crop, "b", 0) / 100_000d);
                }
                out.add(imageElement(id, asset, x, y, width, height, rotation, style));
                continue;
            }

            // Shapes: PowerPoint presets the editor has a matching shape for, filled and/or outlined.
            // Custom outlines (freeform paths) have no equivalent here and would render as wrong rectangles.
            String shapeId = SHAPE_PRESETS.get(preset);
            if (hasText(node) || shapeId == null) continue;
            Fill fill = fillOf(properties, theme);
            String fillCss = fill == null ? null : fill.css();
            String lineColor = readLineColor(node, theme);
            Element line = firstDescendant(properties, "ln");
            double lineWidth = line == null ? 0 : longAttr(line, "w", 0) / 12_700d * (960d / (pageSize[0] / 12_700d));
            boolean outlined = lineColor != null && lineWidth > 0;
            if (fillCss == null && !outlined) continue;
            style.put("shape", shapeId);
            if (outlined) style.put("borderWidth", Math.max(1, Math.round(lineWidth * 10) / 10d));
            out.add(TemplateManifest.Element.builder()
                    .id("decor-" + id)
                    .type("shape")
                    .role("decoration")
                    .x(x).y(y).width(width).height(height)
                    .rotation(rotation)
                    .locked(true)
                    .fill(fillCss == null ? "transparent" : fillCss)
                    .borderColor(outlined ? lineColor : null)
                    .style(style)
                    .build());
        }
    }

    /** PowerPoint preset geometry -> the editor's own shape id (see front-end utils/shapeLibrary). */
    private static final Map<String, String> SHAPE_PRESETS = Map.ofEntries(
            Map.entry("rect", "rect"),
            Map.entry("roundRect", "roundRect"),
            Map.entry("ellipse", "ellipse"),
            Map.entry("triangle", "triangle"),
            Map.entry("diamond", "diamond"),
            Map.entry("star5", "star"),
            Map.entry("rightArrow", "arrowRight"),
            Map.entry("chevron", "chevron"),
            Map.entry("homePlate", "chevron")
    );

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

    /**
     * The real text of a shape, one editor-ready HTML paragraph per PowerPoint paragraph
     * (`<a:p>`), instead of `readText`'s single flattened line — so a real deck opened for
     * editing keeps its bullets as actual bullets (and step 4's "reveal one at a time" has
     * bullets to reveal), not one run-on sentence. Titles stay plain paragraphs; body/custom
     * text becomes a bulleted list when it has more than one paragraph, matching how most
     * placeholders are actually used.
     */
    private String readTextHtml(Element shape, String role) {
        List<String> paragraphs = descendants(shape, "p").stream()
                .map(paragraph -> descendants(paragraph, "t").stream()
                        .map(Element::getTextContent)
                        .filter(value -> value != null && !value.isEmpty())
                        .reduce((left, right) -> left + right)
                        .orElse(""))
                .filter(text -> !text.isBlank())
                .map(this::escapeHtml)
                .toList();
        if (paragraphs.isEmpty()) return "";
        if ("title".equals(role) || paragraphs.size() == 1) {
            return paragraphs.stream().map(text -> "<p>" + text + "</p>").reduce("", String::concat);
        }
        return "<ul>" + paragraphs.stream().map(text -> "<li>" + text + "</li>").reduce("", String::concat) + "</ul>";
    }

    private String escapeHtml(String value) {
        return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;");
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
        private final Map<String, TemplateManifest.Element> placeholders = new HashMap<>();
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
