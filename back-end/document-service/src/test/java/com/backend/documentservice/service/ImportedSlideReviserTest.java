package com.backend.documentservice.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class ImportedSlideReviserTest {

    private final ObjectMapper mapper = new ObjectMapper();
    private final ImportedSlideReviser reviser = new ImportedSlideReviser(mapper);

    private static final String IMPORTED = "{\"_imported\":true,\"_decor\":[{\"id\":\"pic\"}]}";

    private static final String BOXES = """
            [
              {"id":"t","type":"text","role":"title","x":313,"y":23,"width":309,"height":40,
               "content":"<p>Nội dung môn học</p>","style":{"fontFamily":"Times New Roman","textAlign":"center","fontSize":28}},
              {"id":"b","type":"text","role":"body","x":58,"y":96,"width":527,"height":348,
               "content":"<ul><li>Giới thiệu về Hệ gợi ý</li><li>Gợi ý dựa trên lọc cộng tác</li><li>Gợi ý dựa trên nội dung</li></ul>",
               "style":{"fontFamily":"Times New Roman","fontSize":20}},
              {"id":"u","type":"text","role":"body","x":669,"y":504,"width":129,"height":17,
               "content":"<p>http://www.ptit.edu.vn</p>","style":{"fontSize":10}}
            ]
            """;

    @Test
    void newWordsGoIntoTheOldBoxesAndKeepTheirStyle() throws Exception {
        ImportedSlideReviser.Poured poured = reviser.pour(
                IMPORTED, BOXES, "Nội dung môn học (tóm tắt)", List.of("Tổng quan Hệ gợi ý.", "Lọc cộng tác."));

        assertThat(poured).isNotNull();
        JsonNode boxes = mapper.readTree(poured.elementsJson());
        assertThat(boxes).hasSize(3);
        JsonNode title = boxes.get(0);
        assertThat(title.path("content").asText()).isEqualTo("<p>Nội dung môn học (tóm tắt)</p>");
        // Position, font and alignment of the file's own box are untouched.
        assertThat(title.path("x").asInt()).isEqualTo(313);
        assertThat(title.path("style").path("fontFamily").asText()).isEqualTo("Times New Roman");
        assertThat(title.path("style").path("textAlign").asText()).isEqualTo("center");
        JsonNode body = boxes.get(1);
        assertThat(body.path("content").asText())
                .isEqualTo("<ul><li>Tổng quan Hệ gợi ý.</li><li>Lọc cộng tác.</li></ul>");
        assertThat(body.path("width").asInt()).isEqualTo(527);
        // The footer address is a short side note: it stays where the file put it.
        assertThat(boxes.get(2).path("content").asText()).isEqualTo("<p>http://www.ptit.edu.vn</p>");
        assertThat(boxes.get(2).path("y").asInt()).isEqualTo(504);
    }

    @Test
    void bulletsReadTheSameAsTheBodyBoxesSoTheEditorKeepsTheLayout() {
        ImportedSlideReviser.Poured poured = reviser.pour(
                IMPORTED, BOXES, "Tiêu đề", List.of("Ý một", "Ý hai"));

        // The editor drops stored boxes whose text disagrees with the slide's bullets, so the
        // bullets must list the body boxes in order, footer included.
        assertThat(poured.bullets()).containsExactly("Ý một", "Ý hai", "http://www.ptit.edu.vn");
    }

    @Test
    void aSecondContentBoxIsDroppedBecauseItsOldWordsWereReplaced() throws Exception {
        String twoColumns = """
                [
                  {"id":"l","type":"text","role":"body","x":40,"y":100,"width":400,"height":300,
                   "content":"<ul><li>Cột trái một</li><li>Cột trái hai</li></ul>","style":{}},
                  {"id":"r","type":"text","role":"body","x":480,"y":100,"width":400,"height":300,
                   "content":"<ul><li>Cột phải một</li><li>Cột phải hai</li></ul>","style":{}}
                ]
                """;
        ImportedSlideReviser.Poured poured = reviser.pour(IMPORTED, twoColumns, "", List.of("Chỉ còn một ý"));

        JsonNode boxes = mapper.readTree(poured.elementsJson());
        assertThat(boxes).hasSize(1);
        // The old box was a list, so the single remaining point stays a list item.
        assertThat(boxes.get(0).path("content").asText()).isEqualTo("<ul><li>Chỉ còn một ý</li></ul>");
        assertThat(poured.bullets()).containsExactly("Chỉ còn một ý");
    }

    @Test
    void textIsEscapedSoItCannotInjectMarkup() throws Exception {
        ImportedSlideReviser.Poured poured = reviser.pour(
                IMPORTED, BOXES, "A & B <script>", List.of("x < y & z"));

        JsonNode boxes = mapper.readTree(poured.elementsJson());
        assertThat(boxes.get(0).path("content").asText()).isEqualTo("<p>A &amp; B &lt;script&gt;</p>");
        assertThat(boxes.get(1).path("content").asText()).contains("x &lt; y &amp; z");
        assertThat(poured.bullets()).contains("x < y & z");
    }

    @Test
    void aSlideThatWasNotOpenedFromAFileIsLeftToTheNormalLayout() {
        assertThat(reviser.pour("{}", BOXES, "T", List.of("a"))).isNull();
        assertThat(reviser.pour(null, BOXES, "T", List.of("a"))).isNull();
        // An opened slide with nothing to put the bullets in also falls back.
        String onlyTitle = "[{\"id\":\"t\",\"type\":\"text\",\"role\":\"title\",\"content\":\"<p>x</p>\"}]";
        assertThat(reviser.pour(IMPORTED, onlyTitle, "T", List.of("a"))).isNull();
        assertThat(reviser.pour(IMPORTED, BOXES, "T", List.of())).isNull();
    }
}
