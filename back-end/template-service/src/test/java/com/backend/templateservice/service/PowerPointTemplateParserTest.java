package com.backend.templateservice.service;

import com.backend.templateservice.dto.manifest.TemplateManifest;
import com.backend.templateservice.dto.request.TemplateMatchRequest;
import com.backend.templateservice.dto.response.TemplateMatchResponse;
import org.junit.jupiter.api.Test;

import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

import static org.assertj.core.api.Assertions.assertThat;

class PowerPointTemplateParserTest {

    @Test
    void parsesLayoutAndMatchesSemanticContent() throws Exception {
        PowerPointTemplateParser parser = new PowerPointTemplateParser();
        TemplateManifest manifest = parser.parse(minimalPptx());

        assertThat(manifest.getAspectRatio()).isEqualTo("16:9");
        assertThat(manifest.getTheme().getPrimaryColor()).isEqualTo("#4472C4");
        assertThat(manifest.getLayouts()).hasSize(1);
        assertThat(manifest.getLayouts().getFirst().getType()).isEqualTo("content");
        assertThat(manifest.getLayouts().getFirst().getElements())
                .extracting(TemplateManifest.Element::getRole)
                .contains("title", "body");

        TemplateMatchResponse match = new TemplateLayoutMatcher().match(
                manifest,
                TemplateMatchRequest.builder()
                        .title("Template upload")
                        .bullets(List.of("First point", "Second point"))
                        .layout("text_only")
                        .pageIndex(1)
                        .build()
        );

        assertThat(match.getLayoutType()).isEqualTo("content");
        assertThat(match.getPrimaryColor()).isEqualTo("#4472C4");
        assertThat(match.getHeadingFont()).isEqualTo("Aptos Display");
        assertThat(match.getBodyFont()).isEqualTo("Aptos");
        assertThat(match.getTitleStyle()).containsKeys("fontFamily", "fontSize", "fontWeight", "color");
        assertThat(match.getBodyStyle()).containsKeys("fontFamily", "fontSize", "fontWeight", "color");
        assertThat(match.getElements()).extracting(item -> item.get("role"))
                .contains("background", "title", "body");
        assertThat(match.getElements().stream()
                .filter(item -> "title".equals(item.get("role")))
                .findFirst()
                .orElseThrow()
                .get("content")).isEqualTo("Template upload");
    }

    @Test
    void parsesImageFrameAndThemeColorsAndStoresMediaAsAssets() throws Exception {
        TemplateManifest manifest = new PowerPointTemplateParser().parse(sampleSlidePptx());

        // The slide's pictures are kept as decoration, so they travel with the template as assets.
        assertThat(manifest.getAssets()).containsOnlyKeys("background.png", "photo.png");
        assertThat(manifest.getLayouts()).hasSize(1);
        TemplateManifest.Layout layout = manifest.getLayouts().getFirst();
        assertThat(layout.getType()).isEqualTo("title");
        assertThat(layout.getElements()).filteredOn(item -> "image".equals(item.getType())).hasSize(1);
        TemplateManifest.Element imageFrame = layout.getElements().stream()
                .filter(item -> "image".equals(item.getType()))
                .findFirst()
                .orElseThrow();
        assertThat(imageFrame.getRole()).isEqualTo("image");
        assertThat(imageFrame.isPlaceholder()).isTrue();
        assertThat(imageFrame.isLocked()).isFalse();
        assertThat(imageFrame.getSrc()).isNull();
        assertThat(imageFrame.getX()).isEqualTo(528d);
        assertThat(imageFrame.getY()).isEqualTo(72d);
        assertThat(imageFrame.getWidth()).isEqualTo(336d);
        assertThat(imageFrame.getHeight()).isEqualTo(360d);
        assertThat(layout.getBackgroundColor()).isEqualTo("#FFFFFF");
        assertThat(layout.getElements()).noneMatch(item -> "shape".equals(item.getType()));
        assertThat(layout.getElements()).filteredOn(TemplateManifest.Element::isPlaceholder)
                .extracting(TemplateManifest.Element::getRole)
                .containsExactlyInAnyOrder("title", "image");
        assertThat(layout.getElements().stream()
                .filter(item -> "title".equals(item.getRole()))
                .findFirst()
                .orElseThrow()
                .getStyle()).containsEntry("color", "#FFFFFF");

        TemplateMatchResponse match = new TemplateLayoutMatcher().match(
                manifest,
                TemplateMatchRequest.builder()
                        .title("New title")
                        .imageUrl("https://example.test/generated.png")
                        .pageIndex(0)
                        .build()
        );
        // The generated picture goes in the template's image frame; the template's own pictures
        // come along as decoration, referenced by asset.
        assertThat(match.getElements()).filteredOn(item -> "image".equals(item.get("role")))
                .singleElement()
                .satisfies(item -> assertThat(item.get("src")).isEqualTo("https://example.test/generated.png"));
        assertThat(match.getBackgroundColor()).isEqualTo("#FFFFFF");
        assertThat(match.getElements())
                .filteredOn(item -> "decoration".equals(item.get("role")) && "image".equals(item.get("type")))
                .extracting(item -> item.get("src"))
                .containsExactlyInAnyOrder("asset:background.png", "asset:photo.png");
        assertThat(match.getElements()).filteredOn(item -> "title".equals(item.get("role")))
                .singleElement()
                .satisfies(item -> {
                    assertThat(item.get("content")).isEqualTo("New title");
                    assertThat(((Map<?, ?>) item.get("style")).get("color")).isEqualTo("#111111");
                });

        TemplateMatchResponse emptyFrameMatch = new TemplateLayoutMatcher().match(
                manifest,
                TemplateMatchRequest.builder().title("No generated image yet").pageIndex(0).build()
        );
        assertThat(emptyFrameMatch.getElements()).filteredOn(item -> "image".equals(item.get("role")))
                .singleElement()
                .satisfies(item -> assertThat(item).doesNotContainKey("src"));
    }

