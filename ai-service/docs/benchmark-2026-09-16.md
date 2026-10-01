# Phase F: first live benchmark sample (2026-09-16)

Scope: one `vi_short_topic` prompt fixture on the Azure AI worker, using
`gemini-3.1-flash-lite`, `plan=pro`, eight requested slides and image generation
disabled. This is a smoke/quality sample, **not** a before/after benchmark or a
claim about all ten fixtures. The generated deck remains outside the repository
in the benchmark output directory.

## Observed result

| Measure | Result |
| --- | --- |
| Task | `e22c1ed3-0bb0-400a-a453-f84b64d7dde3`, completed |
| Slide count | 8/8 |
| Empty slides | 0 |
| Required topic coverage | Passed |
| Static fixture checks | Passed |
| Gemini calls in worker telemetry | 15; no provider error in this task's logs |
| Image generation | Disabled |

The deck includes an introduction, learning objectives, AI history, machine
learning/deep learning, practical study use, applications, ethics and a conclusion.
Speaker notes are present on all eight slides (about 536–635 characters each).
Two slides have table layouts. These observations do not verify factual accuracy,
visual rendering or whether the notes sound natural when narrated.

The opening slide still puts a long definition of AI and an importance statement
into its two bullets. This is a concrete presentation-quality issue: the opening
reads more like the first content slide than a clean title/overview slide. Treat
it as a separate design/content acceptance check before calling the phase done.

### Cover-quality follow-up

After adding a post-review cover check, the same fixture was generated again on
the deployed worker as task `d896838b-0ee1-43eb-b77f-62ad2d52cb6a`.
It completed in **75.1 seconds** (runner-measured end-to-end task time), with
8/8 slides, no empty slide, and all static fixture checks passing. The opening
now has one scope-preview bullet:

> Từ Hành trình tiến hóa của AI đến Đạo đức và trách nhiệm trong kỷ nguyên AI

The original detail is retained in speaker notes where needed. This resolves
the specific verbose-cover failure in this sample; it does not establish that
the full deck is visually polished or factually accurate. The generated slide
title's capitalization inside the subtitle could still be improved editorially.

Worker quality-pass telemetry for the task recorded five coherence-review calls
(two slides changed), two speaker-note-review calls (eight slides changed), and a
zero-call instruction-coverage pass. The deck response does not expose the LLM
ledger, so the offline evaluator reports `llm_calls: null`; the 15-call count is
from worker logs, not from the deck JSON. The resumed result-fetch duration is not
the original generation latency and must not be used as such.

## Remaining evaluation work

- Run the other prompt modes and document-grounded fixtures, especially numeric
  preservation and evidence near the end of a source document.
- Score source faithfulness, note quality and rendered layout with a versioned
  rubric and human review; static checks alone cannot establish these.
- Measure true end-to-end latency and provider cost, then compare against a
  recorded baseline before removing or retuning quality passes.
- Verify the authenticated FE → BE → AI path separately; this run called AI
  directly and did not exercise that integration.

## First document-grounding case: numbers and dates

The `numbers_dates` fixture was uploaded as a UTF-8 `.txt` source and generated
as task `41cf9d2e-bf00-4448-95e5-76e773eddb31`. It completed in **84.11
seconds** with 7/7 slides and no empty slide. The offline scorer found every
literal target (`2024`, `12,5`, `2,1`, `3,0`, `3,4`, `4,0`) and reported a static
pass.

**Manual source-faithfulness review: fail.** The source contains only the annual
revenue and four quarterly figures. The deck additionally asserts marketing
campaign effects, a customer segment, operating-cost pressure, product changes,
and a 2025 growth strategy. None of those claims is supported by the fixture.
Preserving numbers is therefore insufficient. Do not use this output as a
grounded document presentation without editing it.

The document runner first received HTTP 400 because the API requires an
instruction alongside an uploaded file. That request was rejected before AI
generation; the runner now sends a scope/preservation instruction and supports
both prompt and document fixtures. No full-suite quality claim follows from
these two live fixture types.

### Grounding guard follow-up

Investigation found a routing defect: uploaded `.txt` content under 800
characters was classified as a *prompt*, then expanded by the LLM before slide
planning. The API now explicitly carries uploaded-file provenance to the worker,
so even a short uploaded file stays in document mode. A separate final audit
checks titles, bullets, notes, tables and charts for unsupported source claims,
asks for one targeted repair, and rejects the task if claims remain.

Task `7e5e827e-afbb-4dab-aea0-081d70f498b9` verified the new path: worker
logs show document mode and no prompt-expansion call. The audit found unsupported
claims, attempted repair, found remaining claims and returned an **error rather
than a fabricated deck**. This is safer, but it is not a successful generation
for sparse-source/exact-seven-slide requests. The semantic audit is LLM-based,
so it cannot guarantee perfect detection; the current audit is also limited to
source texts of at most 30,000 characters. Both constraints need further work.

### Sparse-source adjustment

