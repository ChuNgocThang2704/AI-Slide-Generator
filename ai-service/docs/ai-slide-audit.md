# AI slide generation — Phase A audit

Date: 2026-09-15  
Scope: `ai-service` slide generation only. Video generation is excluded.  
Method: static call-graph/config/rule inspection of the current working tree. No production behavior was changed.

## Executive summary

The service is already beyond a simple one-shot generator. It has a provider fallback, presentation-mode classification, heading-aware chunking, an outline-first short-input path, structured normalization, several targeted quality routines, source retrieval with optional embeddings, stable slide IDs, a structure lock, and guarded visual processing.

The largest architectural issue is not missing capability but **two materially different generation paths**:

- Short input uses `generate_outline_first_deck()`: plan exact outline, author against it, mark `_outline_locked`.
- Long input summarizes chunks and then calls the older `expand -> group -> section generation -> post-process` pipeline.

Consequently, long documents—the inputs that most need hierarchical planning and grounding—do not use the strongest planning contract. The legacy finalization path also performs overlapping semantic passes and repeatedly re-applies lecture enrichment, provenance, slide-count repair, and boundary normalization.

Recommended next change: do not reorganize folders yet. First add instrumentation and benchmark fixtures, then introduce a `ContentPlan` adapter that both short and long paths can consume. Preserve the current outline-first path as the characterization reference.

## Scope and baseline

Inspected entry points and modules:

- `backend/routes/api.py`, `backend/services/redis_queue.py`
- `backend/config.py`
- all modules under `backend/services/content/`
- `deck_planner.py`, `deck_contract.py`, `deck_coherence.py`
- `slide_quality.py`, `slide_text_quality.py`, `technical_quality.py`
- `lecture_quality.py`, `presentation_mode.py`, `revision_rules.py`, `plan_limits.py`
- `file_processor.py`, `source_retrieval.py`, source/chart/table/visual services
- `backend/services/images/*`
- the existing test suite

Repository detail: several files named in the requested audit live directly under `backend/services/`, not `backend/services/content/`.

The repository contains 18 focused `test_*.py` modules (plus script-level tests), covering deck planning/contracts/coherence, presentation mode, revisions, retrieval, images and quality. The project virtualenv baseline passes: **182 passed, 1 skipped** before Phase A.1 changes. Running system Python failed because it lacked pytest; running from the repository also required `PYTHONPATH=backend`. Phase A.1 adds `pytest.ini`, making the virtualenv command reproducible without manual path configuration.

## Real top-level call graph

```text
HTTP upload-text/upload-file
  -> Redis task storage / optional worker offload
  -> generate-slide-spec (inline background task) OR RedisQueue worker
     -> ContentExtractor.extract_and_structure
        -> classify_presentation_mode
        -> strip meta instructions / detect explicit slide blocks
        -> detect prompt mode vs document mode
        -> [document + user scope] focus_document_scope
        -> [prompt mode] generate_content_from_prompt
        -> [no provider] deterministic fallback_structure
        -> [long input] chunking path
        |  -> split_by_headings / paragraph blocks
        |  -> summarize chunks concurrently with retry/fallback
        |  -> merge summaries + estimate slide count
        |  -> LEGACY expand_group_generate_refine_pipeline
        -> [short input] optional summary, normally skipped
           -> generate_outline_first_deck
              -> plan exact outline + requirement_spec
              -> optional plan repair
              -> author exact deck against locked outline
              -> optional author repair
              -> _outline_locked
           -> [on failure] LEGACY expand_group_generate_refine_pipeline

     -> [legacy only] improve_slide_text_quality
     -> [legacy only] improve_deck_source_grounding
     -> finalize_deck_for_visuals
        -> locked-outline finalizer OR legacy finalizer
        -> provenance / technical validation and repair
        -> stable IDs + STRUCTURE LOCK
     -> build_visual_plan
     -> build table specs
     -> build chart specs
     -> optional image selection/generation/validation
     -> assert structure signature after visual stages
     -> structured slide-spec response and/or PPTX renderer
```

There are two orchestration implementations with substantially duplicated behavior: the inline background function in `routes/api.py` and the Redis worker methods in `redis_queue.py`. Both call the same core services, but duplication makes behavioral drift likely.

## Stage inventory