    @Test
    void ignoresEmbeddedImagesFromLegacyManifests() {
        TemplateManifest.Element legacyImage = TemplateManifest.Element.builder()
                .id("legacy-background")
                .type("image")
                .role("background")
                .x(0).y(0).width(960).height(540)
                .src("data:image/png;base64,AQID")
                .locked(true)
                .build();
        TemplateManifest.Element legacyShape = TemplateManifest.Element.builder()
                .id("legacy-shape")
                .type("shape")
                .role("decoration")
                .x(0).y(0).width(960).height(540)
                .fill("#000000")
                .opacity(0.79d)
                .locked(true)
                .build();
        TemplateManifest.Element legacyTitle = TemplateManifest.Element.builder()
                .id("legacy-title")
                .type("text")
                .role("title")
                .x(64).y(44).width(832).height(68)
                .placeholder(true)
                .style(Map.of("color", "#FFFFFF", "fontFamily", "Arial", "fontSize", 32))
                .build();
        TemplateManifest manifest = TemplateManifest.builder()
                .theme(TemplateManifest.Theme.builder()
                        .colors(Map.of("tx1", "#111111"))
                        .build())
                .layouts(List.of(TemplateManifest.Layout.builder()
                        .id("legacy-layout")
                        .type("title")
                        .backgroundColor("#000000")
                        .elements(List.of(legacyImage, legacyShape, legacyTitle))
                        .build()))
                .build();

        TemplateMatchResponse match = new TemplateLayoutMatcher().match(
                manifest,
                TemplateMatchRequest.builder().title("New title").pageIndex(0).build()
        );

        assertThat(match.getElements()).noneMatch(item -> "image".equals(item.get("type")));
        assertThat(match.getElements()).noneMatch(item -> "decoration".equals(item.get("role")));
        // The page takes the layout's own colour (black here), not a fixed white.
        assertThat(match.getElements()).filteredOn(item -> "background".equals(item.get("role")))
                .singleElement()
                .satisfies(item -> assertThat(item.get("fill")).isEqualTo("#000000"));
        // White text on that black page is already readable, so it is kept.
        assertThat(match.getElements()).filteredOn(item -> "title".equals(item.get("role")))
                .singleElement()
                .satisfies(item -> assertThat(((Map<?, ?>) item.get("style")).get("color"))
                        .isEqualTo("#FFFFFF"));
    }

    @Test
    void openedDeckKeepsPlaceholderTextAndInheritsLayoutPosition() throws Exception {
        byte[] deck = placeholderDeckPptx();

        // Opening a real deck: the words in its title and body placeholders are the deck itself.
        TemplateManifest opened = new PowerPointTemplateParser().parseWithAssets(deck, true).manifest();
        List<TemplateManifest.Element> texts = opened.getLayouts().get(0).getElements().stream()
                .filter(item -> "text".equals(item.getType()))
                .toList();
        assertThat(texts).extracting(TemplateManifest.Element::getContent)
                .anyMatch(content -> content.contains("Tieu de that"))
                .anyMatch(content -> content.contains("Noi dung that"));
        // Neither placeholder has a position of its own; each takes the one its layout gives it,
        // matched by index, so the two boxes do not end up in the same place.
        TemplateManifest.Element title = texts.stream()
                .filter(item -> item.getContent().contains("Tieu de that")).findFirst().orElseThrow();
        TemplateManifest.Element body = texts.stream()
                .filter(item -> item.getContent().contains("Noi dung that")).findFirst().orElseThrow();
        assertThat(title.getY()).isLessThan(body.getY());
        assertThat(body.getWidth()).isGreaterThan(title.getWidth());

        // Uploading the same file as a template keeps placeholders blank, as before.
        TemplateManifest asTemplate = new PowerPointTemplateParser().parseWithAssets(deck, false).manifest();
        assertThat(asTemplate.getLayouts().get(0).getElements())
                .noneMatch(item -> item.getContent() != null && item.getContent().contains("Tieu de that"));
    }

    @Test
    void openedDeckKeepsTheFilesOwnBullets() throws Exception {
        String slide = """
                <?xml version="1.0" encoding="UTF-8"?>
                <p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
                  xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
                  <p:cSld><p:spTree>
                    <p:sp>
                      <p:nvSpPr><p:cNvPr id="2" name="Plain box"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
                      <p:spPr><a:xfrm><a:off x="609600" y="609600"/><a:ext cx="5000000" cy="800000"/></a:xfrm></p:spPr>
                      <p:txBody><a:bodyPr/><a:lstStyle/>
                        <a:p><a:r><a:t>Dong mot</a:t></a:r></a:p>
                        <a:p><a:r><a:t>Dong hai</a:t></a:r></a:p>
                      </p:txBody>
                    </p:sp>
                    <p:sp>
                      <p:nvSpPr><p:cNvPr id="3" name="Bulleted box"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
                      <p:spPr><a:xfrm><a:off x="609600" y="1800000"/><a:ext cx="5000000" cy="500000"/></a:xfrm></p:spPr>
                      <p:txBody><a:bodyPr/><a:lstStyle/>
                        <a:p><a:pPr><a:buChar char="&#8226;"/></a:pPr><a:r><a:t>Co dau dong</a:t></a:r></a:p>
                      </p:txBody>
                    </p:sp>
                    <p:sp>
                      <p:nvSpPr><p:cNvPr id="4" name="Body, no bullet"/><p:cNvSpPr/><p:nvPr><p:ph idx="1"/></p:nvPr></p:nvSpPr>
                      <p:spPr/>
                      <p:txBody><a:bodyPr/><a:lstStyle/>
                        <a:p><a:pPr><a:buNone/></a:pPr><a:r><a:t>Khong dau dong</a:t></a:r></a:p>
                      </p:txBody>
                    </p:sp>
                    <p:sp>
                      <p:nvSpPr><p:cNvPr id="5" name="Body, inherits"/><p:cNvSpPr/><p:nvPr><p:ph idx="1"/></p:nvPr></p:nvSpPr>
                      <p:spPr/>
                      <p:txBody><a:bodyPr/><a:lstStyle/>
                        <a:p><a:r><a:t>Ke thua dau dong</a:t></a:r></a:p>
                      </p:txBody>
                    </p:sp>
                  </p:spTree></p:cSld>
                </p:sld>
                """;
        TemplateManifest opened = new PowerPointTemplateParser()
                .parseWithAssets(withSlide(placeholderDeckPptx(), slide), true).manifest();
        List<String> contents = opened.getLayouts().get(0).getElements().stream()
                .filter(item -> "text".equals(item.getType()))
                .map(TemplateManifest.Element::getContent)
                .toList();

        // A plain text box has no bullet unless the file gives one: two lines stay two lines.
        assertThat(contents).contains("<p>Dong mot</p><p>Dong hai</p>");
        // An explicit bullet character is kept even on a single line.
        assertThat(contents).contains("<ul><li>Co dau dong</li></ul>");
        // A body placeholder takes its layout's bullet unless the paragraph switches it off.
        assertThat(contents).contains("<p>Khong dau dong</p>");
        assertThat(contents).contains("<ul><li>Ke thua dau dong</li></ul>");
    }