The planner/author now receive explicit instructions to distribute a small set
of source facts across different evidence views rather than filling the deck
with invented causes or strategy. The final checker allows at most two targeted
repair attempts, auditing again after each. Local tests pass, and the updated
AI service/worker are running. The follow-up `numbers_dates` live run is reported
below. The extra repair attempt can also increase provider calls when needed.

## Final representative runs (2026-09-17)

- `numbers_dates`, task `9b795595-2944-467c-9793-216e74587c44`: completed
  in 108.12 seconds with 7/7 slides, all specified figures retained, and no
  fabricated marketing or strategy explanations in the reviewed output. Manual
  review still noted one unsupported rhetorical claim in the opening notes
  that the data had been "verified"; this is not a perfect source-faithfulness
  result.
- `late_evidence`, task `75fdfa59-c855-428f-a393-f88cba5afe54`: failed after
  216.18 seconds. The source repair omitted a flagged slide, so the task failed
  closed. A Gemini HTTP 503 also occurred during an earlier review pass. The
  input has a `PAGE 99` marker but is short text; this is a late-evidence test,
  **not** a real long-document performance test.

Consequently Phase F is **not complete**: the document path has one acceptable
but imperfect sample and one failed sample, and neither a real long-document
run nor a before/after comparison exists. No additional provider run was made
after the repair-omission handling change. The final representative suite must
be rerun after that change before any completion claim.

During log inspection, an HTTP error exposed a Gemini API key in the request
URL recorded by the old client. The local code now sends the key in the
`x-goog-api-key` header instead; the existing key should be rotated because
old log copies cannot be assumed private. As of 2026-09-17, the header change
and the bounded per-slide repair fallback are **not deployed**: SSH, HTTP/80,
and HTTP/5173 to `20.196.152.241` all timed out. No post-fix provider smoke
or late-evidence rerun was possible.

### Final deployment and rerun (2026-09-17)

The Azure host became reachable again. The header-authentication change and
per-slide repair fallback were deployed to the AI service and worker. The
service health endpoint returned HTTP 200. A first submission during startup
failed to connect before any task was created. The subsequent `late_evidence`
task `b818fe25-7a1d-42aa-afba-638bd412dd26` reached the worker but ended in
`error` after 72.1 seconds: `Source-faithfulness repair omitted a flagged
slide`. No deck was published. This representative fixture still failed at
that point; the per-slide LLM repair fallback alone was not sufficient.

### Root cause and fix (2026-09-17, continued)

Investigation traced the remaining failure to two distinct problems, found by
inspecting worker logs across several redeploy-and-rerun cycles on the Azure
host (`20.196.152.241`):

1. The bounded per-slide repair made only one LLM attempt before giving up;
   a single malformed response was enough to fail the whole task. Fixed with
   a two-attempt retry before falling back further.
2. Even after that, the strict LLM auditor kept flagging **new** slides on
   each re-check — including a slide restated as a verbatim source
   sentence — over verb framing ("applies" vs. "lists a heading"), not an
   actual invented fact. Chasing this with more LLM repair rounds would not
   converge.

The real fix, per an explicit product decision (loosening the auditor was
considered and rejected in favor of not shrinking requested content further
than necessary): `sparse_document_slide_cap()` in
`services/grounding_policy.py` now counts distinct sentence/clause-sized
facts in the uploaded document and caps the requested slide count to
roughly one slide per fact plus an intro and closing slide, applied once in
`routes/api.py` before generation starts. It only ever lowers the count,
never raises it. A deterministic (non-LLM) literal-sentence fallback was
also added to `source_faithfulness.py` as a last resort: a slide the LLM
repair loop still can't fix is restated as an exact quote from the source,
and quoted slides are exempted from further audit rounds since a verbatim
quote cannot newly become "unsupported."

**Verified on the deployed worker:**

- `late_evidence`, task `78c6a5cf-64ff-4c9a-8af4-26af2320272b`: completed in
  84.1 seconds with 8/8 slides, but manual review found the deterministic
  fallback alone (without the slide-count cap) produced 5 duplicate slides
  repeating the same sentence because only 3 distinct facts existed for 8
  requested slides. This confirmed the cap was still needed, not just the
  fallback.
- `late_evidence`, task `b50c91e3-80d9-4244-a2c5-3fddd9862734` (after adding
  the slide-count cap): completed in 51.1 seconds with **5/5 slides** (capped
  down from the requested 8). Manual review: all three source facts (project
  overview, three-phase method, 87,6% completion by 31/12/2025) are present,
  the closing slide correctly synthesizes the two preserved figures into a
  table, and no invented cause/strategy/stakeholder claim was found. One
  minor quality blemish remains: slide index 3 duplicates the intro's
  sentence verbatim (the deterministic fallback ran out of distinct source
  sentences once).
- `numbers_dates`, task `06bbae8a-0348-4776-837a-0bfba78913c5`: completed in
  72.1 seconds with **7/7 slides**, confirming the new slide-count cap does
  not shrink a fact-dense source (it computed the same 7-slide budget the
  fixture already used successfully). All six figures preserved, no
  fabricated marketing/strategy content in a spot check of the bullets.

