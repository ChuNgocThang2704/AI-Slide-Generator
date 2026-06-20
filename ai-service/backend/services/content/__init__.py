"""Content extraction package.

Public API:
  from services.content.extractor import ContentExtractor, TaskCancelledError

Internal modules (import directly if needed):
  - chunking          ChunkingMixin
  - input_processing  InputProcessingMixin
  - llm_client        LLMClientMixin
  - slide_normalizer  SlideNormalizerMixin
  - slide_pipeline    SlidePipelineMixin
  - image_extraction  ImageExtractionMixin
  - prompts           All prompt strings and JSON schemas
  - json_utils        parse_json_response, try_fix_json
  - errors            TaskCancelledError
"""
