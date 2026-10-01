package com.backend.templateservice.service;

import org.w3c.dom.Element;
import org.w3c.dom.Node;
import org.w3c.dom.NodeList;

import java.util.HashMap;
import java.util.Locale;
import java.util.Map;
import java.util.function.Function;

/**
 * The text style PowerPoint really gives a paragraph.
 *
 * <p>A paragraph rarely states its own font, size, colour, alignment or bullet. It inherits them
 * through several layers, and each layer overrides the one before it:
 * <ol>
 *   <li>the presentation's default text style,
 *   <li>the master's title, body or "other" style (by what kind of text box it is),
 *   <li>the master's placeholder of the same kind, then the layout's,
 *   <li>the text box's own list style,
 *   <li>the paragraph's own properties, and finally
 *   <li>the run's own properties.
 * </ol>
 * Reading only what a run states (as the parser used to) loses most of a deck's look: the serif
 * titles, the sizes of each indent level, the bullet characters and the alignment.
 */
final class PptxTextStyles {

    /** What one layer states about a level of text; {@code null} means "not stated here, inherit". */
    static final class Props {
        Double size;            // points
        Boolean bold;
        Boolean italic;
        Boolean underline;
        String color;           // #RRGGBB
        String font;            // face name, theme fonts already resolved
        String align;           // l | ctr | r | just
        String bulletMode;      // none | char | auto
        String bulletChar;
        String bulletFont;
        Double lineSpacing;     // a multiple of single spacing
        Double letterSpacing;   // points
        Double marginLeft;      // points
        Double indent;          // points (negative: hanging)
        Double spaceBefore;     // points
        Double spaceAfter;      // points

        Props copy() {
            return new Props().over(this);
        }

        /** Applies {@code top} over this: every property it states replaces the one here. */
        Props over(Props top) {
            if (top == null) return this;
            if (top.size != null) size = top.size;
            if (top.bold != null) bold = top.bold;
            if (top.italic != null) italic = top.italic;
            if (top.underline != null) underline = top.underline;
            if (top.color != null) color = top.color;
            if (top.font != null) font = top.font;
            if (top.align != null) align = top.align;
            if (top.bulletMode != null) {
                bulletMode = top.bulletMode;
                bulletChar = top.bulletChar;
                bulletFont = top.bulletFont != null ? top.bulletFont : bulletFont;
            } else if (top.bulletFont != null) {
                bulletFont = top.bulletFont;
            }
            if (top.lineSpacing != null) lineSpacing = top.lineSpacing;
            if (top.letterSpacing != null) letterSpacing = top.letterSpacing;
            if (top.marginLeft != null) marginLeft = top.marginLeft;
            if (top.indent != null) indent = top.indent;
            if (top.spaceBefore != null) spaceBefore = top.spaceBefore;
            if (top.spaceAfter != null) spaceAfter = top.spaceAfter;
            return this;
        }
    }

    private static final int LEVELS = 9;

    private final Function<Element, String> colourOf;
    private final Function<String, String> faceOf;
    private final Props[] defaults = new Props[LEVELS];
    private final Map<String, Props[]> masterStyles = new HashMap<>();

    /**
     * @param colourOf resolves a fill element (solidFill) to #RRGGBB, or null
     * @param faceOf   resolves a typeface, including the theme's "+mj-lt" and "+mn-lt", to a face name
     */
    PptxTextStyles(Function<Element, String> colourOf, Function<String, String> faceOf) {
        this.colourOf = colourOf;
        this.faceOf = faceOf;
    }

    /** The presentation's {@code defaultTextStyle}. */
    void loadDefaults(Element defaultTextStyle) {
        fill(defaults, defaultTextStyle);
    }

    /** The master's {@code txStyles}: its title, body and other styles. */
    void loadMaster(Element txStyles) {
        if (txStyles == null) return;
        for (String[] pair : new String[][]{{"title", "titleStyle"}, {"body", "bodyStyle"}, {"other", "otherStyle"}}) {
            Props[] levels = new Props[LEVELS];
            fill(levels, child(txStyles, pair[1]));
            masterStyles.put(pair[0], levels);
        }
    }

    Props defaultLevel(int level) {
        return defaults[clamp(level)];
    }

    /** The master's style for a kind of text ({@code title}, {@code body} or {@code other}). */
    Props masterLevel(String kind, int level) {
        Props[] levels = masterStyles.get(kind);
        return levels == null ? null : levels[clamp(level)];
    }

    /** One level of a {@code lstStyle} (a text box's own, or a placeholder's on a layout or master). */
    Props listLevel(Element lstStyle, int level) {
        if (lstStyle == null) return null;
        Element levelProperties = child(lstStyle, "lvl" + (clamp(level) + 1) + "pPr");
        return levelProperties == null ? null : paragraph(levelProperties);
    }