    @Test
    void openedDeckKeepsItsSlideNumberAsAPageNumberBox() throws Exception {
        String slide = """
                <?xml version="1.0" encoding="UTF-8"?>
                <p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
                  xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
                  <p:cSld><p:spTree>
                    <p:sp>
                      <p:nvSpPr><p:cNvPr id="2" name="Title 1"/><p:cNvSpPr/><p:nvPr><p:ph type="title"/></p:nvPr></p:nvSpPr>
                      <p:spPr/>
                      <p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:t>Tieu de that</a:t></a:r></a:p></p:txBody>
                    </p:sp>
                    <p:sp>
                      <p:nvSpPr><p:cNvPr id="3" name="Slide Number"/><p:cNvSpPr/><p:nvPr><p:ph type="sldNum" idx="12"/></p:nvPr></p:nvSpPr>
                      <p:spPr/>
                      <p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:fld id="{00000000-1234-1234-1234-123412341234}" type="slidenum"><a:rPr lang="en-US"/><a:t>3</a:t></a:fld></a:p></p:txBody>
                    </p:sp>
                  </p:spTree></p:cSld>
                </p:sld>
                """;
        byte[] deck = withSlide(placeholderDeckPptx(), slide);

        List<TemplateManifest.Element> texts = new PowerPointTemplateParser().parseWithAssets(deck, true).manifest()
                .getLayouts().get(0).getElements().stream().filter(item -> "text".equals(item.getType())).toList();
        TemplateManifest.Element number = texts.stream()
                .filter(item -> "pageNumber".equals(item.getRole())).findFirst().orElseThrow();
        assertThat(number.getContent()).isEqualTo("<p>3</p>");
        // It sits where the slide's layout puts the slide number (bottom right).
        assertThat(number.getX()).isBetween(863d, 865d);
        assertThat(number.getY()).isBetween(503d, 505d);
        // The number is never mistaken for the slide's title, which stays the real heading.
        assertThat(texts).filteredOn(item -> "title".equals(item.getRole())).singleElement()
                .satisfies(item -> assertThat(item.getContent()).contains("Tieu de that"));

        // A template upload never keeps slide numbers.
        TemplateManifest asTemplate = new PowerPointTemplateParser().parseWithAssets(deck, false).manifest();
        assertThat(asTemplate.getLayouts().get(0).getElements())
                .noneMatch(item -> "pageNumber".equals(item.getRole()));
    }

    @Test
    void openedDeckKeepsItsTableCellsAndColumnWidths() throws Exception {
        String slide = """
                <?xml version="1.0" encoding="UTF-8"?>
                <p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
                  xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
                  <p:cSld><p:spTree>
                    <p:graphicFrame>
                      <p:nvGraphicFramePr><p:cNvPr id="4" name="Table 3"/><p:cNvGraphicFramePr/><p:nvPr/></p:nvGraphicFramePr>
                      <p:xfrm><a:off x="609600" y="1524000"/><a:ext cx="9144000" cy="1828800"/></p:xfrm>
                      <a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/table">
                        <a:tbl>
                          <a:tblPr firstRow="1"/>
                          <a:tblGrid><a:gridCol w="3000000"/><a:gridCol w="6144000"/></a:tblGrid>
                          <a:tr h="370840">
                            <a:tc><a:txBody><a:bodyPr/><a:p><a:pPr algn="ctr"/><a:r><a:rPr sz="1800" b="1" i="1"><a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill><a:latin typeface="Times New Roman"/></a:rPr><a:t>Muc</a:t></a:r></a:p></a:txBody><a:tcPr anchor="ctr"><a:solidFill><a:srgbClr val="0000FF"/></a:solidFill></a:tcPr></a:tc>
                            <a:tc><a:txBody><a:bodyPr/><a:p><a:r><a:t>Gia tri</a:t></a:r></a:p></a:txBody></a:tc>
                          </a:tr>
                          <a:tr h="370840">
                            <a:tc><a:txBody><a:bodyPr/><a:p><a:r><a:t>Mot</a:t></a:r></a:p><a:p><a:r><a:t>dong hai</a:t></a:r></a:p></a:txBody></a:tc>
                            <a:tc><a:txBody><a:bodyPr/><a:p><a:r><a:t>10</a:t></a:r></a:p></a:txBody></a:tc>
                          </a:tr>
                        </a:tbl>
                      </a:graphicData></a:graphic>
                    </p:graphicFrame>
                  </p:spTree></p:cSld>
                </p:sld>
                """;
        byte[] deck = withSlide(placeholderDeckPptx(), slide);

        List<TemplateManifest.Element> elements = new PowerPointTemplateParser().parseWithAssets(deck, true).manifest()
                .getLayouts().get(0).getElements();
        TemplateManifest.Element table = elements.stream()
                .filter(item -> "table".equals(item.getType())).findFirst().orElseThrow();
        assertThat(table.getData().get("headers")).isEqualTo(List.of("Muc", "Gia tri"));
        // A cell's paragraphs share one line.
        assertThat(table.getData().get("rows")).isEqualTo(List.of(List.of("Mot dong hai", "10")));
        // The look of each cell: the header's fill, white bold italic serif text, centred.
        @SuppressWarnings("unchecked")
        List<java.util.Map<String, Object>> headerStyles = (List<java.util.Map<String, Object>>) table.getData().get("headerStyles");
        assertThat(headerStyles.get(0)).containsEntry("background", "#0000FF").containsEntry("color", "#FFFFFF")
                .containsEntry("fontWeight", 700).containsEntry("fontStyle", "italic")
                .containsEntry("fontFamily", "Times New Roman").containsEntry("textAlign", "center")
                .containsEntry("verticalAlign", "middle");
        assertThat(table.getData().get("columnWidths")).isEqualTo(List.of(3000000d, 6144000d));
        assertThat(table.getX()).isBetween(47d, 49d);
        // The cells are not also read as a text box of their own.
        assertThat(elements).filteredOn(item -> "text".equals(item.getType())).isEmpty();

        // A template upload keeps no table.
        assertThat(new PowerPointTemplateParser().parseWithAssets(deck, false).manifest().getLayouts().get(0).getElements())
                .noneMatch(item -> "table".equals(item.getType()));
    }