| Stage | Primary responsibility | Main input/output | LLM use | Deterministic behavior and risks |
|---|---|---|---|---|
| File processing | Extract DOCX/PDF/TXT and retain page markers | file -> source text | No | Two PDF extractors and extraction-quality fallback are useful. Text cleaning may alter structure before grounding. |
| Input processing | Strip meta instructions, parse explicit slide blocks, detect headings, split oversized sections | source text -> normalized text/chunks/deck | No | Good structural guardrails. Fallback builder limits output and semantically derives titles/bullets. |
| Mode classification | Decide lecture vs presentation | source + instruction -> structured decision | Conditional | Explicit intent is considered, then heuristic/LLM fallback. Source keyword windows can still influence mode unexpectedly. |
| Prompt expansion | Turn a short topic into source-like content | prompt -> expanded document | 1 | Appropriate for prompt mode, but the expanded text later resembles a document while `_is_document_mode` remains false. Provenance semantics therefore need an explicit generation mode, not a boolean inferred from length. |
| Document focusing | Select document scope from instruction | source -> focused source | Up to 1 | Can reduce cost, but selection and a 30k cap can remove evidence outside the chosen excerpt. |
| Chunking/map | Heading/paragraph chunks and summaries | long document -> summaries | N calls, retries possible | Preserves late sections better than global truncation. Summaries are lossy and currently become the only content supplied to legacy planning. |
| Planning | Exact requirement spec and outline | source excerpt -> locked outline | 1 + optional repair | Strong contract for short input. Source is hard-capped at 30k characters and long-document flow does not use it. It does not yet expose importance/complexity/source refs as a first-class `ContentPlan`. |
| Authoring | Write slide prose against outline | outline + source -> deck | 1 + optional repair | Exact count/order is strong. Prompt contains grounding/density/notes requirements. Large source and output make failure/latency expensive. |
| Legacy expand/group/generate | Expand, group and generate sections concurrently | merged summary -> deck | 2 fixed calls + one call per section | Useful bounded section concurrency, but semantic work overlaps: expand, group, generation and later global refinement. Document mode skips one expansion in some paths, but long chunk results still enter this pipeline. |
| Normalization | Sanitize schema/text, fill defaults, balance content, force counts | candidate deck -> normalized deck | Optional repair in force-count | Necessary validation is mixed with semantic title derivation, bullet acceptance and deck balancing. `_balance_deck` can move/merge semantic content. |
| Text quality | Score title/bullets/notes and repair subsets | deck -> repaired deck | Multiple conditional/batched calls | Some targeted behavior exists, but title, bullet, notes and final quality responsibilities overlap with pipeline refinement and coherence. |
| Source grounding | Global deck rewrite against source excerpt | deck + source -> deck | 1 plus title/notes calls | High-value intent, but it sends/replaces the entire deck and uses only the first/focused 12k characters. It is skipped on the outline-locked path. |
| Coherence | Judge issues and repair selected slides | deck -> issues -> repaired deck | Judge/audit + targeted repair | Closest existing implementation to structured validation/targeted repair. Its issue schema should become the common validator contract. Source evidence is capped. |
| Lecture enrichment | Add/restore objectives, roles, checks and provenance | deck + source -> deck | Mainly deterministic; repair can use LLM | Late deterministic enrichment can add/rewrite structure. It is invoked more than once in legacy finalization to recover changes made by other passes. |
| Final contract | Count/boundaries/provenance/technical repair/stable IDs | deck -> locked deck | Several conditional calls | Structure signature is a strong invariant. Legacy branch has repeated enrichment/provenance/count cycles. |
| Visual planning | Choose image/chart/table/none and composition | locked deck + context -> plan | 1 | Correctly occurs after lock. It uses controlled visual types, although layout/design profile is not yet a dedicated contract. |
| Tables/charts | Extract or infer structured data specs | locked deck/source -> specs | Conditional | Deterministic evidence validation is valuable. Heuristic inference and LLM review are spread across large modules. |
| Images | Semantic extraction, source/stock/generated routing, prompt building, quality validation | slide + source -> image | Per-slide conditional calls plus providers | Rich safety/factual routing. High complexity and cost, but it asserts deck structure and does not reorder slides. |
| Rendering | Produce slide-spec/PPTX | locked deck + visual artifacts -> output | No | Geometry remains renderer-controlled; this is the right boundary for future design intelligence. |

