from __future__ import annotations

import ast
import copy
import json
import re
from typing import Any, Dict, List, Tuple


_CODE_PREFIX = re.compile(
    r"^\s*(?:(?:ví\s+dụ(?:\s+mã)?|cú\s+pháp|mã(?:\s+python)?|code|syntax|example)\s*:\s*)",
    re.IGNORECASE,
)
_PYTHON_START = re.compile(
    r"^\s*(?:>>>|\.\.\.|@\w+|async\s+def\s+|def\s+|class\s+|return\b|yield\b|raise\b|"
    r"import\s+|from\s+\S+\s+import\s+|print\s*\(|if\s+.+:|elif\s+.+:|else\s*:|"
    r"for\s+.+:|while\s+.+:|try\s*:|except\b.*:|finally\s*:|with\s+.+:|"
    r"assert\b|pass\b|break\b|continue\b|[A-Za-z_]\w*\s*=|[A-Za-z_]\w*\s*\()"
)
_BLOCK_HEADER = re.compile(
    r"^(?:async\s+def|def|class|if|elif|else|for|while|try|except|finally|with)\b.*:\s*$"
)
_TOP_LEVEL_HEADER = re.compile(r"^(?:async\s+def|def|class)\b")
_DEDENT_HEADER = re.compile(r"^(?:elif|else|except|finally)\b")
_TRAILING_LANGUAGE_MARKER = re.compile(
    r"\s*:\s*(?:python|javascript|java|c\+\+|c#|sql|bash|shell)\s*$", re.IGNORECASE
)
_TABLE_SEPARATOR = re.compile(r"^\s*:?-{3,}:?(?:\s+:?-{3,}:?)+\s*$")
_LEADING_LIST_MARKER = re.compile(r"^\s*(?:[-*\u2022]+|\d{1,3}[.)])\s+")
_RETURN_TOPIC = re.compile(r"\b(?:return|returns?|trả\s+về|giá\s+trị\s+trả\s+về)\b", re.IGNORECASE)
_CODE_TABLE_HEADER = re.compile(
    r"\b(?:code|mã(?:\s+python|\s+nguồn|\s+lỗi|\s+sửa)?|syntax|cú\s+pháp)\b", re.IGNORECASE
)
_ERROR_FIX_TOPIC = re.compile(
    r"(?:\b(?:error|mistake|bug)\b.*\b(?:fix|correct|solution)\b|"
    r"\b(?:lỗi|sai)\b.*\b(?:sửa|đúng|khắc\s+phục)\b)", re.IGNORECASE
)


def _clean_value(value: Any) -> str:
    text = str(value or "").strip().strip("`")
    text = _LEADING_LIST_MARKER.sub("", text).strip()
    return _TRAILING_LANGUAGE_MARKER.sub("", text).strip()


def _code_text(value: Any) -> Tuple[str, bool]:
    text = _clean_value(value)
    candidate = _CODE_PREFIX.sub("", text).strip()
    first_line = candidate.splitlines()[0].strip() if candidate else ""
    return candidate, bool(_PYTHON_START.match(first_line))


def _reconstruct_python_block(values: List[str]) -> str:
    """Rebuild indentation lost when an LLM returns code as bullet strings."""
    raw_lines: List[str] = []
    for value in values:
        code, _ = _code_text(value)
        raw_lines.extend(line.rstrip() for line in code.splitlines())

    preserved = "\n".join(raw_lines).strip()
    if preserved:
        try:
            ast.parse(preserved)
            return preserved
        except SyntaxError:
            pass

    result: List[str] = []
    indent = 0
    previous_was_header = False
    for raw in raw_lines:
        if not raw.strip():
            indent = 0
            previous_was_header = False
            if result and result[-1] != "":
                result.append("")
            continue
        line = re.sub(r"^\s*(?:>>>|\.\.\.)\s?", "", raw).strip()
        line = re.sub(r"\s+\.\s*$", "", line).rstrip()
        if not line:
            continue
        if _TOP_LEVEL_HEADER.match(line) and result and not previous_was_header:
            indent = 0
        if _DEDENT_HEADER.match(line):
            indent = max(0, indent - 1)
        result.append(f"{'    ' * indent}{line}")
        previous_was_header = bool(_BLOCK_HEADER.match(line))
        if previous_was_header:
            indent += 1
    return "\n".join(result)


