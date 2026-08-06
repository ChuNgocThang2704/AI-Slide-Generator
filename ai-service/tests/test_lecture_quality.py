import asyncio
import unittest

from routes.api import (
    _build_slide_spec_payload,
    _clean_visual_schema_bullets,
    _infer_slide_layout,
    _resolve_unique_visual_specs,
    _structured_content_from_spec_payload,
)
from services.content_extractor import ContentExtractor
from services.lecture_quality import (
    build_source_page_index,
    detect_lecture_mode,
    enrich_lecture_deck,
    excerpt_from_source_pages,
    has_explicit_structural_scope,
    lecture_prompt_block,
    select_relevant_source_excerpt,
)
from services.slide_quality import _preserve_lecture_density, _preserve_slide_layouts
from services.slide_tables import _table_spec_has_text_evidence
from services.slide_text_quality import _deck_title_needs_review, _sanitize_inline_markup
from services.text_utils import plain_slide_text


class LectureQualityTests(unittest.TestCase):
    def test_detects_textbook_but_not_generic_business_prompt(self):
        textbook = (
            "[[SOURCE_PAGE:1]]\nChapter 3 Functions\n"
            "3.1 Function calls\nExample 3.1 demonstrates a function call.\n"
            "[[SOURCE_PAGE:2]]\n3.2 Math functions\nExercise 3.2 asks students to practice."
        )
        self.assertTrue(detect_lecture_mode(textbook))
        self.assertFalse(
            detect_lecture_mode(
                "Create a sales presentation about quarterly revenue and market growth."
            )
        )

    def test_explicit_lecture_request_enables_mode(self):
        self.assertTrue(
            detect_lecture_mode(
                "Python functions",
                "Create a lecture for beginner students with learning objectives.",
            )
        )

    def test_explicit_presentation_request_overrides_textbook_source(self):
        textbook = (
            "Chapter 2 Variables and Statements. Learning objectives and exercises. "
            "This lesson is part of a programming course curriculum."
        )
        self.assertFalse(
            detect_lecture_mode(
                textbook,
                "Create 8 English presentation slides introducing the key ideas.",
            )
        )
        self.assertFalse(
            detect_lecture_mode(
                textbook,
                "Tao 8 slide tieng Viet gioi thieu cac kien thuc quan trong.",
            )
        )

    def test_explicit_lecture_still_wins_when_request_mentions_slides(self):
        self.assertTrue(
            detect_lecture_mode(
                "Chapter 2 Variables",
                "Create 10 lecture slides with learning objectives and examples.",
            )
        )

    def test_chart_layout_requires_a_valid_chart_payload(self):
        layout, primary = _infer_slide_layout(
            None,
            None,
            None,
            {"layout": "text_chart"},
        )
        self.assertEqual((layout, primary), ("text_only", None))

    def test_internal_chart_schema_is_not_exposed_as_bullets(self):
        bullets = [
            "chart",
            "type: bar",
            "title: Revenue trend",
            "x_axis: Year",
            "data:",
            "year: 2018, revenue: 8",
        ]
        cleaned = _clean_visual_schema_bullets(
            bullets,
            title="Doanh thu TMĐT Việt Nam",
            has_chart=False,
        )
        self.assertEqual(len(cleaned), 1)
        self.assertIn("chưa đủ", cleaned[0])

    def test_valid_chart_hides_schema_without_adding_warning(self):
        cleaned = _clean_visual_schema_bullets(
            ["chart", "type: line", "labels: 2020 | 2021", "values: 8 | 12"],
            title="Revenue",
            has_chart=True,
        )
        self.assertEqual(cleaned, [])

    def test_lecture_contract_requires_grounded_technical_examples(self):
        contract = lecture_prompt_block()
        self.assertIn("concrete, source-grounded example", contract)
        self.assertIn("valid code", contract)
        self.assertIn("unsupported absolutes", contract)

    def test_vietnamese_lecture_request_in_source_enables_mode(self):
        self.assertTrue(
            detect_lecture_mode(
                "Tạo 12 slide bài giảng bằng tiếng Việt cho sinh viên mới bắt đầu.",
                "",
            )
        )

    def test_enrichment_adds_roles_and_matches_source_pages(self):
        source = (
            "[[SOURCE_PAGE:10]]\n"
            "A variable is a name that refers to a value. Assignment creates a variable.\n"
            "[[SOURCE_PAGE:11]]\n"
            "Python functions can take arguments and return values. Function calls use parentheses.\n"
            "[[SOURCE_PAGE:12]]\n"
            "Exercises ask students to define a function and inspect its return value.\n"
        )
        deck = {
            "title": "Python Foundations",
            "presentation_mode": "lecture",
            "slides": [
                {
                    "title": "Learning Objectives",
                    "bullets": ["Explain how Python function calls use arguments and return values."],
                    "notes": "Introduce the expected learning outcome.",
                },
                {
                    "title": "Function Calls",
                    "bullets": ["Python function calls use parentheses and may return values."],
                    "notes": "Explain the mechanics of a function call.",
                },
                {
                    "title": "Practice Exercise",
                    "bullets": ["Define a function and inspect the value it returns."],
                    "notes": "Ask learners to complete the exercise.",
                },
            ],
        }
        result = enrich_lecture_deck(deck, source)
        self.assertEqual(result["presentation_mode"], "lecture")
        self.assertEqual(result["slides"][0]["pedagogical_role"], "learning_objectives")
        self.assertIn(11, result["slides"][1]["source_pages"])
        self.assertEqual(result["slides"][2]["pedagogical_role"], "practice")
        self.assertTrue(result["learning_objectives"])

    def test_enrichment_inserts_missing_learning_objectives_slide(self):
        deck = {
            "title": "Python Variables",
            "presentation_mode": "lecture",
            "learning_objectives": [
                "Explain variables and assignment.",
                "Apply expressions in short programs.",
            ],
            "slides": [
                {
                    "title": "Python Variables",
                    "layout": "intro",
                    "bullets": ["A beginner lecture."],
                },
                {
                    "title": "Variables and Assignment",
                    "layout": "normal",
                    "bullets": ["A variable refers to a value."],
                },
            ],
        }

        result = enrich_lecture_deck(deck, "", "Create a lecture in English.")

        self.assertEqual(result["slides"][0]["layout"], "intro")
        self.assertEqual(result["slides"][1]["pedagogical_role"], "learning_objectives")
        self.assertEqual(result["slides"][1]["title"], "Learning Objectives")

    def test_enrichment_derives_objectives_from_real_slide_topics(self):
        deck = {
            "title": "Python Variables",
            "presentation_mode": "lecture",
            "learning_objectives": [],
            "slides": [
                {"title": "Python Variables", "layout": "intro", "bullets": ["Overview."]},
                {"title": "Assignment Statements", "bullets": ["Assignment binds a name."]},
                {"title": "Expression Evaluation", "bullets": ["Operators produce values."]},
                {"title": "Operator Precedence", "bullets": ["Precedence controls order."]},
                {"title": "Summary", "layout": "thankyou", "bullets": ["Review."]},
            ],
        }

        result = enrich_lecture_deck(deck, "", "Create a beginner lecture in English.")

        objective_slide = next(
            slide
            for slide in result["slides"]
            if slide.get("pedagogical_role") == "learning_objectives"
        )
        self.assertEqual(objective_slide["title"], "Learning Objectives")
        self.assertGreaterEqual(len(objective_slide["bullets"]), 2)
        self.assertTrue(any("assignment" in item.lower() for item in objective_slide["bullets"]))

    def test_enrichment_reuses_knowledge_check_as_requested_practice(self):
        deck = {
            "title": "Biến trong Python",
            "presentation_mode": "lecture",
            "learning_objectives": ["Giải thích biến.", "Vận dụng phép gán."],
            "slides": [
                {"title": "Biến trong Python", "layout": "intro", "bullets": ["Tổng quan."]},
                {
                    "title": "Kiểm tra lỗi phép gán",
                    "pedagogical_role": "knowledge_check",
                    "bullets": ["Tìm lỗi trong đoạn mã."],
                },
                {"title": "Tổng kết", "layout": "thankyou", "bullets": ["Ôn tập."]},
            ],
        }

        result = enrich_lecture_deck(
            deck,
            "",
            "Tạo bài giảng có một slide bài tập thực hành.",
        )

        practice = next(
            slide for slide in result["slides"] if slide.get("pedagogical_role") == "practice"
        )
        self.assertIn("Bài tập thực hành", practice["title"])
        self.assertEqual(practice["bullets"], ["Tìm lỗi trong đoạn mã."])

    def test_enrichment_reuses_existing_objective_titled_slide(self):
        deck = {
            "title": "Biến trong Python",
            "presentation_mode": "lecture",
            "learning_objectives": ["Giải thích biến.", "Vận dụng phép gán."],
            "slides": [
                {"title": "Biến trong Python", "layout": "intro", "bullets": ["Tổng quan."]},
                {
                    "title": "Giới thiệu và Mục tiêu bài học",
                    "pedagogical_role": "concept",
                    "bullets": ["Nội dung bài học."],
                },
                {"title": "Phép gán", "bullets": ["Phép gán liên kết tên với giá trị."]},
                {"title": "Tổng kết", "layout": "thankyou", "bullets": ["Ôn tập."]},
            ],
        }

        result = enrich_lecture_deck(deck, "", "Tạo bài giảng bằng tiếng Việt.")
        objective_slides = [
            slide
            for slide in result["slides"]
            if slide.get("pedagogical_role") == "learning_objectives"
        ]

        self.assertEqual(len(objective_slides), 1)
        self.assertEqual(objective_slides[0]["bullets"], deck["learning_objectives"])

    def test_enrichment_creates_requested_practice_from_content_fallback(self):
        deck = {
            "title": "Biến trong Python",
            "presentation_mode": "lecture",
            "learning_objectives": ["Giải thích biến.", "Vận dụng phép gán."],
            "slides": [
                {"title": "Biến trong Python", "layout": "intro", "bullets": ["Tổng quan."]},
                {"title": "Phép gán", "bullets": ["Phép gán liên kết tên với giá trị."]},
                {"title": "Từ khóa", "bullets": ["Không dùng từ khóa làm tên biến."]},
                {"title": "Tổng kết", "layout": "thankyou", "bullets": ["Ôn tập."]},
            ],
        }

        result = enrich_lecture_deck(
            deck,
            "",
            "Tạo bài giảng có một slide bài tập thực hành.",
        )
        practice = next(
            slide for slide in result["slides"] if slide.get("pedagogical_role") == "practice"
        )

        self.assertIn("Bài tập thực hành", practice["title"])
        self.assertEqual(len(practice["bullets"]), 3)

    def test_enrichment_merges_or_removes_dangling_bullet_labels(self):
        deck = {
            "presentation_mode": "lecture",
            "slides": [
                {
                    "title": "Assignment",
                    "bullets": [
                        "Key rule:",
                        "Assignment binds a name to a value.",
                        "Example:",
                    ],
                }
            ],
        }
        result = enrich_lecture_deck(deck, "")
        self.assertEqual(
            result["slides"][0]["bullets"],
            ["Key rule: Assignment binds a name to a value."],
        )

    def test_low_confidence_source_page_is_not_attached(self):
        source = (
            "[[SOURCE_PAGE:1]]\nCloud infrastructure and deployment regions.\n"
            "[[SOURCE_PAGE:2]]\nFinancial accounting and annual statements.\n"
        )
        deck = {
            "presentation_mode": "lecture",
            "slides": [
                {
                    "title": "Python Comments",
                    "bullets": ["Comments explain code intent."],
                }
            ],
        }
        result = enrich_lecture_deck(deck, source)
        self.assertEqual(result["slides"][0]["source_pages"], [])

    def test_deck_title_matching_objective_label_requires_review(self):
        deck = {
            "title": "Mục tiêu học tập",
            "slides": [
                {
                    "title": "Mục tiêu học tập",
                    "pedagogical_role": "learning_objectives",
                    "bullets": ["Giải thích biến và biểu thức."],
                },
                {
                    "title": "Biến trong Python",
                    "pedagogical_role": "concept",
                    "bullets": ["Biến tham chiếu đến một giá trị."],
                },
            ],
        }
        self.assertTrue(_deck_title_needs_review(deck))

    def test_late_learning_objectives_are_moved_after_intro(self):
        deck = {
            "title": "Python Functions",
            "presentation_mode": "lecture",
            "slides": [
                {"title": "Introduction to Functions", "bullets": ["Why functions matter."]},
                {"title": "Function Calls", "bullets": ["A call executes a function."]},
                {"title": "Learning Objectives", "bullets": ["Explain parameters and return values."]},
            ],
        }
        result = enrich_lecture_deck(deck, "")
        self.assertEqual(result["slides"][0]["title"], "Introduction to Functions")
        self.assertEqual(result["slides"][1]["title"], "Learning Objectives")

    def test_normalizer_preserves_lecture_metadata(self):
        extractor = ContentExtractor()
        normalized = extractor._normalize_structured_content(
            {
                "title": "Python Functions",
                "presentation_mode": "lecture",
                "learning_objectives": ["Explain function calls and return values."],
                "slides": [
                    {
                        "title": "Function Calls",
                        "bullets": [
                            "A Python function call executes reusable code with supplied arguments.",
                            "Parentheses distinguish a function call from an ordinary variable reference.",
                            "A return value lets the caller reuse the result in another expression.",
                        ],
                        "notes": "Explain the relationship between the caller, arguments, and returned result.",
                        "pedagogical_role": "concept",
                        "source_pages": [10, 11],
                    }
                ],
            }
        )
        self.assertEqual(normalized["presentation_mode"], "lecture")
        self.assertEqual(normalized["slides"][0]["pedagogical_role"], "concept")
        self.assertEqual(normalized["slides"][0]["source_pages"], [10, 11])

    def test_spec_round_trip_preserves_lecture_fields(self):
        structured = {
            "title": "Python Functions",
            "presentation_mode": "lecture",
            "learning_objectives": ["Explain function calls."],
            "slides": [
                {
                    "title": "Function Calls",
                    "bullets": ["A function call executes a named block of reusable Python code."],
                    "notes": "Explain the call and connect it to the following example.",
                    "pedagogical_role": "concept",
                    "source_pages": [4],
                }
            ],
        }
        payload = _build_slide_spec_payload(
            task_id="lecture-test",
            structured_content=structured,
            chart_specs={},
            table_specs={},
            image_paths={},
        )
        slide = payload["deck"]["slides"][0]
        self.assertEqual(payload["deck"]["presentation_mode"], "lecture")
        self.assertEqual(slide["pedagogical_role"], "concept")
        self.assertEqual(slide["source_pages"], [4])

        restored = _structured_content_from_spec_payload(payload)
        self.assertEqual(restored["presentation_mode"], "lecture")
        self.assertEqual(restored["slides"][0]["source_pages"], [4])

    def test_lecture_prompt_requires_pedagogy_without_inventing_sources(self):
        prompt = lecture_prompt_block()
        self.assertIn("learning objectives", prompt)
        self.assertIn("worked examples", prompt)
        self.assertIn("Never invent page numbers", prompt)

    def test_source_excerpt_follows_requested_chapter(self):
        source = "\n\n".join(
            [
                f"[[SOURCE_PAGE:{page}]]\nChapter 2 Variables\nAssignments and expressions. "
                + ("general text " * 100)
                for page in range(1, 5)
            ]
            + [
                f"[[SOURCE_PAGE:{page}]]\nChapter 3 Functions\nFunction calls, arguments, and return values. "
                + ("function example " * 100)
                for page in range(5, 9)
            ]
        )
        excerpt = select_relevant_source_excerpt(
            source,
            "Focus only on Chapter 3 Functions for beginner students.",
            max_chars=3000,
        )
        self.assertIn("Chapter 3 Functions", excerpt)
        self.assertNotIn("[[SOURCE_PAGE:1]]", excerpt)

    def test_source_excerpt_matches_vietnamese_chapter_request_to_english_source(self):
        source = "\n\n".join(
            [
                "[[SOURCE_PAGE:1]]\nChapter 2 Variables\nAssignments and expressions.",
                "[[SOURCE_PAGE:2]]\n2.8 Debugging\nSyntax, runtime, and semantic errors.",
                "[[SOURCE_PAGE:3]]\nChapter 3 Functions\nFunction calls and return values.",
                "[[SOURCE_PAGE:4]]\n3.3 Composition\nNested function calls and expressions.",
                "[[SOURCE_PAGE:5]]\n3.14 Exercises\nPractice defining functions.",
            ]
        )
        excerpt = select_relevant_source_excerpt(
            source,
            "Sinh 12 slide theo chương 3 trong file bài giảng.",
            max_chars=5000,
        )
        self.assertNotIn("Chapter 2 Variables", excerpt)
        self.assertNotIn("2.8 Debugging", excerpt)
        self.assertIn("Chapter 3 Functions", excerpt)
        self.assertIn("3.3 Composition", excerpt)
        self.assertIn("3.14 Exercises", excerpt)

    def test_scope_helpers_support_structural_and_semantic_selection(self):
        source = "\n\n".join(
            [
                "[[SOURCE_PAGE:1]]\nOverview of cloud infrastructure.",
                "[[SOURCE_PAGE:2]]\nFruitful functions return computed values.",
                "[[SOURCE_PAGE:3]]\nLocal variables exist only inside functions.",
                "[[SOURCE_PAGE:4]]\nNetwork deployment checklist.",
            ]
        )
        self.assertTrue(has_explicit_structural_scope("Sinh slide từ chương 3"))
        self.assertFalse(
            has_explicit_structural_scope(
                "Chỉ trình bày hàm trả về kết quả và phạm vi biến."
            )
        )
        index = build_source_page_index(source)
        self.assertIn("PAGE 2: Fruitful functions", index)
        excerpt = excerpt_from_source_pages(
            source,
            [2],
            include_neighbors=False,
        )
        self.assertIn("Fruitful functions", excerpt)
        self.assertNotIn("Network deployment", excerpt)

    def test_ai_scope_selection_handles_cross_language_semantic_request(self):
        extractor = ContentExtractor()
        extractor.vllm_available = True
        source = "\n\n".join(
            [
                "[[SOURCE_PAGE:1]]\nCloud infrastructure overview. " + ("cloud " * 80),
                "[[SOURCE_PAGE:2]]\nFruitful functions return computed values. " + ("return " * 80),
                "[[SOURCE_PAGE:3]]\nLocal variables and parameters. " + ("local " * 80),
                "[[SOURCE_PAGE:4]]\nNetwork deployment checklist. " + ("network " * 80),
            ]
        )

        async def fake_completion(*args, **kwargs):
            return '{"pages":[2,3],"confidence":0.91,"reason":"semantic match"}'

        extractor._llm_completion_plain_text = fake_completion
        excerpt = asyncio.run(
            extractor._focus_document_scope(
                source,
                "Chỉ trình bày hàm trả về kết quả và phạm vi biến.",
                max_chars=900,
            )
        )
        self.assertIn("Fruitful functions", excerpt)
        self.assertIn("Local variables", excerpt)
        self.assertNotIn("Network deployment", excerpt)

    def test_explicit_output_language_overrides_source_language_both_ways(self):
        extractor = ContentExtractor()
        english_source = "Functions accept arguments and may return values. " * 20
        vietnamese_source = "Hàm nhận đối số và có thể trả về giá trị. " * 20
        self.assertEqual(
            extractor._resolve_output_language_hint(
                english_source,
                "Hãy tạo bài giảng hoàn toàn bằng tiếng Việt.",
            ),
            "vi",
        )
        self.assertEqual(
            extractor._resolve_output_language_hint(
                vietnamese_source,
                "Create the entire lecture deck in English.",
            ),
            "en",
        )

    def test_instruction_language_overrides_source_when_output_language_is_implicit(self):
        extractor = ContentExtractor()
        english_source = "Variables, expressions, and statements in Python. " * 20
        vietnamese_source = "Biến, biểu thức và câu lệnh trong Python. " * 20
        self.assertEqual(
            extractor._resolve_output_language_hint(
                english_source,
                "Tạo 10 slide bài giảng từ chương 2 trong file.",
            ),
            "vi",
        )
        self.assertEqual(
            extractor._resolve_output_language_hint(
                vietnamese_source,
                "Create 10 lecture slides from chapter 2 of the document.",
            ),
            "en",
        )

    def test_grounding_review_cannot_make_lecture_slides_sparse(self):
        original = {
            "presentation_mode": "lecture",
            "slides": [
                {
                    "title": "Function Calls",
                    "pedagogical_role": "concept",
                    "source_pages": [4],
                    "bullets": ["One.", "Two.", "Three.", "Four."],
                },
                {
                    "title": "Review",
                    "pedagogical_role": "knowledge_check",
                    "bullets": ["Question one.", "Question two.", "Question three."],
                },
            ],
        }
        reviewed = {
            "slides": [
                {"title": "Function Calls", "bullets": ["One.", "Two."]},
                {"title": "Review", "bullets": ["Question one.", "Question two.", "Question three."]},
            ],
        }
        result = _preserve_lecture_density(reviewed, original)
        self.assertEqual(len(result["slides"][0]["bullets"]), 4)
        self.assertEqual(result["slides"][0]["source_pages"], [4])
        self.assertEqual(len(result["slides"][1]["bullets"]), 3)

    def test_grounding_review_preserves_cover_and_closing_layouts(self):
        original = {
            "slides": [
                {"title": "Python", "layout": "intro", "bullets": ["Lecture overview."]},
                {"title": "Questions", "layout": "thankyou", "bullets": ["Thank you."]},
            ]
        }
        reviewed = {
            "slides": [
                {"title": "Python", "bullets": ["Lecture overview."]},
                {"title": "Questions", "bullets": ["Thank you."]},
            ]
        }
        result = _preserve_slide_layouts(reviewed, original)
        self.assertEqual(result["slides"][0]["layout"], "intro")
        self.assertEqual(result["slides"][1]["layout"], "thankyou")

    def test_unified_review_requires_cover_and_closing_inside_slide_count(self):
        extractor = ContentExtractor()
        messages = extractor._build_unified_post_process_messages(
            {
                "title": "Python",
                "slides": [
                    {"title": "Variables", "bullets": ["Variables hold values."]},
                    {"title": "Review", "bullets": ["Review the lesson."]},
                ],
            }
        )
        contract = messages[0]["content"]
        self.assertIn("layout='intro'", contract)
        self.assertIn("layout='thankyou'", contract)
        self.assertIn("exact slide count", contract)

    def test_pipeline_guarantees_cover_and_closing_without_extra_slides(self):
        extractor = ContentExtractor()
        extractor._slide_lang_hint = "en"
        deck = {
            "title": "Python Foundations",
            "slides": [
                {
                    "title": f"Topic {index}",
                    "bullets": [f"Detailed concept {index}."],
                    "layout": "normal",
                }
                for index in range(1, 12)
            ],
        }
        result = extractor._ensure_deck_boundaries(deck, 12)
        self.assertEqual(len(result["slides"]), 12)
        self.assertEqual(result["slides"][0]["layout"], "intro")
        self.assertEqual(result["slides"][-1]["layout"], "thankyou")
        self.assertEqual(result["slides"][1]["title"], "Topic 1")

    def test_presentation_boundaries_do_not_use_lecture_copy(self):
        extractor = ContentExtractor()
        extractor._slide_lang_hint = "en"
        extractor._lecture_mode = False
        deck = {
            "title": "Cloud Computing",
            "presentation_mode": "presentation",
            "slides": [
                {"title": "Cloud Models", "bullets": ["Public, private, and hybrid clouds."]},
                {"title": "Benefits", "bullets": ["Cloud platforms improve scalability."]},
            ],
        }

        result = extractor._ensure_deck_boundaries(deck, 3)

        self.assertNotIn("lecture", result["slides"][0]["bullets"][0].lower())
        self.assertEqual(
            result["slides"][-1]["title"],
            "Closing thoughts: Cloud Computing",
        )

    def test_presentation_replaces_stale_lecture_intro_copy(self):
        extractor = ContentExtractor()
        extractor._slide_lang_hint = "en"
        extractor._lecture_mode = False
        deck = {
            "title": "Cloud Computing",
            "presentation_mode": "presentation",
            "slides": [
                {
                    "title": "Cloud Computing",
                    "layout": "intro",
                    "bullets": ["Lecture overview and key concepts."],
                },
                {"title": "Summary", "bullets": ["Cloud platforms scale on demand."]},
            ],
        }

        result = extractor._ensure_deck_boundaries(deck, 2)

        self.assertNotIn("lecture", result["slides"][0]["bullets"][0].lower())

    def test_boundary_preserves_ai_generated_closing_title(self):
        extractor = ContentExtractor()
        extractor._slide_lang_hint = "en"
        extractor._lecture_mode = False
        deck = {
            "title": "Cloud Computing",
            "presentation_mode": "presentation",
            "slides": [
                {"title": "Cloud Models", "bullets": ["Cloud platforms offer flexible models."]},
                {
                    "title": "The Cloud-Ready Future",
                    "layout": "thankyou",
                    "bullets": ["Cloud adoption enables flexible growth."],
                },
            ],
        }

        result = extractor._ensure_deck_boundaries(deck, 3)

        self.assertEqual(result["slides"][-1]["title"], "The Cloud-Ready Future")

    def test_boundary_uses_qa_closing_after_existing_conclusion(self):
        extractor = ContentExtractor()
        extractor._slide_lang_hint = "vi"
        extractor._lecture_mode = False
        deck = {
            "title": "Báo cáo nghiên cứu",
            "presentation_mode": "presentation",
            "slides": [
                {"title": "Báo cáo nghiên cứu", "layout": "intro", "bullets": ["Tổng quan."]},
                {"title": "Kết quả", "bullets": ["Độ chính xác đạt 95,76%."]},
                {"title": "Kết luận", "bullets": ["Kết quả xác nhận tính khả dụng của dữ liệu."]},
                {"title": "Kết luận: Báo cáo nghiên cứu", "bullets": ["Tóm tắt nội dung."]},
            ],
        }

        result = extractor._ensure_deck_boundaries(deck, 4)

        self.assertEqual(result["slides"][-2]["title"], "Kết luận")
        self.assertEqual(result["slides"][-1]["title"], "Cảm ơn và Hỏi đáp")
        self.assertEqual(result["slides"][-1]["layout"], "thankyou")

    def test_boundary_replaces_closing_about_a_topic_missing_from_body(self):
        extractor = ContentExtractor()
        extractor._slide_lang_hint = "en"
        extractor._lecture_mode = False
        deck = {
            "title": "Python Foundations",
            "presentation_mode": "presentation",
            "slides": [
                {"title": "Variables", "bullets": ["Variables store assigned values."]},
                {"title": "Expressions", "bullets": ["Expressions combine values and operators."]},
                {"title": "Interactive and Script Modes", "bullets": ["The two modes execute code differently."]},
                {
                    "title": "Summary",
                    "layout": "thankyou",
                    "bullets": [
                        "Syntax errors violate language rules.",
                        "Runtime errors interrupt program execution.",
                        "Semantic errors produce unintended results.",
                    ],
                },
            ],
        }

        result = extractor._ensure_deck_boundaries(deck, 5)

        closing_text = " ".join(result["slides"][-1]["bullets"]).lower()
        self.assertIn("variables", closing_text)
        self.assertIn("expressions", closing_text)
        self.assertNotIn("syntax errors", closing_text)

    def test_boundary_replaces_unfinished_practice_with_complete_closing(self):
        extractor = ContentExtractor()
        extractor._slide_lang_hint = "vi"
        deck = {
            "title": "Python",
            "learning_objectives": [
                "Giải thích biến và biểu thức trong Python.",
                "Áp dụng đúng thứ tự ưu tiên của toán tử.",
            ],
            "slides": [
                {"title": "Python", "layout": "intro", "bullets": ["Bài giảng Python."]},
                {
                    "title": "Bài tập",
                    "layout": "normal",
                    "pedagogical_role": "practice",
                    "bullets": ["Xác định lỗi trong các đoạn mã sau:", "1. print('Xin chào')"],
                },
            ],
        }
        result = extractor._ensure_deck_boundaries(deck, 2)
        closing = result["slides"][-1]
        self.assertEqual(closing["layout"], "thankyou")
        self.assertEqual(closing["pedagogical_role"], "summary")
        self.assertEqual(closing["bullets"], deck["learning_objectives"])
        self.assertNotIn("Xác định lỗi trong các đoạn mã sau:", closing["bullets"])

    def test_technical_sanitizer_preserves_python_operators_and_identifiers(self):
        text = "Use miles * 1.61, 2 ** 3, and obj.__init__() in this example."
        self.assertEqual(_sanitize_inline_markup(text), text)

    def test_slide_normalizer_preserves_python_operators_and_identifiers(self):
        extractor = ContentExtractor()
        text = "* Use '*' for repetition, 2 ** 3, and obj.__init__()."
        cleaned = extractor._sanitize_inline_markup(text)
        self.assertIn("'*'", cleaned)
        self.assertIn("2 ** 3", cleaned)
        self.assertIn("obj.__init__()", cleaned)

    def test_api_plain_text_preserves_python_operators_and_identifiers(self):
        text = "Use '*' for repetition, 2 ** 3, and obj.__init__()."
        self.assertEqual(plain_slide_text(text), text)

    def test_relevant_excerpt_excludes_unrequested_later_chapter(self):
        source = (
            "[[SOURCE_PAGE:1]]\nChapter 2 Variables Expressions Statements\n"
            + "assignment expression operator " * 80
            + "\n[[SOURCE_PAGE:2]]\nChapter 2 Variables Expressions Statements\n"
            + "variable assignment value " * 80
            + "\n[[SOURCE_PAGE:20]]\nChapter 3 Functions\n"
            + "function definition return recursion " * 80
        )
        excerpt = select_relevant_source_excerpt(
            source,
            "Create a lecture about Variables, Expressions and Statements from Chapter 2",
            max_chars=5000,
        )
        self.assertIn("Chapter 2", excerpt)
        self.assertNotIn("Chapter 3 Functions", excerpt)

    def test_boundary_pass_removes_fragmented_ascii_diagram_bullets(self):
        extractor = ContentExtractor()
        extractor._slide_lang_hint = "en"
        deck = {
            "title": "Variables",
            "slides": [
                {
                    "title": "Assignment",
                    "layout": "normal",
                    "bullets": [
                        "A variable refers to a stored value.",
                        "State diagram:",
                        "+-------+",
                        "message",
                        "+-------+",
                    ],
                },
                {"title": "Summary", "layout": "normal", "bullets": ["Review variables."]},
            ],
        }
        result = extractor._ensure_deck_boundaries(deck, 3)
        body = result["slides"][1]["bullets"]
        self.assertEqual(body, ["A variable refers to a stored value."])

    def test_boundary_moves_existing_intro_before_learning_objectives(self):
        extractor = ContentExtractor()
        extractor._slide_lang_hint = "vi"
        deck = {
            "title": "Biến, Biểu thức và Câu lệnh trong Python",
            "slides": [
                {
                    "title": "Mục tiêu học tập",
                    "layout": "normal",
                    "pedagogical_role": "learning_objectives",
                    "bullets": ["Giải thích được biến và biểu thức."],
                },
                {
                    "title": "Biến, Biểu thức và Câu lệnh trong Python",
                    "layout": "intro",
                    "bullets": ["Bài giảng cho người mới bắt đầu."],
                },
                {
                    "title": "Tổng kết",
                    "layout": "normal",
                    "bullets": ["Ôn tập các khái niệm chính."],
                },
            ],
        }

        result = extractor._ensure_deck_boundaries(deck, 3)

        self.assertEqual(result["slides"][0]["layout"], "intro")
        self.assertEqual(result["slides"][1]["pedagogical_role"], "learning_objectives")
        self.assertEqual(result["slides"][-1]["layout"], "thankyou")

    def test_boundary_replaces_generic_deck_title_with_subject_title(self):
        extractor = ContentExtractor()
        extractor._slide_lang_hint = "vi"
        deck = {
            "title": "Bài thuyết trình",
            "slides": [
                {
                    "title": "Mục tiêu học tập về Python",
                    "layout": "normal",
                    "pedagogical_role": "learning_objectives",
                    "bullets": ["Nhận biết các khái niệm."],
                },
                {
                    "title": "Bài thuyết trình",
                    "layout": "intro",
                    "bullets": ["Bài giảng tổng quan."],
                },
                {
                    "title": "Giới thiệu về Biến, Biểu thức và Câu lệnh trong Python",
                    "layout": "normal",
                    "bullets": ["Biến tham chiếu tới một giá trị."],
                },
                {
                    "title": "Tổng kết",
                    "layout": "normal",
                    "bullets": ["Ôn tập."],
                },
            ],
        }

        result = extractor._ensure_deck_boundaries(deck, 4)

        self.assertEqual(result["title"], "Biến, Biểu thức và Câu lệnh trong Python")
        self.assertEqual(result["slides"][0]["title"], result["title"])

    def test_boundary_replaces_off_topic_closing_with_deck_takeaways(self):
        extractor = ContentExtractor()
        extractor._slide_lang_hint = "vi"
        deck = {
            "title": "Hàm trong lập trình",
            "slides": [
                {"title": "Hàm trong lập trình", "layout": "intro", "bullets": ["Tổng quan."]},
                {
                    "title": "Định nghĩa hàm",
                    "layout": "normal",
                    "bullets": ["Hàm là một nhóm câu lệnh có tên để thực hiện một nhiệm vụ."],
                },
                {
                    "title": "Đối số và tham số",
                    "layout": "normal",
                    "bullets": ["Đối số được truyền vào tham số tương ứng khi gọi hàm."],
                },
                {
                    "title": "Tổng kết",
                    "layout": "thankyou",
                    "bullets": [
                        "Mô-đun chứa tập hợp các hàm.",
                        "Lệnh import tải một mô-đun.",
                    ],
                },
            ],
        }

        result = extractor._ensure_deck_boundaries(deck, 4)

        self.assertEqual(
            result["slides"][-1]["bullets"],
            [
                "Hàm là một nhóm câu lệnh có tên để thực hiện một nhiệm vụ.",
                "Đối số được truyền vào tham số tương ứng khi gọi hàm.",
            ],
        )

    def test_duplicate_table_is_kept_on_most_relevant_slide(self):
        table = {
            "title": "Top-down and Bottom-up comparison",
            "headers": ["Approach", "Mechanism", "Benefit"],
            "rows": [
                ["Top-down", "Memoization", "Computes required states"],
                ["Bottom-up", "Tabulation", "Avoids recursion overhead"],
            ],
        }
        slides = [
            {
                "title": "Dynamic programming overview",
                "bullets": ["Dynamic programming solves overlapping subproblems."],
            },
            {
                "title": "Top-down and Bottom-up",
                "bullets": ["Compare memoization with tabulation and recursion overhead."],
                "table": table,
            },
        ]

        resolved = _resolve_unique_visual_specs(slides, {0: table}, "table")

        self.assertNotIn(0, resolved)
        self.assertEqual(resolved[1], table)

    def test_comparison_table_accepts_supported_sentence_cells(self):
        spec = {
            "headers": ["Tiêu chí", "Ghi nhớ", "Lập bảng"],
            "rows": [
                ["Cách tiếp cận", "Bắt đầu từ bài toán lớn.", "Bắt đầu từ bài toán con."],
                ["Tính toán", "Chỉ tính trạng thái cần thiết.", "Tính tất cả trạng thái."],
                ["Bộ nhớ", "Dùng ngăn xếp đệ quy.", "Dùng bảng và vòng lặp."],
            ],
        }
        evidence = (
            "So sánh Ghi nhớ và Lập bảng. Tiêu chí gồm Cách tiếp cận, "
            "Tính toán và Bộ nhớ. Ghi nhớ bắt đầu từ bài toán lớn; "
            "Lập bảng bắt đầu từ bài toán con."
        )

        self.assertTrue(_table_spec_has_text_evidence(spec, evidence))

if __name__ == "__main__":
    unittest.main()
