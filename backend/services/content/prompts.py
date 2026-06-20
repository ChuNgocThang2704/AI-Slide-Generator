"""Prompt templates and guided-JSON schemas for content extraction.

Keep this file data-only.  The extraction pipeline imports these constants but
does not mutate them.
"""

from __future__ import annotations

from typing import Any, Dict


ONE_PASS_IMAGE_SCENE_SYSTEM = """You write a Stable Diffusion XL image prompt for a presentation slide.

Convert the slide into a REAL-WORLD PHOTOGRAPHABLE SCENE.

STEP 1 - THINK INTERNALLY (do not output):
- What is the single most concrete physical noun in this slide?
- If the slide is abstract, map it to one real-life domain and choose one tangible object from that domain.

STEP 2 - OUTPUT ONLY:
- One English scene description, 15-25 words.
- Comma-separated phrases only.

STRICT RULES:
1. MUST include people, objects, and environment.
2. MUST visually represent the main idea of the slide.
3. DO NOT use abstract words alone (system, architecture, process, performance, solution).
4. If abstract, convert into a concrete real-life situation.
5. Use concrete nouns (engineer, computer, device, office, machine, document, meeting room, etc.).
6. NEVER mention: text, diagram, chart, flowchart, infographic, whiteboard, UI, screenshot, slide, label, arrow.
7. Output must be ENGLISH only.
8. No explanation, no preamble, no bullet points."""


IMAGE_SEMANTIC_SYSTEM = """Extract image-generation semantics from a presentation slide.

Return ONLY valid JSON with this exact shape:
{
  "content_type": "historical|data|comparison|definition|process|normal",
  "domain": "business|education|technology|medical|general",
  "main_topic": "short topic",
  "action": "analysis|design|discussion|learning|planning|default",
  "objects": ["1-3 tangible visual objects"],
  "visual_objects": ["1-3 concrete physical items a camera could photograph"],
  "context": "business|education|technology|community|historical|default",
  "entities": ["0-3 named people, events, places, years, or concepts"],
  "visual_intent": "one short concrete visual direction",
  "stock_queries": ["2-4 English search queries optimized for Pexels and Wikimedia Commons, sorted from specific to generic"],
  "confidence": 0.0
}

Rules for visual_objects (CRITICAL):
- Each item MUST be a concrete, photographable physical object that a viewer could literally see in the photo.
- BAD examples (do NOT output): "balance scale", "harmony", "synergy", "equilibrium",
  "ecosystem imbalance", "global initiative", "cycle of life", "the earth" / "the globe"
  / "the world" (unless the slide is literally about planet Earth as a celestial body),
  "abstract concept", "flow", "responsibility", "growth", "balance".
- GOOD examples: "solar panel", "wind turbine", "policy document", "laptop showing data",
  "factory chimney", "river with debris", "students with notebooks".
- If the topic is abstract (sustainability, freedom, leadership, etc.), pick the most
  representative real-world artifact (e.g. for sustainability: "solar panel", not "balance").
- Output STRICTLY in English even if the slide is in another language.

Rules for stock_queries (CRITICAL):
- Generate 2-4 search queries for stock photo sites, in English.
- If the slide is about a specific historical event or person (especially in Vietnam/non-English regions), translate or paraphrase the event/person/concept to common English search terms (e.g. 'Dien Bien Phu battle' -> 'Vietnam war battle', 'Bác Hồ' -> 'Ho Chi Minh president', 'Chiến tranh Đông Dương' -> 'Indochina war'). Do NOT use obscure non-English terms alone.
- Make queries ordered from specific to generic. The last query must be a highly reliable, general domain/category term (e.g., 'business meeting', 'classroom', 'modern laptop', 'rural nature') guaranteed to return results on Pexels.

Other rules:
- Prefer concrete visual meaning over keywords.
- For history, put real event/person/place/year in entities when present.
- For data-heavy slides, use content_type "data".
- entities can keep the slide's original language (proper nouns).
- main_topic: short English phrase.
- No markdown, no explanation."""