def _technical_issue(index: int, message: str, snippet: str) -> Dict[str, Any]:
    return {
        "index": index,
        "type": "factual_accuracy",
        "severity": "high",
        "instruction": (
            "Repair the syntactically complete Python example using source evidence. Keep it as one multiline code block "
            "with correct indentation, complete compound-statement bodies, and executable syntax. "
            f"{message}. Current snippet: {snippet[:500]}"
        ),
    }


def _unbounded_direct_recursion(block: str) -> List[str]:
    """Return functions that call themselves without any visible guard/branch."""
    try:
        tree = ast.parse(block)
    except SyntaxError:
        return []
    unsafe: List[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        self_calls = [
            statement.value
            for statement in node.body
            if isinstance(statement, ast.Expr)
            and isinstance(statement.value, ast.Call)
            and isinstance(statement.value.func, ast.Name)
            and statement.value.func.id == node.name
        ]
        has_guard = any(isinstance(child, (ast.If, ast.Try, ast.For, ast.While)) for child in ast.walk(node))
        if self_calls and not has_guard:
            unsafe.append(node.name)
    return unsafe


def _code_table_columns(table: Any) -> List[List[str]]:
    if not isinstance(table, dict):
        return []
    headers = [str(value or "").strip() for value in (table.get("headers") or [])]
    rows = [row for row in (table.get("rows") or []) if isinstance(row, list)]
    if not headers or not rows or not any(_CODE_TABLE_HEADER.search(header) for header in headers):
        return []
    columns: List[List[str]] = [[] for _ in headers]
    code_counts = [0 for _ in headers]
    populated_counts = [0 for _ in headers]
    for row in rows:
        if not any(str(value or "").strip() for value in row):
            for column in columns:
                column.append("")
            continue
        for column_index in range(len(headers)):
            value = str(row[column_index] if column_index < len(row) else "").rstrip()
            if not value.strip():
                continue
            populated_counts[column_index] += 1
            _code, is_code = _code_text(value)
            if is_code or re.match(r"^\s*(?:Kết quả|Result|Error|Lỗi)\s*:", value, re.IGNORECASE):
                code_counts[column_index] += 1
            columns[column_index].append(value)
    # A real comparison table may mention code in one or two cells. A flattened
    # code block has code-like content across most rows and must not be rendered
    # as a spreadsheet.
    code_column_indices = [
        index
        for index, header in enumerate(headers)
        if _CODE_TABLE_HEADER.search(header)
        and populated_counts[index] >= 2
        and code_counts[index] / populated_counts[index] >= 0.6
    ]
    if not code_column_indices:
        return []
    return [columns[index] for index in code_column_indices if columns[index]]


def slide_has_code_content(slide: Any) -> bool:
    if not isinstance(slide, dict):
        return False
    if _code_table_columns(slide.get("table")):
        return True
    return any(_code_text(value)[1] for value in (slide.get("bullets") or []))


def validate_technical_content(structured: Dict[str, Any]) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Normalize complete code blocks and report technical defects before rendering."""
    if not isinstance(structured, dict):
        return structured, []
    deck = copy.deepcopy(structured)
    deck["title"] = re.sub(r"^\s*#{1,6}\s*(?:\d+[.)]\s*)?", "", str(deck.get("title") or "").strip()).strip()
    issues: List[Dict[str, Any]] = []
    for index, slide in enumerate(deck.get("slides") or []):
        if not isinstance(slide, dict):
            continue
        slide["title"] = re.sub(r"^\s*#{1,6}\s*(?:\d+[.)]\s*)?", "", str(slide.get("title") or "").strip()).strip()
        bullets = slide.get("bullets") or []
        if not isinstance(bullets, list):
            continue

        code_table_columns = _code_table_columns(slide.get("table"))
        flattened_code_table = bool(code_table_columns)
        if flattened_code_table:
            for column in code_table_columns:
                bullets.append("\n".join(column))
            slide.pop("table", None)
            if "table" in str(slide.get("layout") or "").lower():
                slide["layout"] = "text_only"

        cleaned: List[str] = []
        code_run: List[str] = []
        code_blocks: List[str] = []

        def flush_code() -> None:
            if not code_run:
                return
            block = _reconstruct_python_block(code_run)
            code_run.clear()
            if not block:
                return
            code_blocks.append(block)
            try:
                ast.parse(block)
            except SyntaxError as error:
                issues.append(_technical_issue(index, f"Parser error: {error.msg}", block))
            else:
                recursive = _unbounded_direct_recursion(block)
                if recursive:
                    issues.append(_technical_issue(
                        index,
                        "Direct recursion has no visible termination condition in function(s): " + ", ".join(recursive),
                        block,
                    ))
            cleaned.append(block)

        for raw in bullets:
            original = _clean_value(raw)
            if not original or _TABLE_SEPARATOR.match(original):
                continue
            code, is_code = _code_text(original)
            if is_code:
                code_run.append(code)
            else:
                flush_code()
                cleaned.append(original)
        flush_code()

        if flattened_code_table and len(code_table_columns) > 1:
            issues.append(_technical_issue(
                index,
                "The error/correction example was flattened into table rows; rebuild it as two complete, ordered code examples",
                "\n\n".join("\n".join(column) for column in code_table_columns),
            ))

        topic = " ".join([str(slide.get("title") or ""), *[str(value) for value in cleaned]])
        if code_blocks and _RETURN_TOPIC.search(topic) and not any(re.search(r"\breturn\b", block) for block in code_blocks):
            issues.append(_technical_issue(index, "The slide promises a return-value example but the code has no return statement", "\n".join(code_blocks)))
        if code_blocks and _ERROR_FIX_TOPIC.search(topic) and len(code_blocks) < 2:
            issues.append(_technical_issue(
                index,
                "The slide promises an error and its correction but does not contain two distinct complete code examples",
                "\n\n".join(code_blocks),
            ))

        table = slide.get("table")
        if isinstance(table, dict) and table.get("headers") and table.get("rows"):
            table_tokens = {
                str(value or "").strip().strip("*`").casefold()
                for value in [
                    *(table.get("headers") or []),
                    *(cell for row in (table.get("rows") or []) if isinstance(row, list) for cell in row),
                ]
                if str(value or "").strip()
            }
            deduplicated: List[str] = []
            for bullet in cleaned:
                normalized = str(bullet or "").strip().strip("*`").casefold()
                markdown_row = normalized.startswith("|") or normalized.count("  ") >= 2
                overlap = sum(token in normalized for token in table_tokens if len(token) >= 4)
                if markdown_row or overlap >= 2:
                    continue
                deduplicated.append(bullet)
            cleaned = deduplicated
        slide["bullets"] = cleaned
    return deck, issues


async def repair_technical_content(
    content_extractor,
    structured: Dict[str, Any],
    *,
    source_text: str = "",
    max_passes: int = 2,
) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Run a bounded, syntax-verified repair only on technically invalid slides."""
    current, issues = validate_technical_content(structured)
    if not issues or not hasattr(content_extractor, "_llm_completion_plain_text"):
        return current, issues

    from services.content.json_utils import parse_json_response

    for _ in range(max(1, min(2, max_passes))):
        by_index = {int(issue["index"]): issue for issue in issues}
        payload = {
            "source_evidence": (source_text or "")[:24000],
            "invalid_slides": [
                {
                    "index": index,
                    "title": str(current["slides"][index].get("title") or ""),
                    "bullets": current["slides"][index].get("bullets") or [],
                    "problem": issue["instruction"],
                }
                for index, issue in by_index.items()
                if 0 <= index < len(current.get("slides") or [])
            ],
        }
        messages = [{
            "role": "system",
            "content": (
                "Repair only the supplied technically invalid slides. Use source evidence as authority. "
                "Every Python example must be complete, executable, and pedagogically relevant. Put each complete "
                "code example in one bullet string with newline characters and four-space indentation. Never leave "
                "a def/class/if/for/while header without a body. If the slide teaches return values, include a real "
                "return statement and a matching call. Preserve language, title, slide purpose, and factual scope. "
                "Return strict JSON only: {\"slides\":[{\"index\":0,\"bullets\":[\"prose\",\"code\"]}]}"
            ),
        }, {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}]
        try:
            raw = await content_extractor._llm_completion_plain_text(
                messages, max_tokens=2200, temperature=0.0, json_mode=True
            )
            parsed = parse_json_response(raw, clean_result_text=lambda value: str(value).strip())
        except Exception as error:
            print(f"[technical_quality] repair failed: {error}")
            break
        changed = False
        for item in (parsed.get("slides") if isinstance(parsed, dict) else []) or []:
            if not isinstance(item, dict):
                continue
            try:
                index = int(item.get("index"))
            except (TypeError, ValueError):
                continue
            bullets = [str(value).strip() for value in (item.get("bullets") or []) if str(value).strip()]
            if index not in by_index or not bullets:
                continue
            current["slides"][index]["bullets"] = bullets
            changed = True
        current, issues = validate_technical_content(current)
        if not issues or not changed:
            break
    return current, issues
