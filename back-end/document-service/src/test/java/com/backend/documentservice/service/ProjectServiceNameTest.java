package com.backend.documentservice.service;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class ProjectServiceNameTest {

    @Test
    void removesRoleInstructionFromVietnamesePrompt() {
        assertEquals(
                "Tổng quan IELTS",
                ProjectService.buildConciseProjectName(
                        "Tổng quan IELTS. Bạn là chuyên gia luyện thi, hãy tạo nội dung chi tiết.",
                        null
                )
        );
    }

    @Test
    void removesLeadingRoleSentenceBeforeExtractingTopic() {
        assertEquals(
                "IELTS Speaking",
                ProjectService.buildConciseProjectName(
                        "Bạn là chuyên gia luyện thi IELTS và thiết kế bài giảng. Hãy tạo 15 slide về IELTS Speaking.",
                        null
                )
        );
    }

    @Test
    void removesSlideCommandAndLanguageMetadata() {
        assertEquals(
                "Ứng dụng AI trong giáo dục",
                ProjectService.buildConciseProjectName(
                        "Tạo đúng 10 slide bằng tiếng Việt về Ứng dụng AI trong giáo dục. Yêu cầu: có ví dụ.",
                        null
                )
        );
    }

    @Test
    void usesCleanFileNameWhenPromptIsMissing() {
        assertEquals(
                "Thinkpython2 copy",
                ProjectService.buildConciseProjectName(null, "thinkpython2_copy.pdf")
        );
    }
}