    @Test
    void openedDeckShowsWhatItsLayoutAndMasterDraw() throws Exception {
        String master = """
                <?xml version="1.0" encoding="UTF-8"?>
                <p:sldMaster xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
                  xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
                  <p:cSld><p:spTree>
                    <p:sp>
                      <p:nvSpPr><p:cNvPr id="2" name="Top bar"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
                      <p:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="12192000" cy="300000"/></a:xfrm>
                        <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
                        <a:solidFill><a:srgbClr val="112233"/></a:solidFill></p:spPr>
                    </p:sp>
                  </p:spTree></p:cSld>
                </p:sldMaster>
                """;
        String layout = """
                <?xml version="1.0" encoding="UTF-8"?>
                <p:sldLayout xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
                  xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
                  <p:cSld name="With a rule"><p:spTree>
                    <p:cxnSp>
                      <p:nvCxnSpPr><p:cNvPr id="3" name="Rule"/><p:cNvCxnSpPr/><p:nvPr/></p:nvCxnSpPr>
                      <p:spPr><a:xfrm><a:off x="609600" y="1600000"/><a:ext cx="9000000" cy="0"/></a:xfrm>
                        <a:prstGeom prst="line"><a:avLst/></a:prstGeom>
                        <a:ln w="12700"><a:solidFill><a:srgbClr val="AABBCC"/></a:solidFill></a:ln></p:spPr>
                    </p:cxnSp>
                    <p:cxnSp>
                      <p:nvCxnSpPr><p:cNvPr id="4" name="Diagonal"/><p:cNvCxnSpPr/><p:nvPr/></p:nvCxnSpPr>
                      <p:spPr><a:xfrm><a:off x="609600" y="2600000"/><a:ext cx="2000000" cy="2000000"/></a:xfrm>
                        <a:prstGeom prst="line"><a:avLst/></a:prstGeom>
                        <a:ln w="12700"><a:solidFill><a:srgbClr val="FF0000"/></a:solidFill></a:ln></p:spPr>
                    </p:cxnSp>
                  </p:spTree></p:cSld>
                </p:sldLayout>
                """;
        String layoutRels = """
                <?xml version="1.0" encoding="UTF-8"?>
                <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
                  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/>
                </Relationships>
                """;
        byte[] deck = withPart(withPart(withPart(placeholderDeckPptx(),
                "ppt/slideMasters/slideMaster1.xml", master),
                "ppt/slideLayouts/slideLayout1.xml", layout),
                "ppt/slideLayouts/_rels/slideLayout1.xml.rels", layoutRels);

        List<TemplateManifest.Element> decor = new PowerPointTemplateParser().parseWithAssets(deck, true).manifest()
                .getLayouts().get(0).getDecor();
        // The master's bar is drawn below the layout's rule.
        assertThat(decor).extracting(TemplateManifest.Element::getFill).containsSubsequence("#112233", "#AABBCC");
        TemplateManifest.Element rule = decor.stream().filter(item -> "#AABBCC".equals(item.getFill())).findFirst().orElseThrow();
        assertThat(rule.getType()).isEqualTo("shape");
        assertThat(rule.getHeight()).isBetween(0.9d, 1.6d);          // a thin rectangle, as thick as the line
        assertThat(rule.getWidth()).isBetween(707d, 710d);
        // A diagonal line has no equivalent and is left out.
        assertThat(decor).noneMatch(item -> "#FF0000".equals(item.getFill()));

        // A slide that hides background graphics shows neither.
        String hidden = """
                <?xml version="1.0" encoding="UTF-8"?>
                <p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
                  xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" showMasterSp="0">
                  <p:cSld><p:spTree/></p:cSld>
                </p:sld>
                """;
        byte[] hiddenDeck = withSlide(deck, hidden);
        assertThat(new PowerPointTemplateParser().parseWithAssets(hiddenDeck, true).manifest().getLayouts().get(0).getDecor())
                .extracting(TemplateManifest.Element::getFill).doesNotContain("#112233", "#AABBCC");

        // A template upload keeps the layouts' own placeholders only, as before.
        assertThat(new PowerPointTemplateParser().parseWithAssets(deck, false).manifest().getLayouts().get(0).getDecor())
                .extracting(TemplateManifest.Element::getFill).doesNotContain("#112233", "#AABBCC");
    }

    @Test
    void openedDeckKeepsCustomShapesAndGoogleStyleRules() throws Exception {
        // Google Slides writes every box, bar and rule as custom geometry, a rule with no height at all.
        String layout = """
                <?xml version="1.0" encoding="UTF-8"?>
                <p:sldLayout xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
                  xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
                  <p:cSld name="Custom"><p:spTree>
                    <p:sp>
                      <p:nvSpPr><p:cNvPr id="2" name="Bar"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
                      <p:spPr><a:xfrm><a:off x="1200000" y="3600000"/><a:ext cx="300000" cy="1200000"/></a:xfrm>
                        <a:custGeom><a:pathLst><a:path w="100" h="100">
                          <a:moveTo><a:pt x="0" y="0"/></a:moveTo><a:lnTo><a:pt x="100" y="0"/></a:lnTo>
                          <a:lnTo><a:pt x="100" y="100"/></a:lnTo><a:lnTo><a:pt x="0" y="100"/></a:lnTo><a:close/>
                        </a:path></a:pathLst></a:custGeom>
                        <a:solidFill><a:srgbClr val="717BA2"/></a:solidFill><a:ln><a:noFill/></a:ln></p:spPr>
                    </p:sp>
                    <p:sp>
                      <p:nvSpPr><p:cNvPr id="3" name="Dashed rule"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
                      <p:spPr><a:xfrm><a:off x="609600" y="1300000"/><a:ext cx="10000000" cy="0"/></a:xfrm>
                        <a:custGeom><a:pathLst><a:path w="100" h="0">
                          <a:moveTo><a:pt x="0" y="0"/></a:moveTo><a:lnTo><a:pt x="100" y="0"/></a:lnTo>
                        </a:path></a:pathLst></a:custGeom>
                        <a:ln w="9525"><a:solidFill><a:srgbClr val="999999"/></a:solidFill><a:prstDash val="dash"/></a:ln></p:spPr>
                    </p:sp>
                    <p:sp>
                      <p:nvSpPr><p:cNvPr id="4" name="Style filled"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
                      <p:spPr><a:xfrm><a:off x="6000000" y="3600000"/><a:ext cx="1200000" cy="600000"/></a:xfrm>
                        <a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr>
                      <p:style><a:lnRef idx="0"><a:srgbClr val="000000"/></a:lnRef>
                        <a:fillRef idx="1"><a:srgbClr val="2E8B57"/></a:fillRef></p:style>
                    </p:sp>
                  </p:spTree></p:cSld>
                </p:sldLayout>
                """;
        String layoutRels = """
                <?xml version="1.0" encoding="UTF-8"?>
                <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
                  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/>
                </Relationships>
                """;
        byte[] deck = withPart(withPart(placeholderDeckPptx(), "ppt/slideLayouts/slideLayout1.xml", layout),
                "ppt/slideLayouts/_rels/slideLayout1.xml.rels", layoutRels);

        List<TemplateManifest.Element> decor = new PowerPointTemplateParser().parseWithAssets(deck, true).manifest()
                .getLayouts().get(0).getDecor();

        TemplateManifest.Element bar = decor.stream().filter(item -> "#717BA2".equals(item.getFill())).findFirst().orElseThrow();
        assertThat(bar.getStyle().get("shape")).isEqualTo("path");
        assertThat(bar.getStyle().get("path")).isEqualTo("M 0 0 L 100 0 L 100 100 L 0 100 Z");
        // A dashed rule with no height is kept as a dashed line in its own colour.
        TemplateManifest.Element rule = decor.stream().filter(item -> "#999999".equals(item.getBorderColor())).findFirst().orElseThrow();
        assertThat(rule.getStyle()).containsEntry("shape", "line").containsEntry("dash", "dash");
        assertThat(rule.getWidth()).isBetween(787d, 790d);
        // A shape that takes its colour from its style is filled with it.
        assertThat(decor).anyMatch(item -> "#2E8B57".equals(item.getFill()));
    }