## Prompt mode versus document mode

Current behavior explicitly sets `_is_document_mode = not _is_prompt_input(raw_content)`. Document mode skips prompt expansion and may call `_focus_document_scope`; prompt mode calls `_generate_content_from_prompt` and allows knowledge expansion.

Positive findings:

- The outline author tells the model that source is authoritative and forbids invented facts.
- The legacy expand prompt has mode-aware behavior.
- Source retrieval/provenance exists and exact numbers/technical details receive dedicated checks.

Risks:

1. Mode is inferred from input shape/length rather than passed as a durable request contract.
2. Prompt-generated content is stored in the same source-shaped variable as uploaded evidence.
3. `improve_deck_source_grounding()` says both “remove unsupported claims” and, for mandatory unsupported topics, allow stable foundational explanation. That is sensible for prompt mode but ambiguous for strict document mode.
4. Several validators see excerpts rather than a retrieval result tied to every claim.
5. Outline-first currently receives `source_text[:30000]`; source grounding uses a focused/leading 12k excerpt. Facts near the end can therefore disappear from global decisions.

Recommended contract for Phase C: `GenerationContext(mode='prompt'|'document', source_is_authoritative, user_instruction, source_index, output_language)`. Do not rely on `_is_document_mode` as mutable extractor state.

## LLM call map

All ordinary text completions eventually pass through `LLMClientMixin._llm_completion_plain_text()`, which uses vLLM/Qwen first when healthy and falls back to Gemini. `_request_json_dict()` adds JSON schema/guided-output behavior and may retry/route provider-specific requests.

Approximate call shapes (conditional repairs are not included in the minimum):

| Flow | Minimum content calls before visuals | Possible additions |
|---|---:|---|
| Explicit slide blocks | 0 | final contract, notes, technical repair, visual planning |
| Short prompt, outline-first | classifier 0–1 + prompt expansion 1 + planner 1 + author 1 | plan repair, author repair, coherence/coverage repair, notes, technical repair |
| Short document, outline-first | classifier 0–1 + planner 1 + author 1 | same conditional repairs |
| Long document, legacy | classifier 0–1 + N chunk summaries + expand/group + S section-generation calls | summary retries, unified/fallback refinement, title repair, text quality, global grounding, coherence, notes, technical repair |
| Revision | revision plan/selected-slide calls | title, notes, coherence, technical and visual regeneration calls |

`N` is chunk count and `S` is generated section count. The long-document worst case is materially more expensive than the short path and can repeat whole-deck payloads. There is no single per-task call ledger, so current latency/call counts cannot be measured reliably from output alone.

## Provider layer

Strengths:

- vLLM is correctly treated as an OpenAI-compatible serving endpoint, not as a model.
- Provider health/circuit breaker exists.
- Gemini API-key and Vertex paths are supported.
- JSON-mode behavior is centralized more than most generation logic.

Debt:

- Content services still call private extractor methods (`_llm_completion_plain_text`, `_request_json_dict`) directly, making `ContentExtractor` a service locator.
- Provider capability and content policy arguments are mixed at call sites.
- Provider fallback changes can be difficult to characterize because call purpose is not tagged (planner, author, validator, image semantic, etc.).

Phase B should introduce a thin typed `LLMGateway.complete(request)` interface and call-purpose telemetry, while keeping the same fallback implementation.

## Configuration audit

`config.py` currently mixes at least five categories:

- Runtime/deployment: Redis, paths, API host/port.
- LLM provider: model, URLs, credentials, timeouts, guided JSON.
- Generation policy: chunk thresholds, context limits, fast/final-compose switches.
- Quality policy: refine passes, polish, density and final-quality gates.
- Visual/image policy: providers, limits, style, CLIP/VLM thresholds, dimensions.
- Commercial plan limits: slide/image/character limits.

The configuration is usable but difficult to reason about because many flags describe legacy branches that the outline-first path bypasses. Before removing any flag, add a caller table and log the chosen pipeline path. Suggested future immutable groups: `RuntimeConfig`, `LLMConfig`, `GenerationPolicy`, `QualityPolicy`, `ImageConfig`, `DesignConfig`, with plan limits kept separate as product policy.

