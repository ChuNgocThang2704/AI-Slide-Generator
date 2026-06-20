# Content Extraction Package

This folder contains the active content extraction implementation.

Current split:

- `extractor.py`: active implementation copied out of the old monolithic entrypoint.
- `chunking.py`: long-document chunking, summarization, outline planning, and reduce flow.
- `input_processing.py`: text normalization, heading detection, chunk splitting, and fallback deck builder.
- `json_utils.py`: JSON extraction and repair helpers.
- `llm_client.py`: plain-text vLLM/Gemini completion helpers.
- `prompts.py`: prompt templates, guided JSON schemas, and prompt constants.
- `errors.py`: shared extractor exceptions.

Rollback reference:

- `../content_extractor_legacy.py`: old monolithic implementation kept for comparison only.

Remaining planned split from `extractor.py`:

- `quality.py`: bullet truncation, density, and final deck quality gates.
- `pipeline.py`: raw text -> expanded text -> grouped sections -> refined deck.
- `visual_semantics.py`: image/chart/table semantic extraction wrappers.

Keep refactors behavior-preserving. Move one concern at a time, then test with
the same sample inputs before moving the next concern.
