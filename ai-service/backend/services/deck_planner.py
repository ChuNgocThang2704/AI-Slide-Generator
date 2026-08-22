from __future__ import annotations

import json
from typing import Any, Dict, List

from services.content.json_utils import parse_json_response


_INTRO_LAYOUTS = {"intro", "title"}
_CLOSING_LAYOUTS = {"thankyou", "thank_you", "closing"}
_OBJECTIVE_ROLES = {"learning_objectives", "objectives", "learning_outcomes"}
_EXAMPLE_ROLES = {
    "worked_example", "example", "demonstration", "demo", "practice", "exercise", "case_study"
}
_CHECK_ROLES = {"knowledge_check", "check", "quiz", "assessment", "practice", "exercise"}


def _clean_json(text: str) -> str:
    value = str(text or "").strip()
    if value.startswith("```"):
        value = value.split("\n", 1)[1] if "\n" in value else ""
    if value.endswith("```"):
        value = value[:-3]
    return value.strip()


def _valid_outline(
    plan: Any,
    target_slides: int,
    presentation_mode: str,
    *,
    require_lecture_roles: bool = True,
) -> bool:
    if not isinstance(plan, dict):
        return False
    outline = plan.get("outline")
    if not isinstance(outline, list) or len(outline) != target_slides:
        return False
    if not all(
        isinstance(item, dict)
        and str(item.get("title") or "").strip()
        and str(item.get("purpose") or "").strip()
        for item in outline
    ):
        return False
    first_layout = str(outline[0].get("layout_hint") or "").strip().lower()
    last_layout = str(outline[-1].get("layout_hint") or "").strip().lower()
    last_role = str(outline[-1].get("pedagogical_role") or "").strip().lower()
    if first_layout not in _INTRO_LAYOUTS:
        return False
    if last_layout not in _CLOSING_LAYOUTS and last_role != "summary":
        return False
    if require_lecture_roles and presentation_mode == "lecture" and target_slides >= 6:
        roles = {
            str(item.get("pedagogical_role") or "").strip().lower()
            for item in outline[1:-1]
        }
        if not roles.intersection(_OBJECTIVE_ROLES):
            return False
        if not roles.intersection(_EXAMPLE_ROLES):
            return False
        if not roles.intersection(_CHECK_ROLES):
            return False
    return True


def _valid_authored_deck(
    deck: Any,
    target_slides: int,
    *,
    enforce_density: bool = True,
) -> bool:
    if not isinstance(deck, dict):
        return False
    slides = deck.get("slides")
    if not isinstance(slides, list) or len(slides) != target_slides:
        return False
    if not all(
        isinstance(slide, dict)
        and str(slide.get("title") or "").strip()
        and isinstance(slide.get("bullets"), list)
        for slide in slides
    ):
        return False
    if not enforce_density:
        last_role = str(slides[-1].get("pedagogical_role") or "").strip().lower()
        return last_role == "summary"
    for index, slide in enumerate(slides):
        bullets = slide.get("bullets") or []
        role = str(slide.get("pedagogical_role") or "").strip().lower()
        if len(bullets) > 12:
            return False
        if index == 0 and len(bullets) > 4:
            return False
        if index == len(slides) - 1 and len(bullets) > 6:
            return False
        if role not in _EXAMPLE_ROLES | _CHECK_ROLES and len(bullets) > 8:
            return False
    last_role = str(slides[-1].get("pedagogical_role") or "").strip().lower()
    return last_role == "summary"