## Deterministic-rule inventory

Retain as guardrails:

- JSON/schema parsing and guided output.
- Enum/layout validation and sanitation.
- explicit revision target parsing (`slide 3`, last slide, explicit counts/visual types).
- plan limits and exact requested count validation.
- stable IDs and structure signatures.
- cancellation, timeout, retry and provider circuit breaker.
- technical syntax checks, numeric/table/chart evidence validation.
- render density/overflow constraints and image-quality checks.

Review or demote from semantic authority:

- `_balance_deck()` merging/moving bullets between slides.
- `_force_slide_count_exact()` when it must invent or semantically merge content.
- lecture keyword/regex inference when explicit presentation mode exists.
- automatic lecture enrichment late in finalization.
- keyword-heavy visual semantics as the primary design decision.
- fixed bullet counts that cause factual removal instead of reporting a density issue.

The current code already comments that LLM quality should shorten content semantically in some normalization paths, but other slices and merge rules still mutate content. These should first emit structured issues rather than directly rewriting facts.

## Hard truncation findings

Not all string slicing is harmful. Slicing filenames, log previews, prompt fields, renderer labels, provider payload limits and bounded visual descriptions is appropriate.

High-risk decision truncations:

- `deck_planner.py`: source capped at 30,000 characters for planning and authoring.
- `slide_quality.py`: grounding source excerpt capped at 12,000 characters.
- `slide_quality.py`: visual planning raw input excerpt capped at 5,000 characters.
- `deck_contract.py`: instructional repair source evidence capped at 30,000 characters.
- `technical_quality.py`: source evidence capped at 24,000 characters.
- `lecture_quality.py`: lecture detection only inspects bounded leading windows.
- legacy pipeline expand/group/section prompts commonly use leading 7,000-character previews.

The chunking path avoids losing the document tail during map summarization, but its merged summaries are lossy and do not retain a first-class mapping from planned section to evidence chunks/pages. Replace global leading slices in planning/validation with retrieval over a page/chunk index, not with simply larger limits.

## Grounding, retrieval and semantic duplicates

RAG-like infrastructure already exists in `source_retrieval.py`:

- page-aware chunks;
- BM25 lexical scores;
- optional `fastembed` embeddings;
- hybrid scoring and cached retrieval;
- configurable model, confidence and max pages.

This is useful evidence retrieval, but it is not yet the central source provider for planner, author and every validator. Several stages independently build leading excerpts.

Semantic duplicate detection is not implemented as a clear two-stage quality policy. Exact/normalized token matching appears in normalizer/coherence/image logic. The existing embedder can support stage-two duplicate detection, but it should be exposed behind a small interface, with a configurable threshold and tests, rather than coupling quality code to `fastembed`.

## Quality-pass overlap

The most significant overlap is:

```text
legacy pipeline:
  unified post-process
    -> refine / bullet repair / polish / final quality behavior
  -> density gate
  -> title repair
  -> normalize/balance

orchestrator:
  -> improve_slide_text_quality
  -> improve_deck_source_grounding

legacy finalize:
  -> improve_final_slide_quality
  -> lecture enrich + provenance
  -> technical/coherence repair
  -> lecture enrich + provenance again
  -> count/boundary repair, sometimes twice
  -> instruction coverage and instructional repair
  -> provenance again
  -> technical repair
  -> speaker-note repair
  -> stable IDs / lock
```

The locked-outline branch is substantially cleaner and should be the evolutionary base. `deck_coherence` already produces cleaned structured issues and performs selected-slide repair; it is the best candidate for a unified `ValidationIssue` schema. Do not delete the other passes until benchmark cases show which defects each uniquely catches.

## Structure-lock and design boundary

The structure lock is real and useful:

- stable IDs are assigned before visual work;
- count, uniqueness, intro and closing invariants are asserted;
- table/chart/image stages reassert the signature;
- specs and image paths can be mapped by slide ID.

One important violation of the intended invariant remains: after image generation, the worker may call `_expand_slide_bullets_for_no_image()` for slides whose image failed. This changes textual content after structure lock (although not slide order/count). The intended future contract should lock both structure and content fields, and handle missing images through a design/layout fallback or an explicitly permitted field repair.