    @Test
    void openedDeckResolvesTextStylesThroughTheMaster() throws Exception {
        String master = """
                <?xml version="1.0" encoding="UTF-8"?>
                <p:sldMaster xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
                  xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
                  <p:cSld><p:spTree/></p:cSld>
                  <p:txStyles>
                    <p:titleStyle>
                      <a:lvl1pPr algn="ctr"><a:buNone/>
                        <a:defRPr sz="2800" b="0"><a:solidFill><a:srgbClr val="4D4D4D"/></a:solidFill><a:latin typeface="Times New Roman"/></a:defRPr>
                      </a:lvl1pPr>
                    </p:titleStyle>
                    <p:bodyStyle>
                      <a:lvl1pPr marL="342900" indent="-342900" algn="l"><a:buFont typeface="Wingdings"/><a:buChar char="&#216;"/>
                        <a:defRPr sz="2000"><a:latin typeface="Arial"/></a:defRPr></a:lvl1pPr>
                      <a:lvl2pPr marL="742950" indent="-285750"><a:buFont typeface="Courier New"/><a:buChar char="o"/>
                        <a:defRPr sz="1600"/></a:lvl2pPr>
                    </p:bodyStyle>
                    <p:otherStyle><a:lvl1pPr><a:defRPr sz="1800"/></a:lvl1pPr></p:otherStyle>
                  </p:txStyles>
                </p:sldMaster>
                """;
        String slide = """
                <?xml version="1.0" encoding="UTF-8"?>
                <p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
                  xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
                  <p:cSld><p:spTree>
                    <p:sp>
                      <p:nvSpPr><p:cNvPr id="2" name="Title 1"/><p:cNvSpPr/><p:nvPr><p:ph type="title"/></p:nvPr></p:nvSpPr>
                      <p:spPr/>
                      <p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:t>Tieu de</a:t></a:r></a:p></p:txBody>
                    </p:sp>
                    <p:sp>
                      <p:nvSpPr><p:cNvPr id="3" name="Content 2"/><p:cNvSpPr/><p:nvPr><p:ph idx="1"/></p:nvPr></p:nvSpPr>
                      <p:spPr/>
                      <p:txBody><a:bodyPr/><a:lstStyle/>
                        <a:p><a:r><a:rPr b="1"><a:solidFill><a:srgbClr val="FF0000"/></a:solidFill></a:rPr><a:t>Nhan manh</a:t></a:r><a:r><a:t> thuong</a:t></a:r></a:p>
                        <a:p><a:pPr lvl="1"/><a:r><a:t>Muc hai</a:t></a:r></a:p>
                        <a:p><a:r><a:t>Muc mot nua</a:t></a:r></a:p>
                      </p:txBody>
                    </p:sp>
                    <p:sp>
                      <p:nvSpPr><p:cNvPr id="4" name="Plain box"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
                      <p:spPr><a:xfrm><a:off x="609600" y="5000000"/><a:ext cx="3000000" cy="400000"/></a:xfrm></p:spPr>
                      <p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:pPr algn="r"/><a:r><a:t>Ghi chu</a:t></a:r></a:p></p:txBody>
                    </p:sp>
                  </p:spTree></p:cSld>
                </p:sld>
                """;
        byte[] deck = withSlide(withPart(placeholderDeckPptx(), "ppt/slideMasters/slideMaster1.xml", master), slide);

        List<TemplateManifest.Element> texts = new PowerPointTemplateParser().parseWithAssets(deck, true).manifest()
                .getLayouts().get(0).getElements().stream().filter(item -> "text".equals(item.getType())).toList();
        TemplateManifest.Element title = texts.stream().filter(item -> "title".equals(item.getRole())).findFirst().orElseThrow();
        // The title is a serif, grey, centred, regular-weight 28 point: all of it from the master.
        assertThat(title.getStyle()).containsEntry("fontFamily", "Times New Roman").containsEntry("color", "#4D4D4D")
                .containsEntry("textAlign", "center").containsEntry("fontWeight", 400).containsEntry("fontSize", 28d);
        assertThat(title.getContent()).isEqualTo("<p>Tieu de</p>");

        TemplateManifest.Element body = texts.stream().filter(item -> item.getContent().contains("Nhan manh")).findFirst().orElseThrow();
        assertThat(body.getStyle()).containsEntry("fontFamily", "Arial").containsEntry("fontSize", 20d);
        // Levels become nested lists, each with the bullet its level has; formatting is only on the odd run.
        assertThat(body.getContent()).isEqualTo(
                "<ul class=\"bu-arrow\"><li><span style=\"color:#FF0000;\"><strong>Nhan manh</strong></span> thuong"
                        + "<ul class=\"bu-circle\"><li><span style=\"font-size:16px;\">Muc hai</span></li></ul></li>"
                        + "<li>Muc mot nua</li></ul>");

        // A plain text box takes the master's "other" style, and its own alignment.
        TemplateManifest.Element note = texts.stream().filter(item -> item.getContent().contains("Ghi chu")).findFirst().orElseThrow();
        assertThat(note.getStyle()).containsEntry("fontSize", 18d).containsEntry("textAlign", "right");
        assertThat(note.getContent()).isEqualTo("<p>Ghi chu</p>");
    }

