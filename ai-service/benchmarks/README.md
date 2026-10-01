# AI slide benchmark

`cases.json` defines ten stable scenarios from the Phase A audit. It contains no API credentials and does not invoke providers.

Save a generated structured deck as JSON, then run:

```powershell
.\.venv\Scripts\python.exe benchmarks/evaluate.py vi_short_topic outputs\benchmark\vi_short_topic.json
```

To run one prompt fixture against a running AI service (this invokes the configured
provider and may use quota), use:

```powershell
python benchmarks/run_live_case.py vi_short_topic --base-url http://127.0.0.1:8000
```

The runner disables image generation and writes the deck plus a task-status record
under `~/lecgen-benchmark`. If generation succeeded but saving failed, recover the
existing result without a second provider call using `--task-id TASK_ID`. Its
`elapsed_seconds` value then measures only the resume/poll operation, not the
original generation. Document fixtures are uploaded as UTF-8 `.txt` files.
Revision fixtures are not supported by this runner yet.

The deck API response does not contain the internal LLM-call ledger. An evaluator
result of `llm_calls: null` means *unavailable*, not zero; use worker telemetry for
cost and latency analysis.

The offline scorer checks slide count, empty slides, required topic coverage, literal number/date preservation and requested presentation mode. Semantic faithfulness, coherence and note quality still require a separately versioned evaluator; they must not be presented as deterministic scores.
In particular, `passed_static_checks: true` does **not** mean a document-grounded
deck is faithful to its source; inspect unsupported explanations, causes and
recommendations even when all numbers are preserved.

Quality passes emit content-free `[quality_pass]` JSON log lines. After an end-to-end benchmark run, aggregate cost and no-effect rates with:

```powershell
.\.venv\Scripts\python.exe benchmarks/summarize_quality_passes.py path\to\application.log
```

Do not remove a pass based on one run. Compare its no-effect rate, LLM calls, latency, and downstream benchmark scores across the complete fixture set first.