The renderer already controls geometry, so future adaptive design should add contracts after lock:

```text
DesignProfile (deck-level palette/type/background/density)
  + SlideDesignIntent (primitive + visual weight + visual requirement)
  -> deterministic renderer geometry
  -> visual validator
```

The current frontend “automatic topic template” prototype is independent of this backend boundary and should not be mistaken for full Design Intelligence.

## Risk register

| Priority | Risk | Impact | First mitigation |
|---|---|---|---|
| P0 | No reproducible baseline can currently run in this environment | Refactors cannot prove behavior preservation | Create/use project venv, install pinned test dependencies, run current suite unchanged |
| P0 | Long documents bypass outline-first planning | Weak global coverage exactly where hierarchy matters most | Plan from chunk representations with source refs, then author sections against one locked plan |
| P0 | Global decisions use leading character slices | Late facts/numbers can disappear or be judged unsupported | Route planner/validators through page-aware retrieval |
| P1 | Duplicate inline/worker orchestration | Fixes can land in one path only | Extract one application-level generation workflow used by both adapters |
| P1 | Overlapping full-deck quality passes | Cost, latency and semantic drift | Add issue telemetry, consolidate only after benchmark attribution |
| P1 | Mutable extractor state encodes generation mode/context | Hidden coupling and concurrency/test complexity | Introduce explicit immutable `GenerationContext` |
| P1 | Late lecture enrichment and force-count can rewrite semantics | Grounded facts may move/disappear | Convert semantic mutations into planner requirements or targeted issues |
| P1 | Text expansion after structure lock when image fails | “Lock” does not fully mean final content | Use layout fallback after lock; prohibit silent prose mutation |
| P2 | Config flags span provider, product and quality concerns | Hard deployment/debugging | Typed grouped config after caller map/tests |
| P2 | Direct calls to private extractor LLM methods | Provider/content coupling | Add typed gateway without replacing provider implementation |
| P2 | Semantic dedup is fragmented | Repeated concepts survive exact checks | Two-stage exact + embedding detector with measured threshold |

## Benchmark and instrumentation plan

Before Phase B behavioral work, add a small versioned fixture set with expected invariants:

1. short Vietnamese topic prompt;
2. long topic prompt;
3. Vietnamese source document;
4. English source document;
5. technical/code document;
6. document rich in numbers/dates;
7. long document with mandatory evidence only near the end;
8. explicit lecture request;
9. ordinary presentation request containing education-like vocabulary;
10. explicit revision request.

Capture per task:

- pipeline path and generation mode;
- call purpose/provider/model, attempt count, tokens if exposed, latency and fallback;
- plan requirement coverage and source refs;
- exact slide count/schema/empty slide rate;
- numbers/dates preserved;
- exact and semantic duplicate rate;
- actionable issues by type and repair outcome;
- source faithfulness sampled against retrieved evidence;
- visual overflow/overlap and layout diversity once design work begins.

Use a deterministic validator for schemas/counts/numeric preservation and a clearly labeled evaluator for semantic metrics. Fix model/provider/config for before/after comparisons.

## Recommended implementation sequence

### Phase A.1 — make the baseline executable

- Pin/install test dependencies in the intended venv or container.
- Run all existing tests and save the result.
- Add a call-purpose ledger around the existing LLM gateway without changing routing.
- Add the benchmark fixture schema and runner; do not optimize quality yet.

### Phase B — structural seams, behavior preserved

- Extract one shared generation orchestrator used by HTTP inline and Redis worker paths.
- Introduce immutable request/context objects.
- Add typed configuration groups while preserving current environment variable names.
- Wrap current provider behavior in an `LLMGateway`; keep Qwen/vLLM -> circuit breaker -> Gemini unchanged.

### Phase C — content intelligence

- Define `ContentPlan` with goal, sections, importance, complexity, source refs and slide allocation.
- Feed it from full short source or hierarchical chunk representations for long source.
- Make prompt/document grounding policy explicit.
- Standardize validators on a shared issue schema and target only affected fields/slides.
- Add exact then embedding-based duplicate detection using the existing retrieval embedding boundary.

### Phase D — simplify after measurement

- Compare defect attribution and remove only redundant passes.
- Make the locked-outline finalizer the common path.
- Guarantee content and structure are stable before visuals.