    @Test
    void openedDeckKeepsTheLookOfTextBoxesAndTheShrinkPowerPointApplied() throws Exception {
        String slide = """
                <?xml version="1.0" encoding="UTF-8"?>
                <p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
                  xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
                  <p:cSld><p:spTree>
                    <p:sp>
                      <p:nvSpPr><p:cNvPr id="2" name="Yellow label"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
                      <p:spPr><a:xfrm><a:off x="609600" y="609600"/><a:ext cx="2400000" cy="500000"/></a:xfrm>
                        <a:prstGeom prst="ellipse"><a:avLst/></a:prstGeom>
                        <a:solidFill><a:srgbClr val="FFF2CC"/></a:solidFill>
                        <a:ln w="12700"><a:solidFill><a:srgbClr val="7F6000"/></a:solidFill><a:prstDash val="dash"/></a:ln></p:spPr>
                      <p:txBody><a:bodyPr wrap="none" lIns="0" tIns="0" rIns="0" bIns="0"/><a:lstStyle/>
                        <a:p><a:r><a:rPr sz="2000" spc="-200"/><a:t>minsup = 3</a:t></a:r></a:p></p:txBody>
                    </p:sp>
                    <p:sp>
                      <p:nvSpPr><p:cNvPr id="3" name="Shrunk"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
                      <p:spPr><a:xfrm><a:off x="609600" y="2000000"/><a:ext cx="6000000" cy="2000000"/></a:xfrm></p:spPr>
                      <p:txBody><a:bodyPr><a:normAutofit fontScale="62500" lnSpcReduction="20000"/></a:bodyPr><a:lstStyle/>
                        <a:p><a:r><a:rPr sz="2000"/><a:t>Chu nho lai</a:t></a:r></a:p></p:txBody>
                    </p:sp>
                  </p:spTree></p:cSld>
                </p:sld>
                """;
        byte[] deck = withSlide(placeholderDeckPptx(), slide);

        List<TemplateManifest.Element> texts = new PowerPointTemplateParser().parseWithAssets(deck, true).manifest()
                .getLayouts().get(0).getElements().stream().filter(item -> "text".equals(item.getType())).toList();
        TemplateManifest.Element label = texts.stream().filter(item -> item.getContent().contains("minsup")).findFirst().orElseThrow();
        assertThat(label.getStyle()).containsEntry("background", "#FFF2CC").containsEntry("borderRadius", "50%")
                .containsEntry("padding", "0px 0px 0px 0px").containsEntry("whiteSpace", "nowrap")
                .containsEntry("letterSpacing", "-2px");
        assertThat((String) label.getStyle().get("border")).startsWith("1px dashed #7F6000");

        // 62.5% of 20 points.
        TemplateManifest.Element shrunk = texts.stream().filter(item -> item.getContent().contains("Chu nho")).findFirst().orElseThrow();
        assertThat(shrunk.getStyle()).containsEntry("fontSize", 12.5d);
        // PowerPoint's default inset, as the editor's padding (7.2 pt sides, 3.6 pt top and bottom).
        assertThat(shrunk.getStyle()).containsEntry("padding", "3.6px 7.2px 3.6px 7.2px");
        assertThat(shrunk.getStyle()).doesNotContainKey("background");
    }

    @Test
    void openedDeckKeepsDiagonalAndDashedLines() throws Exception {
        String layout = """
                <?xml version="1.0" encoding="UTF-8"?>
                <p:sldLayout xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
                  xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
                  <p:cSld name="Lines"><p:spTree>
                    <p:cxnSp>
                      <p:nvCxnSpPr><p:cNvPr id="2" name="Diagonal"/><p:cNvCxnSpPr/><p:nvPr/></p:nvCxnSpPr>
                      <p:spPr><a:xfrm><a:off x="1219200" y="1371600"/><a:ext cx="3048000" cy="1714500"/></a:xfrm>
                        <a:prstGeom prst="line"><a:avLst/></a:prstGeom>
                        <a:ln w="12700"><a:solidFill><a:srgbClr val="FF0000"/></a:solidFill></a:ln></p:spPr>
                    </p:cxnSp>
                    <p:cxnSp>
                      <p:nvCxnSpPr><p:cNvPr id="3" name="Rising"/><p:cNvCxnSpPr/><p:nvPr/></p:nvCxnSpPr>
                      <p:spPr><a:xfrm flipV="1"><a:off x="1219200" y="3600000"/><a:ext cx="3048000" cy="1714500"/></a:xfrm>
                        <a:prstGeom prst="line"><a:avLst/></a:prstGeom>
                        <a:ln w="12700"><a:solidFill><a:srgbClr val="00AA00"/></a:solidFill></a:ln></p:spPr>
                    </p:cxnSp>
                    <p:cxnSp>
                      <p:nvCxnSpPr><p:cNvPr id="4" name="Dashed"/><p:cNvCxnSpPr/><p:nvPr/></p:nvCxnSpPr>
                      <p:spPr><a:xfrm><a:off x="609600" y="5800000"/><a:ext cx="9000000" cy="0"/></a:xfrm>
                        <a:prstGeom prst="line"><a:avLst/></a:prstGeom>
                        <a:ln w="9525"><a:solidFill><a:srgbClr val="0000FF"/></a:solidFill><a:prstDash val="dash"/></a:ln></p:spPr>
                    </p:cxnSp>
                    <p:sp>
                      <p:nvSpPr><p:cNvPr id="6" name="Bar"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
                      <p:spPr><a:xfrm><a:off x="2000000" y="2000000"/><a:ext cx="1000000" cy="12700"/></a:xfrm>
                        <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
                        <a:solidFill><a:srgbClr val="222222"/></a:solidFill><a:ln><a:noFill/></a:ln></p:spPr>
                    </p:sp>
                    <p:cxnSp>
                      <p:nvCxnSpPr><p:cNvPr id="5" name="Elbow"/><p:cNvCxnSpPr/><p:nvPr/></p:nvCxnSpPr>
                      <p:spPr><a:xfrm><a:off x="6000000" y="1371600"/><a:ext cx="1000000" cy="1000000"/></a:xfrm>
                        <a:prstGeom prst="bentConnector3"><a:avLst/></a:prstGeom>
                        <a:ln w="12700"><a:solidFill><a:srgbClr val="123456"/></a:solidFill></a:ln></p:spPr>
                    </p:cxnSp>
                  </p:spTree></p:cSld>
                </p:sldLayout>
                """;
        String layoutRels = """
                <?xml version="1.0" encoding="UTF-8"?>
                <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
                  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/>
                </Relationships>
                """;
        byte[] deck = withPart(withPart(placeholderDeckPptx(), "ppt/slideLayouts/slideLayout1.xml", layout),
                "ppt/slideLayouts/_rels/slideLayout1.xml.rels", layoutRels);

        List<TemplateManifest.Element> decor = new PowerPointTemplateParser().parseWithAssets(deck, true).manifest()
                .getLayouts().get(0).getDecor();

        // "\" down to the right: the line shape turned to its angle, about its centre.
        TemplateManifest.Element falling = decor.stream().filter(item -> "#FF0000".equals(item.getBorderColor())).findFirst().orElseThrow();
        assertThat(falling.getStyle()).containsEntry("shape", "line");
        assertThat(falling.getRotation()).isBetween(29d, 32d);       // atan(135/240) = 29.4 degrees
        assertThat(falling.getWidth()).isBetween(274d, 277d);        // the line's length
        // "/" is the same line turned the other way.
        TemplateManifest.Element rising = decor.stream().filter(item -> "#00AA00".equals(item.getBorderColor())).findFirst().orElseThrow();
        assertThat(rising.getRotation()).isBetween(-32d, -29d);
        // A dashed rule stays a dashed line instead of becoming a solid bar.
        TemplateManifest.Element dashed = decor.stream().filter(item -> "#0000FF".equals(item.getBorderColor())).findFirst().orElseThrow();
        assertThat(dashed.getStyle()).containsEntry("shape", "line").containsEntry("dash", "dash");
        // A hairline rectangle (a fraction bar) is kept as a rule in its fill colour.
        assertThat(decor).anyMatch(item -> "#222222".equals(item.getFill()) && item.getHeight() < 3 && item.getWidth() > 70);
        // An elbow connector drawn as a straight line would be wrong, so it is left out.
        assertThat(decor).noneMatch(item -> "#123456".equals(item.getBorderColor()));
    }