CHART_SPEC_SYSTEM = """Extract an editable PowerPoint chart spec from a data-heavy slide.
The slide may contain explicit statistics, label-number pairs, percentages, year/month trends, survey results, KPI values, revenue/cost/profit figures, or category comparisons.

Return ONLY valid JSON. Use EITHER single-series (labels + values) OR multi-series (labels + series).

Single-series shape:
{
  "title": "short chart title",
  "chart_type": "bar|column|line|line_smooth|area|area_stacked|pie|doughnut|column_stacked|column_stacked_100|bar_horizontal|bar_stacked|bar_stacked_100|radar",
  "labels": ["2-12 category labels"],
  "values": [number, ...],
  "unit": "percent|number|currency",
  "is_percent": false
}

Multi-series shape (same categories, multiple lines/columns):
{
  "title": "short chart title",
  "chart_type": "column_stacked|bar_stacked|area_stacked|bar|line|bar_horizontal",
  "labels": ["Q1","Q2","Q3"],
  "series": [
    {"name": "Product A", "values": [1, 2, 3]},
    {"name": "Product B", "values": [4, 5, 6]}
  ],
  "unit": "percent|number|currency",
  "is_percent": false
}

Rules:
- Extract only real numeric values from the slide.
- Use chart data only when at least two comparable numeric points are present.
- Do not invent missing values. Ignore isolated counts that are just ordinary facts, such as "3 features" or "6 months", unless they form a comparable set.
- labels length must match each series values length (2-12 points).
- At most 5 series. pie and doughnut must use single series only.
- chart_type: time series / years -> line or line_smooth; parts of a whole -> pie or doughnut; compare categories -> bar or bar_horizontal; composition over categories -> column_stacked or bar_stacked; trend with stacked magnitude -> area_stacked.
- If values are percentages like 25%, set is_percent true and numeric values as 0.25 (or 25 with is_percent false and unit percent - prefer 0.25 + is_percent true).
- No markdown, no explanation."""


TABLE_SPEC_SYSTEM = """Extract a simple data table from slide bullets that look tabular or comparison-oriented.
The slide may be an explicit markdown/grid table, or it may describe repeated criteria, before/after states, pros/cons, option A/B, current/target, problem/solution, feature comparison, cost/risk/impact, or status by item.

Return ONLY valid JSON:
{
  "title": "optional short table caption",
  "headers": ["Column A", "Column B", "Column C"],
  "rows": [
    ["row1 col1", "row1 col2", "row1 col3"],
    ["row2 col1", "row2 col2", "row2 col3"]
  ]
}

Rules:
- 2-8 columns, 1-12 data rows (excluding header). Trim long text in cells.
- Prefer a table only when the slide has repeated structure across rows or columns.
- Good generic headers include Criteria, Current, Target, Problem, Solution, Option, Benefit, Risk, Impact, Status, or Metric when they fit the slide.
- headers must be non-empty strings.
- Each row must have the same number of cells as headers (pad with "" if needed).
- If the slide is not tabular, return {"headers":[],"rows":[]} (empty).
- No markdown, no explanation outside JSON."""


MAX_BULLETS_PER_SLIDE = 5
MAX_WORDS_PER_BULLET = 26


SLIDE_DECK_JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "slides": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "bullets": {"type": "array", "items": {"type": "string"}},
                    "notes": {"type": "string"},
                },
                "required": ["title", "bullets", "notes"],
            },
        },
    },
    "required": ["title", "slides"],
}

EXPANDED_TEXT_JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "expanded_text": {"type": "string"},
    },
    "required": ["expanded_text"],
}

SECTIONS_JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["title", "content"],
            },
        },
    },
    "required": ["sections"],
}

BULLET_JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "bullet": {"type": "string"},
    },
    "required": ["bullet"],
}

BULLETS_JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "bullets": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["bullets"],
}

ANTI_TRUNCATION_TOKEN_RULE = (
    "CRITICAL TOKEN BUDGET: If running out of space, end the current bullet with a period, "
    "then close valid JSON. Never paste long source fragments that get cut off - rewrite each bullet "
    "as a short complete thought in your own words.\n"
)