### Phase E — design preparation

- Add `DesignProfile` and controlled semantic layout primitives after content lock.
- Keep coordinates and collision handling deterministic in the renderer.

## Phase A conclusion

The target architecture is feasible without a rewrite. The safest route is to converge the long-document and fallback paths onto the existing outline-first/locked-contract approach, then improve planning and grounding behind stable interfaces. The first code change should be observability and an executable benchmark—not moving modules or deleting heuristics.

## Phase A.1 implementation status

Completed after the audit:

- Added repository-level pytest configuration so `python -m pytest -q` resolves `backend/services` consistently.
- Added metadata-only LLM telemetry for provider, model, call purpose, outcome, latency, token budget, JSON mode and fallback origin. Prompt/response content is deliberately excluded.
- Instrumented both the plain-text provider path and the structured JSON vLLM/Gemini path without changing routing, prompts, timeouts or retry policy.
- Added ten versioned benchmark case definitions and an offline deterministic scorer.
- Post-change test result: **184 passed, 1 skipped**.

No live provider benchmark was executed, so no Gemini credits were consumed and no before/after generation-quality claim is made yet.

## Phase B.1 implementation status

The first behavior-preserving structural fix removes shared request state from the HTTP generation paths. `ContentExtractor` stores source text, focused source, user instruction, presentation mode, language hint and progress counters on the instance; the previous module-global instance could therefore leak or overwrite state when background jobs overlapped. Upload extraction, slide-spec generation and revision now create one extractor per task and attach the task ID to its telemetry. The Redis worker already constructed an extractor per task and remains unchanged.

## Phase B.2 implementation status

The common pre-visual transition now lives in `services/generation_workflow.py`. Both HTTP background generation and both Redis generation paths use the same function for source grounding, optional historical exact-count restoration, final content contract and structure-lock assertion. The adapters still own extraction progress and image/chart/table/PPTX work; those larger sections are intentionally not moved without more characterization tests. The helper retains the one existing adapter difference through an explicit compatibility flag instead of silently changing behavior. Post-change result: **187 passed, 1 skipped**.

## Phase B.3 implementation status

Added immutable typed views for runtime, LLM provider, generation, quality, image and design configuration in `config_groups.py`. All legacy constants and environment variable names remain intact. The provider client is the first consumer migrated to `LLMConfig`; other modules remain on legacy constants until they are changed in bounded steps. Secret fields are excluded from dataclass representations. The design group explicitly permits controlled layout primitives and rejects free-form model coordinates. Post-change result: **190 passed, 1 skipped**.

## Phase B.4 implementation status

Added an immutable `GenerationContext` and explicit `GenerationMode` values for prompt, document, explicit-slide and revision flows. New extraction requests bind source, focused source, instruction, title hint, requested count, exact-count policy, output language and presentation-mode decision into one context. A compatibility bridge mirrors the context into legacy mixin attributes, so this step does not require a risky all-at-once rewrite. Revision processing now binds the same explicit context instead of assigning mode fields independently. Source and instruction are excluded from context representations. Post-change result: **192 passed, 1 skipped**.

## Phase C.1 implementation status

Added provider-neutral `ContentPlan`, `ContentSection` and `SourceRef` contracts. The allocator reserves boundary slides, distributes the exact remaining budget by semantic importance and complexity, guarantees one slide per section when the budget permits, and reports zero-allocation sections when it does not; it never merges or rewrites content. Long-document chunk flows now build and retain `_content_plan` metadata with chunk references before entering the legacy generator. This is intentionally observational: legacy generation does not consume the plan yet, allowing benchmark comparison before behavior changes. Post-change result: **196 passed, 1 skipped**.

## Phase C.2 implementation status

Long-document generation now consumes `ContentPlan` through the same outline-first planner and locked authoring contract used by the structured path. Chunk summaries provide bounded semantic importance and complexity scores, while split summaries retain their original chunk index and detected page markers for source traceability. Both planner and author receive the plan, including exact per-section slide recommendations. If hierarchical planning fails or times out, generation falls back to the previous long-document pipeline, restores the exact requested slide count and retains the plan plus an explicit fallback marker for diagnostics. Public request and response contracts remain unchanged. Post-change result: **199 passed, 1 skipped**.