232 to 235 local tests pass throughout (new coverage added for the literal
fallback and the slide-count cap). Both live reruns were driven directly
against the deployed worker on the Azure host via SSH, not through the
public API, because port 8000 is not exposed externally.

**Phase F status: the two representative document fixtures now complete
without fabricated claims.** The remaining known imperfection is the one
duplicated slide in the `late_evidence` case; this is a content-quality
issue, not a faithfulness violation (the duplicated sentence is itself
verbatim source text). No other fixtures (`vi_short_topic`, `en_long_topic`,
`vi_source`, `en_source`, `technical`, `explicit_lecture`,
`ordinary_presentation`, `revision`) were rerun in this pass; only the two
previously-failing/flagged document cases were used to confirm the fix,
consistent with the project's practice of minimizing live provider calls.
A full ten-fixture sweep, a versioned human-rubric review, and a latency/cost
baseline are still outstanding before Phase F can be called fully complete.

## Nine-of-ten fixture sweep (2026-09-17, continued)

The remaining fixtures were run live against the deployed worker
(`20.196.152.241`), continuing to use the SSH-side benchmark runner because
port 8000 is not exposed publicly. Partway through this sweep,
`gemini-3.1-flash-lite` started returning `429 Too Many Requests` on
`vi_source`, `en_source`, and `technical` (the third case only cleared after
a ~120 second wait). The deployed model was switched to
`gemini-3.5-flash-lite` in `docker-compose.azure.yml` (both `ai-service` and
`ai-worker`), which resolved the rate limiting for the rest of the sweep.
**This means the fixtures below did not all run against the same model**:
`vi_source` and `en_source` completed under `gemini-3.1-flash-lite` after the
cooldown; `technical`, `explicit_lecture`, and `ordinary_presentation` ran
under `gemini-3.5-flash-lite`. No before/after quality comparison between the
two models was made; this was a quota workaround, not a deliberate model
evaluation.

| Fixture | Status | Slides | Notes |
| --- | --- | --- | --- |
| `vi_short_topic` | completed | 8/8 | No spot-check issues found. |
| `en_long_topic` | completed | 10/10 | No spot-check issues found. |
| `vi_source` | completed | 4/7 | `sparse_document_slide_cap` reduced the count (source has 2 short facts); all 3 required topics (học máy, học có giám sát, học tăng cường) present, no fabricated claims. |
| `en_source` | completed | 4/6 | Same cap behavior as `vi_source`; not manually content-reviewed beyond slide/status counts. |
| `technical` | completed | 5/8 | Cap reduced count; all three must-preserve values (`O(log n)`, `[1, 3, 5, 7]`, `2`) present verbatim, no fabricated claims. |
| `explicit_lecture` | completed | 10/10 | `presentation_mode: lecture`; has objectives, concept, knowledge_check, demonstration and summary roles as required. |
| `ordinary_presentation` | completed | 8/8 | `presentation_mode: presentation` (not lecture); no objectives/knowledge_check slide was added, matching the fixture's explicit request. |
| `numbers_dates` | completed (already reported above) | 7/7 | — |
| `late_evidence` | completed (already reported above) | 5/8 | — |
| `revision` | not run | — | The benchmark runner (`run_live_case.py`) only supports `prompt` and `document` fixture modes; the revision fixture needs a separate existing-deck revision call this runner does not make. Still outstanding. |

All nine runnable fixtures completed without error, without a fabricated
claim in any manually-reviewed case, and with the correct presentation mode
in both mode-sensitive fixtures. The `document`-mode fixtures with thin
sources (`vi_source`, `en_source`, `technical`, `late_evidence`) all had
their slide count reduced below the requested amount by
`sparse_document_slide_cap`; this is expected behavior, not a failure, but
it does mean the deck no longer has exactly the slide count the caller
asked for whenever the source is sparse. `en_source` was not manually
content-reviewed beyond slide count.

Still outstanding before Phase F is complete: the `revision` fixture, a
versioned human-quality rubric (current review is ad hoc spot-checking),
a latency/cost baseline, and a deliberate same-model before/after
comparison (the mid-sweep model switch was a quota workaround, not a
controlled test).

### User-visible reduction notice (2026-09-17, continued)

Until now, `sparse_document_slide_cap` reduced the slide count silently: the
caller asked for N slides and received fewer with no indication why. A
`notices` array was added to the `/api/generate-slide-spec` response
(`{"type": "slide_count_reduced", "message": "..."}`), populated whenever
the requested count was shrunk for a sparse document, empty otherwise. This
required threading the notice through both independent code paths that
build the response (the inline background task in `routes/api.py` and the
Redis worker's `_process_slide_spec` in `services/redis_queue.py`), since
the two paths duplicate this logic (a pre-existing architectural issue the
Phase A audit already flagged). Verified live: `late_evidence` now returns
a Vietnamese notice explaining the reduction (8 requested to 5 actual), and
`numbers_dates` (which is not reduced) returns an empty `notices` array.
237 local tests pass, including two new tests locking in this behavior in
`tests/test_lecture_quality.py`.