async def generate_outline_first_deck(
    content_extractor,
    *,
    source_text: str,
    user_instruction: str,
    target_slides: int,
    presentation_mode: str,
    language: str,
) -> Dict[str, Any]:
    """Plan once, lock the outline, then author content against that plan."""
    target_slides = max(2, int(target_slides))
    source = str(source_text or "")[:30000]
    planner_payload = {
        "source": source,
        "user_instruction": str(user_instruction or ""),
        "target_slides": target_slides,
        "presentation_mode": presentation_mode,
        "output_language": language,
    }
    planner_messages = [{
        "role": "system",
        "content": (
            "You are a senior presentation architect. Convert the complete user instruction into an atomic "
            "requirement_spec, then design an exact-count outline before any slide prose is written. Treat every "
            "named topic, example, comparison, error, correction, formula, data item, exercise, audience constraint, "
            "language, scope, and requested depth as mandatory. Ground the plan in source; do not invent facts. "
            "requirement_spec must contain the user's explicit requirements and requirements necessarily implied by "
            "the requested scope. Do not promote every optional source detail into a mandatory requirement. Put "
            "useful source enrichment in outline.required_components instead. "
            "The first outline item must use layout_hint=intro. The last must use layout_hint=thankyou and "
            "pedagogical_role=summary; it may synthesize, recommend a next step, or invite questions, but must not "
            "introduce a new lesson topic or exercise. In lecture mode with at least six slides, include a separate "
            "learning_objectives item after the introduction (never merge objectives into the cover), at least one "
            "worked_example/demonstration/practice item, and a knowledge_check "
            "or practice item after its prerequisite concepts. Allocate one "
            "In presentation mode, do not add a learning-objectives slide, knowledge check, practice, or worked "
            "example unless the user explicitly requests it. Allocate the available body slides to every named "
            "analysis topic, comparison, roadmap, metric, and recommendation before adding enrichment. Never merge "
            "two explicitly requested major sections merely to make room for an unrequested teaching device. "
            "clear purpose per slide and ensure every atomic requirement is assigned to at least one slide index. "
            "Return strict JSON only: {\"deck_title\":string,\"requirement_spec\":[{\"id\":string,"
            "\"description\":string,\"required_components\":[string],\"assigned_slide_indices\":[number],"
            "\"priority\":\"mandatory|supporting\"}],"
            "\"outline\":[{\"index\":number,\"title\":string,\"purpose\":string,"
            "\"required_components\":[string],\"pedagogical_role\":string,\"layout_hint\":string}]}."
        ),
    }, {"role": "user", "content": json.dumps(planner_payload, ensure_ascii=False)}]
    raw_plan = await content_extractor._llm_completion_plain_text(
        planner_messages,
        max_tokens=min(5200, 1800 + target_slides * 260),
        temperature=0.1,
        json_mode=True,
    )
    plan = parse_json_response(raw_plan, clean_result_text=_clean_json)
    if not _valid_outline(plan, target_slides, presentation_mode):
        repair_messages = [
            *planner_messages,
            {"role": "assistant", "content": str(raw_plan or "")},
            {
                "role": "user",
                "content": (
                    f"Your outline violated the output contract. Return corrected strict JSON with exactly "
                    f"{target_slides} outline items indexed 1 through {target_slides}. Preserve every atomic "
                    "requirement. The first item must have layout_hint=intro. The last must have "
                    "layout_hint=thankyou and pedagogical_role=summary. For a lecture of six or more slides, include "
                    "learning_objectives, an example/demonstration/practice, and a later knowledge_check/practice. "
                    "Return JSON only."
                ),
            },
        ]
        repaired_raw = await content_extractor._llm_completion_plain_text(
            repair_messages,
            max_tokens=min(5200, 1800 + target_slides * 260),
            temperature=0.0,
            json_mode=True,
        )
        plan = parse_json_response(repaired_raw, clean_result_text=_clean_json)
        if not _valid_outline(plan, target_slides, presentation_mode):
            if not _valid_outline(
                plan,
                target_slides,
                presentation_mode,
                require_lecture_roles=False,
            ):
                raise ValueError("outline planner did not satisfy the exact-count structure contract after repair")
            print(
                "[outline_first] repaired outline is structurally valid; "
                "semantic rubric will enforce missing lecture devices"
            )

    author_payload = {
        "source": source,
        "user_instruction": str(user_instruction or ""),
        "presentation_mode": presentation_mode,
        "output_language": language,
        "deck_title": plan.get("deck_title"),
        "requirement_spec": plan.get("requirement_spec") or [],
        "locked_outline": plan["outline"],
    }
    author_messages = [{
        "role": "system",
        "content": (
            "You are the slide author. Write the complete deck strictly against locked_outline; do not add, remove, "
            "merge, split, or reorder slides. Every slide must fulfill its purpose and required_components, and every "
            "requirement_spec item must be substantively covered in body content, not merely named in objectives or "
            "the conclusion. Use source as authority. Preserve output_language throughout. For technical examples, "
            "put each code/formula/input/output line in its own bullet and include the full requested mechanism and "
            "result. Common mistakes must include corrections. Knowledge checks must contain actual questions. "
            "Honor every explicit quantity literally (for example, three questions means exactly three distinct "
            "questions). Never emit Markdown language fences or standalone language labels such as 'python'. "
            "Never prefix bullet strings with '-', '*', bullet glyphs, or manual numbering such as '1.' because the "
            "renderer supplies list markers. If a title promises plural types, categories, methods, stages, causes, "
            "or examples, substantively present at least two distinct members; otherwise use a singular title. "
            "For a table slide, provide a structured table object with title, headers, and rows; do not duplicate "
            "the table as Markdown bullets. Before returning, verify every requirement_spec item against the body "
            "of its assigned slides and correct omissions without changing the locked outline. "
            "Keep visual density presentation-ready: cover 1-3 bullets, ordinary slides 3-6 bullets, closing 2-5 "
            "bullets, example/check slides 3-6 visible prompts, and code slides at most 10 concise lines. Never dump a long document "
            "or full program into one slide. Keep ordinary visible content near 500 characters and never exceed "
            "about 760 characters when an image is useful. Move supporting detail into speaker notes rather than "
            "shrinking the slide text. When a slide naturally contains categories, stages, criteria, or techniques, "
            "use 2-4 concise 'Short label: explanation' bullets to expose hierarchy. Do not force labels onto a "
            "simple narrative, and never emit a long flat list of equally weighted facts. "
            "The final authored slide must remain a summary/closing slide and must not become a new concept, example, "
            "or exercise. Speaker notes should add teaching or presentation value without repeating bullets. Return strict JSON: "
            "{\"title\":string,\"presentation_mode\":\"lecture|presentation\",\"learning_objectives\":[string],"
            "\"slides\":[{\"title\":string,\"bullets\":[string],\"notes\":string,"
            "\"layout\":string,\"pedagogical_role\":string,\"source_pages\":[number],"
            "\"table\":null|{\"title\":string,\"headers\":[string],\"rows\":[[string]]}}]}."
        ),
    }, {"role": "user", "content": json.dumps(author_payload, ensure_ascii=False)}]
    raw_deck = await content_extractor._llm_completion_plain_text(
        author_messages,
        max_tokens=min(10000, 2400 + target_slides * 700),
        temperature=0.18,
        json_mode=True,
    )
    deck = parse_json_response(raw_deck, clean_result_text=_clean_json)
    if not _valid_authored_deck(deck, target_slides):
        repair_author_messages = [
            *author_messages,
            {"role": "assistant", "content": str(raw_deck or "")},
            {
                "role": "user",
                "content": (
                    "Correct the authored deck without changing locked_outline count or order. Ensure every slide has "
                    "a title and bullets, fulfill every required component, and keep the final slide as a genuine "
                    "summary/closing slide with pedagogical_role=summary. Enforce presentation density: cover 1-3 "
                    "bullets, ordinary slides 3-6, closing 2-5, and example/check slides no more than 8 concise "
                    "lines. Keep image-oriented slides below roughly 760 visible characters. Group naturally related "
                    "facts with short semantic labels and move secondary detail to notes. Preserve complete meaning "
                    "while removing excess detail. Return strict JSON only."
                ),
            },
        ]
        repaired_deck_raw = await content_extractor._llm_completion_plain_text(
            repair_author_messages,
            max_tokens=min(10000, 2400 + target_slides * 700),
            temperature=0.0,
            json_mode=True,
        )
        deck = parse_json_response(repaired_deck_raw, clean_result_text=_clean_json)
        if not _valid_authored_deck(deck, target_slides):
            if not _valid_authored_deck(deck, target_slides, enforce_density=False):
                raise ValueError("outline author did not satisfy the locked deck contract after repair")
            print(
                "[outline_first] authored deck is structurally valid but dense; "
                "semantic rubric will refine it without discarding the outline"
            )
    slides = deck.get("slides") or []
    slides[0]["layout"] = "intro"
    slides[-1]["layout"] = "thankyou"
    deck["presentation_mode"] = presentation_mode
    deck["requirement_spec"] = plan.get("requirement_spec") or []
    deck["locked_outline"] = plan["outline"]
    deck["_outline_locked"] = True
    return deck