## Phase C.3 implementation status

Added one shared grounding policy used by outline planning, locked-outline authoring and the legacy source-review pass. Document mode treats uploaded content as factual authority while user instructions control scope and presentation; prompt mode permits stable foundational explanation without pretending generated background is uploaded evidence. The policy preserves exact names, dates, quantities, units and qualifications and prohibits invented citations, quotations, findings and statistics. Document generation now deterministically extracts numeric anchors from source plus explicit user quantities, detects unsupported numbers in the authored deck and requests one targeted repair without changing the locked outline. Any values that remain after repair are retained as internal grounding warnings for the later shared-validator phase rather than silently passing as verified. Post-change result: **203 passed, 1 skipped**.

## Phase C.4 implementation status

Added a canonical immutable `QualityIssue` contract shared by deterministic checks and LLM audits. It normalizes legacy aliases, validates slide indices, severity and issue type, records optional evidence, and explicitly names the fields a repair may change. Technical syntax checks, boundary-layout checks, semantic coherence issues and unresolved numeric-grounding warnings now enter the same normalization path. Coherence refinement includes each issue contract in its payload and applies returned changes only to `target_fields`, preserving unrelated titles, notes, roles and content even if the model attempts to rewrite them. Legacy `index`, `type`, `severity` and `instruction` keys remain available, so external API behavior is unchanged. Post-change result: **207 passed, 1 skipped**.

## Phase C.5 implementation status

Added deterministic-first duplicate-content detection before coherence repair. Normalized fingerprints identify exact repeated body slides without model cost, then the existing retrieval embedding boundary checks the remaining pairs for semantic duplication. The later slide is always the repair target and the earlier source-grounded slide is preserved. Cover, objectives, summary and closing slides are excluded, while semantically related concept/practice or concept/worked-example pairs are protected when their pedagogical roles differ. Embedding failures degrade to exact-only detection and never block generation. Duplicate findings use the shared `QualityIssue` contract and therefore flow through field-targeted repair. Post-change result: **212 passed, 1 skipped**.

## Phase D.1 implementation status

Added content-free quality-pass telemetry around the major legacy and outline-locked finalization stages. Each event records pass name, latency, LLM-call delta, input/output slide count, changed slide indices, changed field names and whether the pass had no observable effect; no prompt, source, slide text or model response is logged. An offline log aggregator reports per-pass run count, LLM cost proxy, latency, changed-slide events and no-effect rate. This establishes the evidence required to remove redundant reviews in a later bounded change; no quality pass has been deleted or reordered yet. Post-change result: **215 passed, 1 skipped**.

## Phase D.2 implementation status

Legacy and outline-first generation now converge on shared finalization primitives for deterministic issue collection, post-review technical cleanup/provenance, stable slide identity, exact-count validation, boundary validation and structure locking. Their remaining compatibility differences are declared in immutable `FinalizationPolicy` values instead of being embedded in duplicated control flow: legacy retains up to two instruction-coverage passes and count repair, while outline-first retains one coverage pass and rejects any pre-review count drift. Review order and provider behavior are unchanged. Post-change result: **217 passed, 1 skipped**.

## Phase D.3 implementation status

Added explicit, telemetry-visible safe skipping without deleting any quality capability. Instruction-coverage audit is skipped only when there is no user instruction—the underlying auditor already returned without work in that condition. Downstream speaker-note review is skipped only when the same deterministic note checks used internally report no candidates. Skipped passes record a fixed reason and are separated from executed no-effect passes in both in-memory summaries and the offline log aggregator, preventing skip rates from being misreported as wasted LLM work. All semantic/model-dependent passes remain enabled until representative live benchmark evidence exists. Post-change result: **218 passed, 1 skipped**.

## Phase E.1 implementation status

Added immutable deck-level `DesignProfile` and per-slide `SlideDesignIntent` contracts. They are derived only after the structure lock, map existing layout names to a controlled primitive vocabulary, preserve stable slide IDs, and contain no free-form coordinates. The existing renderer still owns exact palette, typography and geometry; the generated plan is kept on the request-scoped extractor as an observational extension point and is not sent to clients or applied to rendering. Planning failures cannot break slide generation. Post-change result: **220 passed, 1 skipped**.
