"""Package trích xuất nội dung.

API công khai (Public API):
  from services.content.extractor import ContentExtractor, TaskCancelledError

Các module nội bộ (import trực tiếp nếu cần):
  - chunking          ChunkingMixin
  - input_processing  InputProcessingMixin
  - llm_client        LLMClientMixin
  - slide_normalizer  SlideNormalizerMixin
  - slide_pipeline    SlidePipelineMixin
  - image_extraction  ImageExtractionMixin
  - prompts           Toàn bộ các chuỗi prompt và JSON schema
  - json_utils        parse_json_response, try_fix_json
  - errors            TaskCancelledError
"""