    /** Paragraph properties ({@code a:pPr}, or a level of a list style), with the run defaults inside it. */
    Props paragraph(Element pPr) {
        Props props = new Props();
        String align = pPr.getAttribute("algn");
        if (!align.isBlank()) props.align = align;
        props.marginLeft = emuPoints(pPr.getAttribute("marL"));
        props.indent = emuPoints(pPr.getAttribute("indent"));
        for (Element item : children(pPr)) {
            switch (item.getLocalName()) {
                case "buNone" -> props.bulletMode = "none";
                case "buChar" -> {
                    props.bulletMode = "char";
                    props.bulletChar = item.getAttribute("char");
                }
                case "buAutoNum" -> props.bulletMode = "auto";
                case "buBlip" -> props.bulletMode = "char";
                case "buFont" -> props.bulletFont = item.getAttribute("typeface");
                case "lnSpc" -> {
                    Element percent = child(item, "spcPct");
                    if (percent != null) {
                        try {
                            props.lineSpacing = Long.parseLong(percent.getAttribute("val")) / 100_000d;
                        } catch (NumberFormatException ignored) {
                            // keep the inherited spacing
                        }
                    }
                }
                case "spcBef" -> props.spaceBefore = spacing(item, props);
                case "spcAft" -> props.spaceAfter = spacing(item, props);
                case "defRPr" -> props.over(run(item));
                default -> { }
            }
        }
        return props;
    }

    private static Double emuPoints(String value) {
        if (value == null || value.isBlank()) return null;
        try {
            return Long.parseLong(value) / 12_700d;
        } catch (NumberFormatException ignored) {
            return null;
        }
    }

    /** Space before or after a paragraph, in points ({@code spcPts}, or a percentage of a 12-point line). */
    private static Double spacing(Element item, Props props) {
        Element points = child(item, "spcPts");
        try {
            if (points != null) return Long.parseLong(points.getAttribute("val")) / 100d;
            Element percent = child(item, "spcPct");
            if (percent != null) return Long.parseLong(percent.getAttribute("val")) / 100_000d * 12;
        } catch (NumberFormatException ignored) {
            // no spacing stated
        }
        return null;
    }

    /** Run properties ({@code a:rPr}, or the {@code defRPr} of a list style). */
    Props run(Element rPr) {
        Props props = new Props();
        if (rPr == null) return props;
        if (!rPr.getAttribute("spc").isBlank()) {
            try {
                props.letterSpacing = Long.parseLong(rPr.getAttribute("spc")) / 100d;
            } catch (NumberFormatException ignored) {
                // keep the inherited spacing
            }
        }
        try {
            long size = rPr.getAttribute("sz").isBlank() ? 0 : Long.parseLong(rPr.getAttribute("sz"));
            if (size > 0) props.size = size / 100d;
        } catch (NumberFormatException ignored) {
            // keep the inherited size
        }
        String bold = rPr.getAttribute("b");
        if (!bold.isBlank()) props.bold = "1".equals(bold) || "true".equalsIgnoreCase(bold);
        String italic = rPr.getAttribute("i");
        if (!italic.isBlank()) props.italic = "1".equals(italic) || "true".equalsIgnoreCase(italic);
        String underline = rPr.getAttribute("u");
        if (!underline.isBlank()) props.underline = !"none".equalsIgnoreCase(underline);
        Element fill = child(rPr, "solidFill");
        if (fill != null) props.color = colourOf.apply(fill);
        Element latin = child(rPr, "latin");
        if (latin != null && !latin.getAttribute("typeface").isBlank()) {
            props.font = faceOf.apply(latin.getAttribute("typeface"));
        }
        return props;
    }

    private void fill(Props[] target, Element list) {
        if (list == null) return;
        for (int level = 0; level < LEVELS; level++) {
            Element levelProperties = child(list, "lvl" + (level + 1) + "pPr");
            target[level] = levelProperties == null ? null : paragraph(levelProperties);
        }
    }

    private static int clamp(int level) {
        return Math.max(0, Math.min(LEVELS - 1, level));
    }

    static Element child(Element parent, String localName) {
        if (parent == null) return null;
        for (Node node = parent.getFirstChild(); node != null; node = node.getNextSibling()) {
            if (node instanceof Element element && localName.equals(element.getLocalName())) return element;
        }
        return null;
    }

    static java.util.List<Element> children(Element parent) {
        java.util.List<Element> result = new java.util.ArrayList<>();
        NodeList nodes = parent.getChildNodes();
        for (int index = 0; index < nodes.getLength(); index++) {
            if (nodes.item(index) instanceof Element element) result.add(element);
        }
        return result;
    }

    /**
     * The bullet a list should show, as a short style name the editor draws, or {@code null} for the
     * plain disc. Bullet characters are usually symbol-font codes (Wingdings "q" is a boxed square).
     */
    static String bulletStyle(String character, String font) {
        if (character == null || character.isEmpty()) return null;
        boolean symbols = font != null && font.toLowerCase(Locale.ROOT).contains("wingdings");
        if (symbols) {
            return switch (character) {
                case "q", "❏" -> "bu-box";
                case "Ø", "➢" -> "bu-arrow";
                case "§", "n", "▪" -> "bu-square";
                case "v", "❖" -> "bu-diamond";
                case "ü", "þ", "✓" -> "bu-check";
                default -> null;
            };
        }
        return switch (character) {
            case "o", "◦", "○" -> "bu-circle";
            case "–", "—", "-" -> "bu-dash";
            case "▪", "■" -> "bu-square";
            case "➢", "➔", "➜" -> "bu-arrow";
            case "❏" -> "bu-box";
            case "✓", "✔" -> "bu-check";
            case "❖" -> "bu-diamond";
            default -> null;
        };
    }
}