    /** The same package with another slide in place of its first one. */
    private byte[] withSlide(byte[] pptx, String slideXml) throws Exception {
        return withPart(pptx, "ppt/slides/slide1.xml", slideXml);
    }

    /** The same package with one part replaced, or added when the package has none by that name. */
    private byte[] withPart(byte[] pptx, String partName, String xml) throws Exception {
        ByteArrayOutputStream output = new ByteArrayOutputStream();
        boolean replaced = false;
        try (java.util.zip.ZipInputStream input = new java.util.zip.ZipInputStream(new java.io.ByteArrayInputStream(pptx));
             ZipOutputStream zip = new ZipOutputStream(output)) {
            ZipEntry entry;
            while ((entry = input.getNextEntry()) != null) {
                byte[] content = input.readAllBytes();
                boolean target = partName.equals(entry.getName());
                replaced |= target;
                add(zip, entry.getName(), target ? xml.getBytes(StandardCharsets.UTF_8) : content);
            }
            if (!replaced) add(zip, partName, xml.getBytes(StandardCharsets.UTF_8));
        }
        return output.toByteArray();
    }

    private byte[] placeholderDeckPptx() throws Exception {
        String presentation = """
                <?xml version="1.0" encoding="UTF-8"?>
                <p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
                  <p:sldSz cx="12192000" cy="6858000"/>
                </p:presentation>
                """;
        String theme = """
                <?xml version="1.0" encoding="UTF-8"?>
                <a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
                  <a:themeElements>
                    <a:clrScheme name="Office">
                      <a:dk1><a:srgbClr val="111111"/></a:dk1>
                      <a:lt1><a:srgbClr val="FFFFFF"/></a:lt1>
                      <a:accent1><a:srgbClr val="008C7A"/></a:accent1>
                    </a:clrScheme>
                    <a:fontScheme name="Office">
                      <a:majorFont><a:latin typeface="Aptos Display"/></a:majorFont>
                      <a:minorFont><a:latin typeface="Aptos"/></a:minorFont>
                    </a:fontScheme>
                  </a:themeElements>
                </a:theme>
                """;
        String master = """
                <?xml version="1.0" encoding="UTF-8"?>
                <p:sldMaster xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
                  xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
                  <p:cSld><p:spTree/></p:cSld>
                </p:sldMaster>
                """;
        String layout = """
                <?xml version="1.0" encoding="UTF-8"?>
                <p:sldLayout xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
                  xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
                  <p:cSld name="Title and content"><p:spTree>
                    <p:sp>
                      <p:nvSpPr><p:cNvPr id="2" name="Title"/><p:cNvSpPr/><p:nvPr><p:ph type="title"/></p:nvPr></p:nvSpPr>
                      <p:spPr><a:xfrm><a:off x="609600" y="365760"/><a:ext cx="6096000" cy="914400"/></a:xfrm></p:spPr>
                    </p:sp>
                    <p:sp>
                      <p:nvSpPr><p:cNvPr id="3" name="Content"/><p:cNvSpPr/><p:nvPr><p:ph idx="1"/></p:nvPr></p:nvSpPr>
                      <p:spPr><a:xfrm><a:off x="609600" y="1828800"/><a:ext cx="10972800" cy="4114800"/></a:xfrm></p:spPr>
                    </p:sp>
                    <p:sp>
                      <p:nvSpPr><p:cNvPr id="4" name="Slide number"/><p:cNvSpPr/><p:nvPr><p:ph type="sldNum" idx="12"/></p:nvPr></p:nvSpPr>
                      <p:spPr><a:xfrm><a:off x="10972800" y="6400800"/><a:ext cx="609600" cy="274320"/></a:xfrm></p:spPr>
                    </p:sp>
                  </p:spTree></p:cSld>
                </p:sldLayout>
                """;
        // Both placeholders on the slide omit <a:xfrm>: PowerPoint stores nothing when a box has
        // not been moved from its layout.
        String slide = """
                <?xml version="1.0" encoding="UTF-8"?>
                <p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
                  xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
                  <p:cSld><p:spTree>
                    <p:sp>
                      <p:nvSpPr><p:cNvPr id="2" name="Title 1"/><p:cNvSpPr/><p:nvPr><p:ph type="title"/></p:nvPr></p:nvSpPr>
                      <p:spPr/>
                      <p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:t>Tieu de that</a:t></a:r></a:p></p:txBody>
                    </p:sp>
                    <p:sp>
                      <p:nvSpPr><p:cNvPr id="3" name="Content 2"/><p:cNvSpPr/><p:nvPr><p:ph idx="1"/></p:nvPr></p:nvSpPr>
                      <p:spPr/>
                      <p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:t>Noi dung that</a:t></a:r></a:p></p:txBody>
                    </p:sp>
                  </p:spTree></p:cSld>
                </p:sld>
                """;
        String relationships = """
                <?xml version="1.0" encoding="UTF-8"?>
                <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
                  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
                </Relationships>
                """;

        ByteArrayOutputStream output = new ByteArrayOutputStream();
        try (ZipOutputStream zip = new ZipOutputStream(output)) {
            add(zip, "ppt/presentation.xml", presentation);
            add(zip, "ppt/theme/theme1.xml", theme);
            add(zip, "ppt/slideMasters/slideMaster1.xml", master);
            add(zip, "ppt/slideLayouts/slideLayout1.xml", layout);
            add(zip, "ppt/slides/slide1.xml", slide);
            add(zip, "ppt/slides/_rels/slide1.xml.rels", relationships);
        }
        return output.toByteArray();
    }

