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

    private void add(ZipOutputStream zip, String path, String value) throws Exception {
        zip.putNextEntry(new ZipEntry(path));
        zip.write(value.getBytes(StandardCharsets.UTF_8));
        zip.closeEntry();
    }
}
