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
            PptxTextStyles textStyles = keepContent ? buildTextStyles(entries, theme) : null;
            List<TemplateManifest.Layout> sampleLayouts = readSampleLayouts(
                    entries, pageSize, theme, assetsOut, keepContent, master, textStyles);
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
            MasterData master,
            PptxTextStyles textStyles
    ) throws Exception {
        Map<String, Element> trees = new HashMap<>();
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
            TextContext textContext = keepContent ? textContextFor(entries, path, pageSize, textStyles, trees) : null;
            List<TemplateManifest.Element> elements = normalizeSampleElements(parseShapeTree(
                    document, pageSize, theme, layoutPlaceholders, keepContent, null, textContext
            ), keepContent);

            if (elements.isEmpty() && !keepContent) continue;

            String layoutType = layouts.isEmpty() ? "title" : classifyLayout("Sample slide", elements);
            SlideVisuals visuals = extractVisuals(path, document, entries, pageSize, theme, assetsOut, keepContent);
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
                .filter(item -> !"pageNumber".equals(item.getRole()))
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
            List<TemplateManifest.Element> tables = visibleElements.stream()
                    .filter(item -> "table".equals(item.getType()) && item.getData() != null)
                    .map(item -> {
                        TemplateManifest.Element copy = copyElement(item);
                        copy.setPlaceholder(false);
                        copy.setLocked(false);
                        return copy;
                    })
                    .toList();
            List<TemplateManifest.Element> kept = textElements.stream()
                    .filter(element -> !String.valueOf(element.getContent()).isBlank())
                    .map(element -> {
                        TemplateManifest.Element copy = copyElement(element);
                        copy.setRole("pageNumber".equals(element.getRole()) ? "pageNumber"
                                : element == title ? "title" : "body");
                        copy.setPlaceholder(false);
                        copy.setLocked(false);
                        return copy;
                    })
                    .toList();
            return java.util.stream.Stream.concat(kept.stream(), tables.stream()).toList();
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
        return parseShapeTree(document, pageSize, theme, inheritedPlaceholders, false, null, null);
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
            Map<String, TemplateManifest.Element> placeholdersOut,
            TextContext textContext
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
            // A deck being opened keeps its slide numbers (as the editor's own page-number boxes);
            // a template keeps none, and date, footer and header are never kept.
            boolean slideNumber = "sldNum".equals(placeholder.type) && (keepText || placeholdersOut != null);
            if (slideNumber) role = "pageNumber";
            if (placeholder.ignore && !slideNumber) continue;
            TemplateManifest.Element inherited = inheritedPlaceholders.getOrDefault(
                    placeholder.key(), inheritedPlaceholders.get(role)
            );
            double[] anchor = readAnchor(shape, pageSize);
            if (anchor == null && inherited != null) {
                anchor = new double[]{inherited.getX(), inherited.getY(), inherited.getWidth(), inherited.getHeight()};
            }
            if (anchor == null) continue;

            String elementType = "text";
            Map<String, Object> tableData = null;
            boolean hasImageFill = firstDescendant(shape, "blip") != null;
            if ("pic".equals(kind) || hasImageFill || "image".equals(role)) {
                elementType = "image";
                role = "image";
            } else if ("graphicFrame".equals(kind)) {
                tableData = keepText ? readTable(shape, theme, pageSize) : null;
                if (tableData != null) role = "table";
                elementType = tableData != null ? "table" : switch (role) {
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
            // A table's words live in its cells (tableData), not in a text box of their own.
            RichText rich = keepText && textContext != null && tableData == null && elementType.equals("text")
                    ? readRichText(shape, role, placeholder, textContext) : null;
            String content = tableData != null || (placeholder.present && !keepText) ? ""
                    : rich != null ? rich.html() : readTextHtml(shape, role);
            if (rich != null) style.putAll(rich.style());
            if (keepText && textContext != null && tableData == null && elementType.equals("text")) {
                style.putAll(boxLook(shape, placeholder.present, theme, pageSize));
            }

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
                    .data(tableData)
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

    /**
     * The cells of a PowerPoint table, in the shape the editor's tables use: the first row as the
     * headers, the rest as rows, and the columns' relative widths. Null when the frame holds no table.
     */
    private Map<String, Object> readTable(Element frame, TemplateManifest.Theme theme, long[] pageSize) {
        Element table = firstDescendant(frame, "tbl");
        if (table == null) return null;
        List<List<String>> grid = new ArrayList<>();
        List<List<Map<String, Object>>> looks = new ArrayList<>();
        for (Element row : descendants(table, "tr")) {
            List<String> cells = new ArrayList<>();
            List<Map<String, Object>> rowLooks = new ArrayList<>();
            for (Element cell : childElements(row)) {
                if (!"tc".equals(cell.getLocalName())) continue;
                cells.add(cellText(cell));
                rowLooks.add(cellLook(cell, theme, pageSize));
            }
            if (!cells.isEmpty()) {
                grid.add(cells);
                looks.add(rowLooks);
            }
        }
        if (grid.isEmpty()) return null;

        int columns = grid.get(0).size();
        List<List<String>> normalized = new ArrayList<>();
        for (List<String> row : grid) {
            List<String> padded = new ArrayList<>(row.subList(0, Math.min(columns, row.size())));
            while (padded.size() < columns) padded.add("");
            normalized.add(padded);
        }
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("headers", normalized.get(0));
        data.put("rows", new ArrayList<>(normalized.subList(1, normalized.size())));
        List<Map<String, Object>> headerLooks = new ArrayList<>();
        List<List<Map<String, Object>>> cellLooks = new ArrayList<>();
        boolean styled = false;
        for (int rowIndex = 0; rowIndex < looks.size(); rowIndex++) {
            List<Map<String, Object>> padded = new ArrayList<>();
            for (int column = 0; column < columns; column++) {
                Map<String, Object> look = column < looks.get(rowIndex).size() ? looks.get(rowIndex).get(column) : new LinkedHashMap<>();
                if (!look.isEmpty()) styled = true;
                padded.add(look);
            }
            if (rowIndex == 0) headerLooks = padded;
            else cellLooks.add(padded);
        }
        if (styled) {
            data.put("headerStyles", headerLooks);
            data.put("cellStyles", cellLooks);
        }

        Element columnGrid = firstChild(table, "tblGrid");
        if (columnGrid != null) {
            List<Double> widths = new ArrayList<>();
            for (Element column : childElements(columnGrid)) {
                if ("gridCol".equals(column.getLocalName())) widths.add((double) longAttr(column, "w", 0));
            }
            if (widths.size() == columns && widths.stream().allMatch(width -> width > 0)) {
                data.put("columnWidths", widths);
            }
        }
        return data;
    }

    /**
     * What a table cell looks like: its fill, the font its first run was set in (size, weight,
     * slant, colour, family) and the alignment of its text; the editor keeps these per cell.
     */
    private Map<String, Object> cellLook(Element cell, TemplateManifest.Theme theme, long[] pageSize) {
        Map<String, Object> look = new LinkedHashMap<>();
        Element properties = firstChild(cell, "tcPr");
        if (properties != null) {
            Fill fill = fillOf(properties, theme);
            if (fill != null && fill.css() != null) look.put("background", fill.css());
            String anchor = properties.getAttribute("anchor");
            if ("ctr".equals(anchor)) look.put("verticalAlign", "middle");
            else if ("t".equals(anchor)) look.put("verticalAlign", "top");
            else if ("b".equals(anchor)) look.put("verticalAlign", "bottom");
        }
        Element run = null;
        for (Element candidate : descendants(cell, "r")) {
            Element text = firstChild(candidate, "t");
            if (text != null && !text.getTextContent().isBlank()) {
                run = candidate;
                break;
            }
        }
        if (run != null) {
            Element style = firstChild(run, "rPr");
            if (style != null) {
                if (!style.getAttribute("sz").isBlank()) {
                    double size = longAttr(style, "sz", 1800) / 100d * 960d / (pageSize[0] / 12_700d);
                    look.put("fontSize", Math.round(size * 10) / 10d);
                }
                if ("1".equals(style.getAttribute("b"))) look.put("fontWeight", 700);
                if ("1".equals(style.getAttribute("i"))) look.put("fontStyle", "italic");
                Element solid = firstChild(style, "solidFill");
                String color = solid == null ? null : colorFromNode(solid, theme.getColors());
                if (color != null) look.put("color", color);
                Element latin = firstChild(style, "latin");
                if (latin != null && !latin.getAttribute("typeface").isBlank() && !latin.getAttribute("typeface").startsWith("+")) {
                    look.put("fontFamily", latin.getAttribute("typeface"));
                }
            }
        }
        for (Element paragraph : descendants(cell, "p")) {
            Element paragraphProperties = firstChild(paragraph, "pPr");
            if (paragraphProperties != null && !paragraphProperties.getAttribute("algn").isBlank()) {
                look.put("textAlign", cssAlign(paragraphProperties.getAttribute("algn")));
                break;
            }
        }
        return look;
    }

    /** A table cell's text, its paragraphs on one line. */
    private String cellText(Element cell) {
        return descendants(cell, "p").stream()
                .map(paragraph -> descendants(paragraph, "t").stream()
                        .map(Element::getTextContent)
                        .filter(value -> value != null && !value.isEmpty())
                        .reduce("", String::concat)
                        .trim())
                .filter(text -> !text.isEmpty())
                .collect(java.util.stream.Collectors.joining(" "));
    }

    /** Everything a slide's text inherits from: the deck's styles and the slide's layout and master. */
    private record TextContext(PptxTextStyles styles, Element layoutTree, Element masterTree, double pointToPixel) {}

    private record RichText(String html, Map<String, Object> style) {}

    private record Run(PptxTextStyles.Props props, String text) {}

    private record Paragraph(int level, PptxTextStyles.Props props, List<Run> runs) {}

    /** The deck's default text style and its master's text styles, as a cascade to resolve a paragraph against. */
    private PptxTextStyles buildTextStyles(Map<String, byte[]> entries, TemplateManifest.Theme theme) {
        PptxTextStyles styles = new PptxTextStyles(
                fill -> colorFromNode(fill, theme.getColors()),
                face -> switch (face) {
                    case "+mj-lt", "+mj-ea", "+mj-cs" -> theme.getHeadingFont();
                    case "+mn-lt", "+mn-ea", "+mn-cs" -> theme.getBodyFont();
                    default -> face;
                });
        try {
            Document presentation = parseXml(entries.get("ppt/presentation.xml"));
            styles.loadDefaults(firstDescendant(presentation.getDocumentElement(), "defaultTextStyle"));
            String master = entries.keySet().stream()
                    .filter(name -> name.startsWith("ppt/slideMasters/slideMaster") && name.endsWith(".xml"))
                    .sorted().findFirst().orElse(null);
            if (master != null) {
                styles.loadMaster(firstDescendant(parseXml(entries.get(master)).getDocumentElement(), "txStyles"));
            }
        } catch (Exception exception) {
            log.debug("Cannot read the deck's text styles: {}", exception.getMessage());
        }
        return styles;
    }

    private TextContext textContextFor(
            Map<String, byte[]> entries, String slidePath, long[] pageSize, PptxTextStyles styles, Map<String, Element> trees
    ) {
        Element layoutTree = null;
        Element masterTree = null;
        try {
            String layoutPath = readRelationships(entries, slidePath).values().stream()
                    .filter(target -> target.startsWith("ppt/slideLayouts/")).findFirst().orElse(null);
            layoutTree = shapeTreeOf(layoutPath, entries, trees);
            if (layoutPath != null) {
                String masterPath = readRelationships(entries, layoutPath).values().stream()
                        .filter(target -> target.startsWith("ppt/slideMasters/")).findFirst().orElse(null);
                masterTree = shapeTreeOf(masterPath, entries, trees);
            }
        } catch (Exception exception) {
            log.debug("Cannot read the layout of {}: {}", slidePath, exception.getMessage());
        }
        return new TextContext(styles, layoutTree, masterTree, 960d / (pageSize[0] / 12_700d));
    }

    private Element shapeTreeOf(String part, Map<String, byte[]> entries, Map<String, Element> cache) throws Exception {
        if (part == null || !entries.containsKey(part)) return null;
        if (!cache.containsKey(part)) {
            cache.put(part, firstDescendant(parseXml(entries.get(part)).getDocumentElement(), "spTree"));
        }
        return cache.get(part);
    }

    /** The placeholder of a layout or master that a slide's placeholder takes its text style from. */
    private Element findPlaceholderShape(Element tree, String type, String index) {
        if (tree == null) return null;
        Element byType = null;
        for (Element shape : childElements(tree)) {
            if (!"sp".equals(shape.getLocalName())) continue;
            Element ph = firstDescendant(shape, "ph");
            if (ph == null) continue;
            String shapeType = ph.getAttribute("type").isBlank() ? "obj" : ph.getAttribute("type");
            if (!index.isBlank() && index.equals(ph.getAttribute("idx"))) return shape;
            if (byType == null && type.equals(shapeType)) byType = shape;
        }
        return byType;
    }

    private static String masterPlaceholderType(String type) {
        return switch (type) {
            case "title", "ctrTitle" -> "title";
            case "sldNum", "dt", "ftr", "hdr" -> type;
            default -> "body";
        };
    }

    /**
     * The text of a shape as editor HTML, with the style it really has.
     *
     * <p>Paragraphs keep their indent level (nested lists), bullet character, alignment and run
     * formatting (bold, italic, underline, colour, size, font). The box's own style is that of its
     * first run, so only runs that differ from it need an inline style.
     */
    private RichText readRichText(Element shape, String role, PlaceholderInfo placeholder, TextContext context) {
        PptxTextStyles styles = context.styles();
        String type = placeholder.type();
        String kind;
        if ("title".equals(role) || "ctrTitle".equals(type)) {
            kind = "title";
        } else if (placeholder.present && !"pageNumber".equals(role) && !List.of("sldNum", "dt", "ftr", "hdr").contains(type)) {
            kind = "body";
        } else {
            kind = "other";
        }
        Element masterShape = placeholder.present
                ? findPlaceholderShape(context.masterTree(), masterPlaceholderType(type), "") : null;
        Element layoutShape = placeholder.present
                ? findPlaceholderShape(context.layoutTree(), type, placeholder.index()) : null;
        Element masterList = masterShape == null ? null : firstDescendant(masterShape, "lstStyle");
        Element layoutList = layoutShape == null ? null : firstDescendant(layoutShape, "lstStyle");
        Element ownList = firstDescendant(shape, "lstStyle");

        List<Paragraph> paragraphs = new ArrayList<>();
        for (Element paragraph : descendants(shape, "p")) {
            Element pPr = firstChild(paragraph, "pPr");
            int level = pPr == null ? 0 : (int) longAttr(pPr, "lvl", 0);
            PptxTextStyles.Props base = new PptxTextStyles.Props();
            base.over(styles.defaultLevel(level))
                    .over(styles.masterLevel(kind, level))
                    .over(styles.listLevel(masterList, level))
                    .over(styles.listLevel(layoutList, level))
                    .over(styles.listLevel(ownList, level));
            if (pPr != null) base.over(styles.paragraph(pPr));
            // A deck whose master says nothing about body text still shows a body placeholder as a list.
            if ("body".equals(kind) && base.bulletMode == null && styles.masterLevel("body", 0) == null) {
                base.bulletMode = "char";
            }
            List<Run> runs = new ArrayList<>();
            for (Element part : childElements(paragraph)) {
                String name = part.getLocalName();
                if ("br".equals(name)) {
                    runs.add(new Run(base, null));
                    continue;
                }
                if (!"r".equals(name) && !"fld".equals(name)) continue;
                Element textNode = firstChild(part, "t");
                String text = textNode == null ? "" : textNode.getTextContent();
                if (text == null || text.isEmpty()) continue;
                runs.add(new Run(base.copy().over(styles.run(firstChild(part, "rPr"))), text));
            }
            if (runs.stream().anyMatch(run -> run.text() != null && !run.text().isBlank())) {
                paragraphs.add(new Paragraph(level, base, runs));
            }
        }
        if (paragraphs.isEmpty()) return null;

        // The box's own style is the one most of its text has, so a bold or coloured word stands out
        // as a run, not the other way round; its alignment is that of its first paragraph.
        PptxTextStyles.Props box = dominantProps(paragraphs).copy();
        box.align = paragraphs.get(0).props().align;
        Element bodyProperties = firstDescendant(shape, "bodyPr");
        Element autofit = bodyProperties == null ? null : firstChild(bodyProperties, "normAutofit");
        double shrink = 1;
        if (autofit != null && !autofit.getAttribute("fontScale").isBlank()) {
            shrink = Math.max(0.2, longAttr(autofit, "fontScale", 100_000) / 100_000d);
        }
        double toPixel = context.pointToPixel() * shrink;
        Map<String, Object> boxStyle = new LinkedHashMap<>();
        if (box.size != null) boxStyle.put("fontSize", Math.round(box.size * toPixel * 10) / 10d);
        if (box.font != null) boxStyle.put("fontFamily", box.font);
        if (box.color != null) boxStyle.put("color", box.color);
        boxStyle.put("fontWeight", Boolean.TRUE.equals(box.bold) ? 700 : 400);
        if (Boolean.TRUE.equals(box.italic)) boxStyle.put("fontStyle", "italic");
        boxStyle.put("textAlign", cssAlign(box.align));
        if (box.lineSpacing != null) boxStyle.put("lineHeight", Math.round(1.2 * box.lineSpacing * 100) / 100d);
        return new RichText(richHtml(paragraphs, box, toPixel), boxStyle);
    }

    /** The run style that covers the most characters of the shape (the first one wins a tie). */
    private PptxTextStyles.Props dominantProps(List<Paragraph> paragraphs) {
        Map<String, Integer> weight = new LinkedHashMap<>();
        Map<String, PptxTextStyles.Props> sample = new HashMap<>();
        for (Paragraph paragraph : paragraphs) {
            for (Run run : paragraph.runs()) {
                if (run.text() == null || run.text().isBlank()) continue;
                PptxTextStyles.Props props = run.props();
                String key = props.size + "|" + props.font + "|" + props.color + "|"
                        + props.bold + "|" + props.italic + "|" + props.underline;
                weight.merge(key, run.text().length(), Integer::sum);
                sample.putIfAbsent(key, props);
            }
        }
        String best = null;
        for (Map.Entry<String, Integer> entry : weight.entrySet()) {
            if (best == null || entry.getValue() > weight.get(best)) best = entry.getKey();
        }
        return sample.get(best);
    }

    /** A pixel length without a needless ".0". */
    private static String px(double value) {
        double rounded = Math.round(value * 10) / 10d;
        return rounded == Math.rint(rounded) ? String.valueOf((long) rounded) : String.valueOf(rounded);
    }

    private static String cssAlign(String align) {
        return switch (align == null ? "l" : align) {
            case "ctr" -> "center";
            case "r" -> "right";
            case "just", "dist" -> "justify";
            default -> "left";
        };
    }

    /** Paragraphs as editor HTML: plain paragraphs, and bulleted ones as nested lists by indent level. */
    private String richHtml(List<Paragraph> paragraphs, PptxTextStyles.Props box, double toPixel) {
        StringBuilder html = new StringBuilder();
        List<String> openLists = new ArrayList<>();
        List<Boolean> openItems = new ArrayList<>();
        String boxAlign = cssAlign(box.align);
        for (Paragraph paragraph : paragraphs) {
            PptxTextStyles.Props props = paragraph.props();
            String align = cssAlign(props.align);
            // Only a paragraph aligned differently from its box needs a <p> of its own inside a list item.
            String open = align.equals(boxAlign) ? null : "<p style=\"text-align:" + align + "\">";
            String inner = runsHtml(paragraph.runs(), box, toPixel);
            boolean bulleted = "char".equals(props.bulletMode) || "auto".equals(props.bulletMode);
            if (!bulleted) {
                closeLists(html, openLists, openItems, 0);
                html.append(open == null ? "<p>" : open).append(inner).append("</p>");
                continue;
            }
            int target = Math.min(paragraph.level() + 1, openLists.size() + 1);
            closeLists(html, openLists, openItems, target);
            if (openLists.size() == target) {
                if (openItems.get(target - 1)) html.append("</li>");
                openItems.set(target - 1, false);
            } else {
                String tag = "auto".equals(props.bulletMode) ? "ol" : "ul";
                String style = "ol".equals(tag) ? null : PptxTextStyles.bulletStyle(props.bulletChar, props.bulletFont);
                html.append('<').append(tag).append(style == null ? "" : " class=\"" + style + "\"").append('>');
                openLists.add(tag);
                openItems.add(false);
            }
            html.append("<li>").append(open == null ? inner : open + inner + "</p>");
            openItems.set(openLists.size() - 1, true);
        }
        closeLists(html, openLists, openItems, 0);
        return html.toString();
    }

    /** Closes lists (and their open items) until only {@code depth} remain. */
    private void closeLists(StringBuilder html, List<String> openLists, List<Boolean> openItems, int depth) {
        while (openLists.size() > depth) {
            int last = openLists.size() - 1;
            if (openItems.get(last)) html.append("</li>");
            html.append("</").append(openLists.get(last)).append('>');
            openLists.remove(last);
            openItems.remove(last);
        }
    }

    /** The runs of one paragraph, each styled only where it differs from the box's own style. */
    private String runsHtml(List<Run> runs, PptxTextStyles.Props box, double toPixel) {
        StringBuilder html = new StringBuilder();
        String pending = null;
        StringBuilder text = new StringBuilder();
        PptxTextStyles.Props pendingProps = null;
        for (Run run : runs) {
            if (run.text() == null) {
                flushRun(html, pendingProps, text, box, toPixel);
                text.setLength(0);
                pending = null;
                pendingProps = null;
                html.append("<br>");
                continue;
            }
            String key = runKey(run.props(), box);
            if (pending != null && !pending.equals(key)) {
                flushRun(html, pendingProps, text, box, toPixel);
                text.setLength(0);
            }
            pending = key;
            pendingProps = run.props();
            text.append(escapeHtml(run.text()));
        }
        flushRun(html, pendingProps, text, box, toPixel);
        return html.toString();
    }

    private String runKey(PptxTextStyles.Props run, PptxTextStyles.Props box) {
        return String.join("|",
                String.valueOf(Boolean.TRUE.equals(run.bold) != Boolean.TRUE.equals(box.bold)),
                String.valueOf(Boolean.TRUE.equals(run.italic) != Boolean.TRUE.equals(box.italic)),
                String.valueOf(Boolean.TRUE.equals(run.underline) != Boolean.TRUE.equals(box.underline)),
                String.valueOf(run.color != null && !run.color.equals(box.color) ? run.color : ""),
                String.valueOf(run.size != null && !run.size.equals(box.size) ? run.size : ""),
                String.valueOf(run.font != null && !run.font.equals(box.font) ? run.font : ""));
    }

    private void flushRun(StringBuilder html, PptxTextStyles.Props run, StringBuilder text,
                          PptxTextStyles.Props box, double toPixel) {
        if (run == null || text.length() == 0) return;
        StringBuilder style = new StringBuilder();
        if (run.color != null && !run.color.equals(box.color)) style.append("color:").append(run.color).append(';');
        if (run.size != null && !run.size.equals(box.size)) {
            style.append("font-size:").append(px(run.size * toPixel)).append("px;");
        }
        if (run.font != null && !run.font.equals(box.font)) style.append("font-family:").append(run.font).append(';');
        boolean bold = Boolean.TRUE.equals(run.bold) != Boolean.TRUE.equals(box.bold);
        boolean italic = Boolean.TRUE.equals(run.italic) != Boolean.TRUE.equals(box.italic);
        boolean underline = Boolean.TRUE.equals(run.underline) != Boolean.TRUE.equals(box.underline);
        // A run that turns off what the box has on needs a style; one that adds it uses the mark.
        if (bold && Boolean.TRUE.equals(box.bold)) style.append("font-weight:400;");
        if (italic && Boolean.TRUE.equals(box.italic)) style.append("font-style:normal;");
        String open = "";
        String close = "";
        if (style.length() > 0) {
            open += "<span style=\"" + style + "\">";
            close = "</span>" + close;
        }
        if (bold && !Boolean.TRUE.equals(box.bold)) { open += "<strong>"; close = "</strong>" + close; }
        if (italic && !Boolean.TRUE.equals(box.italic)) { open += "<em>"; close = "</em>" + close; }
        if (underline && !Boolean.TRUE.equals(box.underline)) { open += "<u>"; close = "</u>" + close; }
        html.append(open).append(text).append(close);
    }

    /**
     * What a text box looks like around its text: the fill and outline of the shape it is (a yellow
     * label, a framed note, an ellipse with a name in it), its rounded corners, and the inset
     * PowerPoint keeps between the edge and the text. The editor applies these as CSS.
     */
    private Map<String, Object> boxLook(Element shape, boolean placeholder, TemplateManifest.Theme theme, long[] pageSize) {
        Map<String, Object> look = new LinkedHashMap<>();
        double toPixel = 960d / pageSize[0];
        Element body = firstDescendant(shape, "bodyPr");
        double left = body == null || body.getAttribute("lIns").isBlank() ? 91_440 : longAttr(body, "lIns", 91_440);
        double top = body == null || body.getAttribute("tIns").isBlank() ? 45_720 : longAttr(body, "tIns", 45_720);
        double right = body == null || body.getAttribute("rIns").isBlank() ? 91_440 : longAttr(body, "rIns", 91_440);
        double bottom = body == null || body.getAttribute("bIns").isBlank() ? 45_720 : longAttr(body, "bIns", 45_720);
        look.put("padding", px(top * toPixel) + "px " + px(right * toPixel) + "px "
                + px(bottom * toPixel) + "px " + px(left * toPixel) + "px");

        Element properties = firstChild(shape, "spPr");
        if (placeholder || properties == null) return look;
        boolean statesFill = List.of("solidFill", "gradFill", "noFill", "blipFill", "pattFill").stream()
                .anyMatch(name -> firstChild(properties, name) != null);
        Fill fill = fillOf(properties, theme);
        String background = fill != null ? fill.css() : (statesFill ? null : styleColor(shape, "fillRef", theme));
        if (background != null) look.put("background", background);

        Element line = firstChild(properties, "ln");
        String lineColor;
        double lineWidth;
        boolean dashed = false;
        if (line != null) {
            Element solid = firstChild(line, "solidFill");
            lineColor = firstChild(line, "noFill") != null || solid == null ? null : colorFromNode(solid, theme.getColors());
            lineWidth = longAttr(line, "w", 12_700) * toPixel;
            Element dash = firstChild(line, "prstDash");
            dashed = dash != null && !"solid".equals(dash.getAttribute("val"));
        } else {
            lineColor = styleColor(shape, "lnRef", theme);
            lineWidth = 12_700 * toPixel;
        }
        if (lineColor != null) {
            look.put("border", px(Math.max(1, lineWidth)) + "px " + (dashed ? "dashed" : "solid") + " " + lineColor);
        }
        Element geometry = firstChild(properties, "prstGeom");
        String preset = geometry == null ? "" : geometry.getAttribute("prst");
        if ("ellipse".equals(preset)) look.put("borderRadius", "50%");
        else if ("roundRect".equals(preset)) look.put("borderRadius", "12px");
        return look;
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
            parseShapeTree(parseXml(entries.get(layoutPath)), pageSize, theme, master.placeholders, false, placeholders, null);
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
                .data(source.getData())
                .style(new LinkedHashMap<>(source.getStyle()))
                .build();
    }

    /* ───────────── backgrounds, pictures and shapes of a sample slide ───────────── */

    private static final long MAX_ASSET_BYTES = 6L * 1024 * 1024;
    private static final int MAX_DECOR = 40;
    private static final int MAX_DECOR_OPENED = 400;
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
            Map<String, byte[]> assetsOut,
            boolean keepText
    ) {
        List<TemplateManifest.Element> decor = new ArrayList<>();
        try {
            Fill background = backgroundChain(slidePath, entries, theme, decor, assetsOut, 0);
            // What the slide's layout and master draw (logo, rules, the slide-number mark) sits behind
            // the slide's own shapes, just above its background picture.
            if (keepText) {
                int above = !decor.isEmpty() && String.valueOf(decor.get(0).getId()).startsWith("decor-bg") ? 1 : 0;
                decor.addAll(above, inheritedDecor(slidePath, slide, entries, pageSize, theme, assetsOut));
            }
            Element tree = firstDescendant(slide.getDocumentElement(), "spTree");
            if (tree != null) {
                List<double[]> textRects = new ArrayList<>();
                collectVisuals(tree, new double[]{1, 0, 1, 0}, readRelationships(entries, slidePath),
                        pageSize, theme, entries, assetsOut, decor, textRects, keepText);
                // A pill, label or button behind the sample's own text is meaningless once that text is gone.
                // An opened deck keeps its own text, so a panel behind it is part of the slide.
                if (!keepText) {
                    decor.removeIf(art -> !"background".equals(art.getRole())
                            && art.getWidth() * art.getHeight() < 0.12 * 960 * 540
                            && textRects.stream().anyMatch(rect -> mostlyInside(rect, art)));
                }
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

    /**
     * The pictures, shapes and rules a slide shows from its layout and its master, bottom first.
     * A slide that hides background graphics ({@code showMasterSp="0"}) shows none of them.
     */
    private List<TemplateManifest.Element> inheritedDecor(
            String slidePath,
            Document slide,
            Map<String, byte[]> entries,
            long[] pageSize,
            TemplateManifest.Theme theme,
            Map<String, byte[]> assetsOut
    ) {
        List<TemplateManifest.Element> out = new ArrayList<>();
        try {
            if ("0".equals(slide.getDocumentElement().getAttribute("showMasterSp"))) return out;
            String layoutPath = readRelationships(entries, slidePath).values().stream()
                    .filter(target -> target.startsWith("ppt/slideLayouts/")).findFirst().orElse(null);
            if (layoutPath == null || !entries.containsKey(layoutPath)) return out;
            Document layout = parseXml(entries.get(layoutPath));
            List<String> parts = new ArrayList<>();
            if (!"0".equals(layout.getDocumentElement().getAttribute("showMasterSp"))) {
                readRelationships(entries, layoutPath).values().stream()
                        .filter(target -> target.startsWith("ppt/slideMasters/")).findFirst().ifPresent(parts::add);
            }
            parts.add(layoutPath);
            for (String part : parts) {
                if (!entries.containsKey(part)) continue;
                Element tree = firstDescendant(parseXml(entries.get(part)).getDocumentElement(), "spTree");
                if (tree != null) {
                    collectVisuals(tree, new double[]{1, 0, 1, 0}, readRelationships(entries, part),
                            pageSize, theme, entries, assetsOut, out, new ArrayList<>(), true);
                }
            }
        } catch (Exception exception) {
            log.debug("Cannot read the layout and master decoration of {}: {}", slidePath, exception.getMessage());
        }
        return out;
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
            List<double[]> textRects,
            boolean keepSmallMarks
    ) {
        for (Element node : childElements(container)) {
            if (out.size() >= (keepSmallMarks ? MAX_DECOR_OPENED : MAX_DECOR)) return;
            String kind = node.getLocalName();
            if ("grpSp".equals(kind)) {
                collectVisuals(node, groupTransform(node, tf), rels, pageSize, theme, entries, assetsOut, out, textRects,
                        keepSmallMarks);
                continue;
            }
            if ("cxnSp".equals(kind)) {
                addRule(node, tf, pageSize, theme, out);
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
            if ("sp".equals(kind) && (height < 1.5 || width < 1.5) && (height >= 3 || width >= 3)
                    && firstDescendant(node, "ph") == null && !hasText(node)) {
                addRule(node, tf, pageSize, theme, out);
                continue;
            }
            if (width < 3 || height < 3 || x > 960 || y > 540 || x + width < 0 || y + height < 0) continue;

            boolean textBox = "sp".equals(kind) && firstChild(properties, "blipFill") == null
                    && (firstDescendant(node, "ph") != null || hasText(node));
            if (textBox) {
                textRects.add(new double[]{x, y, width, height});
                continue;
            }
            if (firstDescendant(node, "ph") != null) continue; // picture placeholders are filled by the app
            // Small marks away from the slide edge (logos, brand stamps) would land on top of the text.
            // (A template's own slides only; in an opened deck a small bar or mark is part of the slide.)
            boolean smallMark = width * height < 4_500;
            boolean nearEdge = x < 48 || y < 48 || x + width > 960 - 48 || y + height > 540 - 48;
            if (!keepSmallMarks && smallMark && !nearEdge) continue;

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

            Element custom = firstChild(properties, "custGeom");
            if (custom != null && !hasText(node)) {
                String path = readCustomPath(custom);
                if (path == null) continue;
                Fill customFill = fillOf(properties, theme);
                String customCss = customFill == null ? styleColor(node, "fillRef", theme) : customFill.css();
                Element stroke = firstDescendant(properties, "ln");
                String strokeColor = readLineColor(node, theme);
                if (strokeColor == null && stroke == null) strokeColor = styleColor(node, "lnRef", theme);
                double strokeWidth = stroke == null ? 1 : longAttr(stroke, "w", 0) / (double) pageSize[0] * 960;
                boolean stroked = strokeColor != null && strokeWidth > 0;
                if (customCss == null && !stroked) continue;
                style.put("shape", "path");
                style.put("path", path);
                if (stroked) style.put("borderWidth", Math.max(1, Math.round(strokeWidth * 10) / 10d));
                out.add(TemplateManifest.Element.builder()
                        .id("decor-" + id)
                        .type("shape")
                        .role("decoration")
                        .x(x).y(y).width(width).height(height)
                        .rotation(rotation)
                        .locked(true)
                        .fill(customCss == null ? "transparent" : customCss)
                        .borderColor(stroked ? strokeColor : null)
                        .style(style)
                        .build());
                continue;
            }

            // Shapes: PowerPoint presets the editor has a matching shape for, filled and/or outlined.
            // Custom outlines (freeform paths) have no equivalent here and would render as wrong rectangles.
            String shapeId = SHAPE_PRESETS.get(preset);
            if (hasText(node) || shapeId == null) continue;
            Fill fill = fillOf(properties, theme);
            String fillCss = fill == null ? styleColor(node, "fillRef", theme) : fill.css();
            String lineColor = readLineColor(node, theme);
            Element line = firstDescendant(properties, "ln");
            if (lineColor == null && line == null) lineColor = styleColor(node, "lnRef", theme);
            double lineWidth = line == null ? (lineColor == null ? 0 : 1)
                    : longAttr(line, "w", 0) / 12_700d * (960d / (pageSize[0] / 12_700d));
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

    /** A colour a shape takes from its style reference (fillRef / lnRef) when it states none itself. */
    private String styleColor(Element shape, String reference, TemplateManifest.Theme theme) {
        Element style = firstChild(shape, "style");
        Element ref = style == null ? null : firstChild(style, reference);
        if (ref == null || "0".equals(ref.getAttribute("idx"))) return null;
        return colorFromNode(ref, theme.getColors());
    }

    /**
     * The outline of a custom-geometry shape as an SVG path in a 0..100 box (M, L, C, Q, Z), so it
     * stretches with the element. Arcs are drawn as short straight segments.
     */
    private String readCustomPath(Element custom) {
        Element list = firstChild(custom, "pathLst");
        if (list == null) return null;
        StringBuilder d = new StringBuilder();
        for (Element path : childElements(list)) {
            if (!"path".equals(path.getLocalName())) continue;
            double w = longAttr(path, "w", 0);
            double h = longAttr(path, "h", 0);
            if (w <= 0 || h <= 0) continue;
            double[] current = {0, 0};
            for (Element command : childElements(path)) {
                List<Element> points = childElements(command).stream()
                        .filter(item -> "pt".equals(item.getLocalName())).toList();
                switch (command.getLocalName()) {
                    case "moveTo", "lnTo" -> {
                        if (points.isEmpty()) break;
                        current = new double[]{longAttr(points.get(0), "x", 0), longAttr(points.get(0), "y", 0)};
                        d.append("moveTo".equals(command.getLocalName()) ? "M " : "L ")
                                .append(unit(current[0], w)).append(' ').append(unit(current[1], h)).append(' ');
                    }
                    case "cubicBezTo" -> {
                        if (points.size() < 3) break;
                        d.append("C ");
                        for (int index = 0; index < 3; index++) {
                            d.append(unit(longAttr(points.get(index), "x", 0), w)).append(' ')
                                    .append(unit(longAttr(points.get(index), "y", 0), h)).append(' ');
                        }
                        current = new double[]{longAttr(points.get(2), "x", 0), longAttr(points.get(2), "y", 0)};
                    }
                    case "quadBezTo" -> {
                        if (points.size() < 2) break;
                        d.append("Q ");
                        for (int index = 0; index < 2; index++) {
                            d.append(unit(longAttr(points.get(index), "x", 0), w)).append(' ')
                                    .append(unit(longAttr(points.get(index), "y", 0), h)).append(' ');
                        }
                        current = new double[]{longAttr(points.get(1), "x", 0), longAttr(points.get(1), "y", 0)};
                    }
                    case "arcTo" -> current = appendArc(d, command, current, w, h);
                    case "close" -> d.append("Z ");
                    default -> { }
                }
            }
        }
        String result = d.toString().trim();
        return result.isEmpty() ? null : result;
    }

    private String unit(double value, double extent) {
        return String.format(Locale.ROOT, "%.2f", value / extent * 100);
    }

    /** An elliptical arc from the current point, as straight segments; returns the point it ends at. */
    private double[] appendArc(StringBuilder d, Element arc, double[] from, double w, double h) {
        double radiusX = longAttr(arc, "wR", 0);
        double radiusY = longAttr(arc, "hR", 0);
        if (radiusX <= 0 || radiusY <= 0) return from;
        double start = Math.toRadians(longAttr(arc, "stAng", 0) / 60_000d);
        double sweep = Math.toRadians(longAttr(arc, "swAng", 0) / 60_000d);
        // PowerPoint's angles are visual; the ellipse's own parameter is tan(t) = (rx / ry) * tan(angle).
        double t0 = Math.atan2(Math.sin(start) * radiusX, Math.cos(start) * radiusY);
        double t1 = Math.atan2(Math.sin(start + sweep) * radiusX, Math.cos(start + sweep) * radiusY);
        double delta = t1 - t0;
        if (sweep > 0 && delta < 0) delta += 2 * Math.PI;
        if (sweep < 0 && delta > 0) delta -= 2 * Math.PI;
        if (Math.abs(Math.abs(sweep) - 2 * Math.PI) < 1e-6) delta = sweep;
        double centreX = from[0] - radiusX * Math.cos(t0);
        double centreY = from[1] - radiusY * Math.sin(t0);
        int steps = Math.max(6, (int) Math.ceil(Math.abs(delta) / (Math.PI / 12)));
        double[] last = from;
        for (int step = 1; step <= steps; step++) {
            double t = t0 + delta * step / steps;
            last = new double[]{centreX + radiusX * Math.cos(t), centreY + radiusY * Math.sin(t)};
            d.append("L ").append(unit(last[0], w)).append(' ').append(unit(last[1], h)).append(' ');
        }
        return last;
    }

    /**
     * A straight horizontal or vertical line (a rule under a title, a divider) as a thin rectangle,
     * which the editor draws exactly. Diagonal lines have no equivalent here and are left out.
     */
    private void addRule(Element line, double[] tf, long[] pageSize, TemplateManifest.Theme theme,
                         List<TemplateManifest.Element> out) {
        Element properties = firstChild(line, "spPr");
        Element transform = properties == null ? null : firstChild(properties, "xfrm");
        Element offset = transform == null ? null : firstChild(transform, "off");
        Element extent = transform == null ? null : firstChild(transform, "ext");
        if (offset == null || extent == null) return;
        // Only straight lines: an elbow or curved connector drawn straight would be wrong.
        Element geometry = firstChild(properties, "prstGeom");
        String preset = geometry == null ? "" : geometry.getAttribute("prst");
        if (!preset.isEmpty() && !"line".equals(preset) && !"straightConnector1".equals(preset)) return;
        Element nonVisual = firstDescendant(line, "cNvPr");
        if (nonVisual != null && "1".equals(nonVisual.getAttribute("hidden"))) return;

        double x = (tf[0] * longAttr(offset, "x", 0) + tf[1]) / pageSize[0] * 960;
        double y = (tf[2] * longAttr(offset, "y", 0) + tf[3]) / pageSize[1] * 540;
        double width = tf[0] * longAttr(extent, "cx", 0) / pageSize[0] * 960;
        double height = tf[2] * longAttr(extent, "cy", 0) / pageSize[1] * 540;
        if (width < 1.5 && height < 1.5) return;
        if (x > 960 || y > 540 || x + width < 0 || y + height < 0) return;

        String color = readLineColor(line, theme);
        if (color == null) {
            Element style = firstChild(line, "style");
            Element reference = style == null ? null : firstChild(style, "lnRef");
            color = reference == null ? null : colorFromNode(reference, theme.getColors());
        }
        if (color == null) return;
        Element stroke = firstDescendant(properties, "ln");
        double thickness = Math.max(1, stroke == null ? 1 : longAttr(stroke, "w", 12_700) / (double) pageSize[0] * 960);
        Element dash = stroke == null ? null : firstDescendant(stroke, "prstDash");
        String dashName = dash == null ? "" : dash.getAttribute("val");
        boolean dashed = !dashName.isBlank() && !"solid".equals(dashName);

        boolean horizontal = height < 1.5;
        boolean vertical = width < 1.5;
        String id = "decor-rule" + out.size() + "-" + UUID.randomUUID().toString().substring(0, 6);
        if ((horizontal || vertical) && !dashed) {
            // An exact thin rectangle.
            out.add(TemplateManifest.Element.builder()
                    .id(id).type("shape").role("decoration")
                    .x(horizontal ? x : x - thickness / 2)
                    .y(horizontal ? y - thickness / 2 : y)
                    .width(horizontal ? width : thickness)
                    .height(horizontal ? thickness : height)
                    .locked(true).fill(color)
                    .style(new LinkedHashMap<>(Map.of("shape", "rect")))
                    .build());
            return;
        }
        // Any other line (diagonal, or dashed): the editor's line shape, turned to the line's angle.
        boolean flipH = "1".equals(transform.getAttribute("flipH"));
        boolean flipV = "1".equals(transform.getAttribute("flipV"));
        double length = Math.hypot(width, height);
        double angle = horizontal ? 0 : vertical ? 90 : Math.toDegrees(Math.atan2(height, width)) * (flipH ^ flipV ? -1 : 1);
        angle += longAttr(transform, "rot", 0) / 60_000d;
        double centreX = x + width / 2;
        double centreY = y + height / 2;
        Map<String, Object> lineStyle = new LinkedHashMap<>();
        lineStyle.put("shape", "line");
        lineStyle.put("borderWidth", Math.round(thickness * 10) / 10d);
        if (dashed) lineStyle.put("dash", dashName.contains("dot") || dashName.contains("Dot") ? "dot" : "dash");
        out.add(TemplateManifest.Element.builder()
                .id(id).type("shape").role("decoration")
                .x(centreX - length / 2).y(centreY - 1).width(length).height(2)
                .rotation(angle)
                .locked(true).fill("transparent").borderColor(color)
                .style(lineStyle)
                .build());
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
    /**
     * One {@code <p>} per paragraph, with consecutive bulleted paragraphs grouped into a list.
     *
     * <p>Whether a paragraph carries a bullet is read from the file: an explicit bullet character
     * or numbering is a bullet, {@code buNone} is not, and a paragraph that says nothing inherits.
     * A plain text box inherits no bullet, so two lines of a text box stay two plain lines; a body
     * placeholder inherits its layout's bullet, which is a bullet except for a subtitle.
     */
    private String readTextHtml(Element shape, String role) {
        boolean bulletByDefault = bodyPlaceholderBullets(shape, role);
        List<Boolean> bulleted = new ArrayList<>();
        List<String> paragraphs = new ArrayList<>();
        for (Element paragraph : descendants(shape, "p")) {
            String text = descendants(paragraph, "t").stream()
                    .map(Element::getTextContent)
                    .filter(value -> value != null && !value.isEmpty())
                    .reduce((left, right) -> left + right)
                    .orElse("");
            if (text.isBlank()) continue;
            paragraphs.add(escapeHtml(text));
            bulleted.add(paragraphBullet(paragraph, bulletByDefault));
        }
        if (paragraphs.isEmpty()) return "";
        if ("title".equals(role)) {
            return paragraphs.stream().map(text -> "<p>" + text + "</p>").reduce("", String::concat);
        }
        StringBuilder html = new StringBuilder();
        boolean inList = false;
        for (int index = 0; index < paragraphs.size(); index++) {
            if (bulleted.get(index)) {
                if (!inList) html.append("<ul>");
                inList = true;
                html.append("<li>").append(paragraphs.get(index)).append("</li>");
            } else {
                if (inList) html.append("</ul>");
                inList = false;
                html.append("<p>").append(paragraphs.get(index)).append("</p>");
            }
        }
        if (inList) html.append("</ul>");
        return html.toString();
    }

    /** Whether a paragraph that names no bullet of its own gets one from the placeholder it sits in. */
    private boolean bodyPlaceholderBullets(Element shape, String role) {
        Element placeholder = firstDescendant(shape, "ph");
        if (placeholder == null || "title".equals(role) || "pageNumber".equals(role)) return false;
        String type = placeholder.getAttribute("type");
        return !List.of("subTitle", "ctrTitle", "title").contains(type);
    }

    private boolean paragraphBullet(Element paragraph, boolean bulletByDefault) {
        Element properties = firstChild(paragraph, "pPr");
        if (properties == null) return bulletByDefault;
        if (firstChild(properties, "buNone") != null) return false;
        if (firstChild(properties, "buChar") != null
                || firstChild(properties, "buAutoNum") != null
                || firstChild(properties, "buBlip") != null) {
            return true;
        }
        return bulletByDefault;
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