    private byte[] minimalPptx() throws Exception {
        String presentation = """
                <?xml version="1.0" encoding="UTF-8"?>
                <p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
                  <p:sldSz cx="12192000" cy="6858000"/>
                </p:presentation>
                """;
        String theme = """
                <?xml version="1.0" encoding="UTF-8"?>
                <a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
                  <a:themeElements>
                    <a:clrScheme name="Office">
                      <a:dk1><a:srgbClr val="000000"/></a:dk1>
                      <a:lt1><a:srgbClr val="FFFFFF"/></a:lt1>
                      <a:accent1><a:srgbClr val="4472C4"/></a:accent1>
                    </a:clrScheme>
                    <a:fontScheme name="Office">
                      <a:majorFont><a:latin typeface="Aptos Display"/></a:majorFont>
                      <a:minorFont><a:latin typeface="Aptos"/></a:minorFont>
                    </a:fontScheme>
                  </a:themeElements>
                </a:theme>
                """;
        String master = """
                <?xml version="1.0" encoding="UTF-8"?>
                <p:sldMaster xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
                  xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
                  <p:cSld><p:spTree>
                    <p:sp>
                      <p:nvSpPr><p:cNvPr id="2" name="Title"/><p:cNvSpPr/><p:nvPr><p:ph type="title"/></p:nvPr></p:nvSpPr>
                      <p:spPr><a:xfrm><a:off x="609600" y="365760"/><a:ext cx="10972800" cy="914400"/></a:xfrm></p:spPr>
                    </p:sp>
                  </p:spTree></p:cSld>
                </p:sldMaster>
                """;
        String layout = """
                <?xml version="1.0" encoding="UTF-8"?>
                <p:sldLayout xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
                  xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
                  <p:cSld name="Title and Content"><p:spTree>
                    <p:sp>
                      <p:nvSpPr><p:cNvPr id="2" name="Title"/><p:cNvSpPr/><p:nvPr><p:ph type="title"/></p:nvPr></p:nvSpPr>
                      <p:spPr><a:xfrm><a:off x="609600" y="365760"/><a:ext cx="10972800" cy="914400"/></a:xfrm></p:spPr>
                    </p:sp>
                    <p:sp>
                      <p:nvSpPr><p:cNvPr id="3" name="Content"/><p:cNvSpPr/><p:nvPr><p:ph type="body"/></p:nvPr></p:nvSpPr>
                      <p:spPr><a:xfrm><a:off x="914400" y="1524000"/><a:ext cx="10363200" cy="4267200"/></a:xfrm></p:spPr>
                    </p:sp>
                  </p:spTree></p:cSld>
                </p:sldLayout>
                """;

        ByteArrayOutputStream output = new ByteArrayOutputStream();
        try (ZipOutputStream zip = new ZipOutputStream(output)) {
            add(zip, "ppt/presentation.xml", presentation);
            add(zip, "ppt/theme/theme1.xml", theme);
            add(zip, "ppt/slideMasters/slideMaster1.xml", master);
            add(zip, "ppt/slideLayouts/slideLayout1.xml", layout);
        }
        return output.toByteArray();
    }

    private byte[] sampleSlidePptx() throws Exception {
        String presentation = """
                <?xml version="1.0" encoding="UTF-8"?>
                <p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
                  <p:sldSz cx="12192000" cy="6858000"/>
                </p:presentation>
                """;
        String theme = """
                <?xml version="1.0" encoding="UTF-8"?>
                <a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
                  <a:themeElements>
                    <a:clrScheme name="Office">
                      <a:dk1><a:srgbClr val="111111"/></a:dk1>
                      <a:lt1><a:srgbClr val="FFFFFF"/></a:lt1>
                      <a:dk2><a:srgbClr val="333333"/></a:dk2>
                      <a:lt2><a:srgbClr val="EEEEEE"/></a:lt2>
                      <a:accent1><a:srgbClr val="008C7A"/></a:accent1>
                    </a:clrScheme>
                    <a:fontScheme name="Office">
                      <a:majorFont><a:latin typeface="Aptos Display"/></a:majorFont>
                      <a:minorFont><a:latin typeface="Aptos"/></a:minorFont>
                    </a:fontScheme>
                  </a:themeElements>
                </a:theme>
                """;
        String slide = """
                <?xml version="1.0" encoding="UTF-8"?>
                <p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
                  xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
                  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
                  <p:cSld>
                    <p:bg><p:bgPr><a:blipFill><a:blip r:embed="rId1"/></a:blipFill></p:bgPr></p:bg>
                    <p:spTree>
                      <p:sp>
                        <p:nvSpPr><p:cNvPr id="2" name="Photo shape"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
                        <p:spPr>
                          <a:xfrm><a:off x="6705600" y="914400"/><a:ext cx="4267200" cy="4572000"/></a:xfrm>
                          <a:blipFill><a:blip r:embed="rId2"/></a:blipFill>
                        </p:spPr>
                      </p:sp>
                      <p:sp>
                        <p:nvSpPr><p:cNvPr id="4" name="Translucent panel"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
                        <p:spPr>
                          <a:xfrm><a:off x="0" y="0"/><a:ext cx="5486400" cy="6858000"/></a:xfrm>
                          <a:solidFill><a:schemeClr val="bg1"><a:alpha val="23000"/></a:schemeClr></a:solidFill>
                        </p:spPr>
                      </p:sp>
                      <p:sp>
                        <p:nvSpPr><p:cNvPr id="3" name="Sample title"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
                        <p:spPr><a:xfrm><a:off x="609600" y="914400"/><a:ext cx="5486400" cy="1524000"/></a:xfrm></p:spPr>
                        <p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r>
                          <a:rPr sz="4200"><a:solidFill><a:schemeClr val="bg1"/></a:solidFill></a:rPr>
                          <a:t>Sample title</a:t>
                        </a:r></a:p></p:txBody>
                      </p:sp>
                    </p:spTree>
                  </p:cSld>
                </p:sld>
                """;
        String relationships = """
                <?xml version="1.0" encoding="UTF-8"?>
                <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
                  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/background.png"/>
                  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/photo.png"/>
                </Relationships>
                """;

        ByteArrayOutputStream output = new ByteArrayOutputStream();
        try (ZipOutputStream zip = new ZipOutputStream(output)) {
            add(zip, "ppt/presentation.xml", presentation);
            add(zip, "ppt/theme/theme1.xml", theme);
            add(zip, "ppt/slides/slide1.xml", slide);
            add(zip, "ppt/slides/_rels/slide1.xml.rels", relationships);
            add(zip, "ppt/media/background.png", new byte[]{1, 2, 3});
            add(zip, "ppt/media/photo.png", new byte[]{4, 5, 6});
        }
        return output.toByteArray();
    }

    private void add(ZipOutputStream zip, String path, String value) throws Exception {
        add(zip, path, value.getBytes(StandardCharsets.UTF_8));
    }

    private void add(ZipOutputStream zip, String path, byte[] value) throws Exception {
        zip.putNextEntry(new ZipEntry(path));
        zip.write(value);
        zip.closeEntry();
    }
}
