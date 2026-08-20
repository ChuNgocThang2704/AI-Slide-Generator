from services.technical_quality import validate_technical_content
from services.text_utils import plain_slide_block


def test_removes_sentence_period_from_python_code():
    deck = {"slides": [{"bullets": ["Ví dụ: height = math.sin(degrees / 180 * math.pi) ."]}]}
    cleaned, issues = validate_technical_content(deck)
    assert cleaned["slides"][0]["bullets"] == ["height = math.sin(degrees / 180 * math.pi)"]
    assert issues == []


def test_reports_incomplete_function_definition():
    deck = {"slides": [{"bullets": ["Cú pháp: def my_function(param1, param2):"]}]}
    _cleaned, issues = validate_technical_content(deck)
    assert len(issues) == 1
    assert issues[0]["type"] == "factual_accuracy"
    assert "syntactically complete" in issues[0]["instruction"]


def test_does_not_modify_normal_prose_or_math_sentence():
    bullet = "Giá trị trung bình bằng 3.5."
    deck = {"slides": [{"bullets": [bullet]}]}
    cleaned, issues = validate_technical_content(deck)
    assert cleaned["slides"][0]["bullets"] == [bullet]
    assert issues == []


def test_removes_trailing_language_marker_from_prose_label():
    deck = {"slides": [{"bullets": ["Function definition: python", "def add(a, b): return a + b"]}]}
    cleaned, issues = validate_technical_content(deck)
    assert cleaned["slides"][0]["bullets"][0] == "Function definition"
    assert issues == []


def test_removes_manual_markers_that_would_duplicate_renderer_bullets():
    deck = {"slides": [{"bullets": ["1. Positional arguments", "- Keyword arguments", "* Defaults"]}]}
    cleaned, issues = validate_technical_content(deck)
    assert cleaned["slides"][0]["bullets"] == [
        "Positional arguments",
        "Keyword arguments",
        "Defaults",
    ]
    assert issues == []


def test_removes_markdown_table_duplicate_when_structured_table_exists():
    deck = {
        "slides": [{
            "bullets": [
                "Feature Parameter Argument",
                ":-------- :-------- :--------",
                "**Location** Function definition Function call",
                "Use this comparison to avoid confusing the two terms.",
            ],
            "table": {
                "headers": ["Feature", "Parameter", "Argument"],
                "rows": [["Location", "Function definition", "Function call"]],
            },
        }]
    }
    cleaned, issues = validate_technical_content(deck)
    assert cleaned["slides"][0]["bullets"] == [
        "Use this comparison to avoid confusing the two terms."
    ]
    assert issues == []


def test_reconstructs_and_validates_multiline_function_block():
    deck = {"slides": [{"bullets": [
        "def add(a, b):",
        "return a + b",
        "result = add(2, 3)",
    ]}]}
    cleaned, issues = validate_technical_content(deck)
    assert issues == []
    assert cleaned["slides"][0]["bullets"] == [
        "def add(a, b):\n    return a + b\n    result = add(2, 3)"
    ]
    compile(cleaned["slides"][0]["bullets"][0], "<slide>", "exec")


def test_reports_function_header_left_without_a_body_at_end_of_example():
    deck = {"slides": [{"bullets": [
        "def print_lyrics():",
        "print('Hello')",
        "def repeat_lyrics():",
    ]}]}
    _cleaned, issues = validate_technical_content(deck)
    assert len(issues) == 1
    assert "indented block" in issues[0]["instruction"]


def test_reports_return_example_without_return_statement():
    deck = {"slides": [{
        "title": "Hàm trả về giá trị",
        "bullets": ["def area(radius):", "value = 3.14 * radius ** 2"],
    }]}
    _cleaned, issues = validate_technical_content(deck)
    assert any("no return statement" in issue["instruction"] for issue in issues)


def test_converts_flattened_single_column_code_table_to_code_block():
    deck = {"slides": [{
        "title": "Complete example",
        "layout": "text_table",
        "bullets": ["A complete reusable example."],
        "table": {
            "headers": ["Python code"],
            "rows": [
                ["def greet():"],
                ["    print('Hello')"],
                [""],
                ["greet()"],
            ],
        },
    }]}
    cleaned, issues = validate_technical_content(deck)
    slide = cleaned["slides"][0]
    assert "table" not in slide
    assert slide["layout"] == "text_only"
    assert issues == []
    code = next(value for value in slide["bullets"] if value.startswith("def greet"))
    assert code == "def greet():\n    print('Hello')\n\ngreet()"
    compile(code, "<slide>", "exec")


def test_rejects_flattened_error_correction_code_table():
    deck = {"slides": [{
        "title": "Common error and correction",
        "bullets": ["Calling a function before it is defined causes NameError."],
        "table": {
            "headers": ["Error code", "Corrected code"],
            "rows": [
                ["greet()", "def greet():"],
                ["def greet():", "    print('Hello')"],
                ["    print('Hello')", ""],
                ["", "greet()"],
            ],
        },
    }]}
    cleaned, issues = validate_technical_content(deck)
    assert "table" not in cleaned["slides"][0]
    assert any("flattened into table rows" in issue["instruction"] for issue in issues)


def test_api_text_cleanup_preserves_code_newlines_and_indentation():
    code = "def greet():\n    print('Hello')\n\ngreet()"
    assert plain_slide_block(code) == code


def test_converts_code_column_even_when_description_column_is_prose():
    deck = {"slides": [{
        "title": "Complete example",
        "bullets": ["Explanation"],
        "table": {
            "headers": ["Python code", "Description"],
            "rows": [
                ["def greet():", "Define the function"],
                ["    print('Hello')", "Function body"],
                ["greet()", "Call the function"],
            ],
        },
    }]}
    cleaned, issues = validate_technical_content(deck)
    assert "table" not in cleaned["slides"][0]
    assert issues == []


def test_error_and_fix_slide_requires_two_code_examples():
    deck = {"slides": [{
        "title": "Lỗi thường gặp và cách sửa",
        "bullets": [
            "Ví dụ lỗi:",
            "greet()\ndef greet():\n    print('Hello')",
            "Cách sửa: đặt lời gọi sau định nghĩa.",
        ],
    }]}
    _cleaned, issues = validate_technical_content(deck)
    assert any("two distinct complete code examples" in issue["instruction"] for issue in issues)


def test_reports_direct_recursion_without_a_termination_guard():
    deck = {"slides": [{"bullets": [
        "def repeat_message():\n    print('hello')\n    repeat_message()"
    ]}]}
    _cleaned, issues = validate_technical_content(deck)
    assert any("recursion has no visible termination" in issue["instruction"] for issue in issues)


def test_allows_guarded_direct_recursion():
    deck = {"slides": [{"bullets": [
        "def countdown(n):\n    if n <= 0:\n        return\n    countdown(n - 1)"
    ]}]}
    _cleaned, issues = validate_technical_content(deck)
    assert not any("recursion has no visible termination" in issue["instruction"] for issue in issues)
