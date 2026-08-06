package com.backend.templateservice.service;

import com.backend.templateservice.dto.manifest.TemplateManifest;
import com.backend.templateservice.dto.request.TemplateMatchRequest;
import com.backend.templateservice.dto.response.TemplateMatchResponse;
import org.junit.jupiter.api.Test;

import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.List;
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
        assertThat(match.getElements()).extracting(item -> item.get("role"))
                .contains("background", "title", "body");
        assertThat(match.getElements().stream()
                .filter(item -> "title".equals(item.get("role")))
                .findFirst()
                .orElseThrow()
                .get("content")).isEqualTo("Template upload");
    }

    @Test
    void parsesImageFrameAndThemeColorsWithoutEmbeddedMedia() throws Exception {
        TemplateManifest manifest = new PowerPointTemplateParser().parse(sampleSlidePptx());

        assertThat(manifest.getAssets()).isEmpty();
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
        assertThat(match.getElements()).filteredOn(item -> "image".equals(item.get("type")))
                .singleElement()
                .satisfies(item -> assertThat(item.get("src")).isEqualTo("https://example.test/generated.png"));
        assertThat(match.getElements()).filteredOn(item -> "title".equals(item.get("role")))
                .extracting(item -> item.get("content"))
                .containsExactly("New title");

        TemplateMatchResponse emptyFrameMatch = new TemplateLayoutMatcher().match(
                manifest,
                TemplateMatchRequest.builder().title("No generated image yet").pageIndex(0).build()
        );
        assertThat(emptyFrameMatch.getElements()).filteredOn(item -> "image".equals(item.get("type")))
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
        TemplateManifest manifest = TemplateManifest.builder()
                .layouts(List.of(TemplateManifest.Layout.builder()
                        .id("legacy-layout")
                        .type("title")
                        .backgroundColor("#FFFFFF")
                        .elements(List.of(legacyImage))
                        .build()))
                .build();

        TemplateMatchResponse match = new TemplateLayoutMatcher().match(
                manifest,
                TemplateMatchRequest.builder().title("New title").pageIndex(0).build()
        );

        assertThat(match.getElements()).noneMatch(item -> "image".equals(item.get("type")));
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
