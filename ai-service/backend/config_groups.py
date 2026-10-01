"""Typed, immutable views over the legacy environment-backed constants.

Existing names in ``config.py`` remain the compatibility contract. New code can
consume these groups without forcing a repository-wide configuration rewrite.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Tuple

import config as legacy


@dataclass(frozen=True)
class RuntimeConfig:
    base_dir: Path
    upload_dir: Path
    output_dir: Path
    image_dir: Path
    redis_url: str
    redis_offload_when_worker_alive: bool
    redis_queue_min_chars: int
    api_host: str
    api_port: int
    max_file_size: int
    allowed_extensions: Tuple[str, ...]


@dataclass(frozen=True)
class LLMConfig:
    model: str
    vllm_base_url: str
    vllm_timeout_sec: float
    vllm_use_guided_json: bool
    vllm_guided_decoding_backend: str
    vllm_basic_auth_user: str = field(repr=False)
    vllm_basic_auth_pass: str = field(repr=False)
    gemini_model: str = ""
    gemini_api_key: str = field(default="", repr=False)
    gemini_timeout_sec: float = 120.0
    vertex_enabled: bool = False
    gcp_project_id: str = ""
    gcp_region: str = "us-central1"
    gcp_service_account_json_path: str = field(default="", repr=False)


@dataclass(frozen=True)
class GenerationConfig:
    context_tokens: int
    repeat_penalty: float
    use_json_format: bool
    chunk_threshold: int
    single_pass_char_limit: int
    short_path_skip_summarize: bool
    fast_mode: bool
    quality_mode: bool
    chunk_timeout_sec: float
    chunk_fast_timeout_sec: float
    subchunk_timeout_sec: float
    chunk_parallel: int
    retrieval_enabled: bool
    embedding_enabled: bool
    embedding_model: str
    retrieval_min_confidence: float
    retrieval_max_pages: int
    embedding_cache_dir: str


@dataclass(frozen=True)
class QualityConfig:
    final_compose: bool
    final_compose_enforce_outline: bool
    refine_extra_if_truncated: bool
    refine_max_extra_passes: int
    bullet_polish_pass: bool
    final_quality_gate: bool
    final_quality_gate_max_fixes: int
    presentation_style_mode: bool
    final_density_gate: bool
    final_density_min_bullets: int
    final_density_max_rewrites: int


@dataclass(frozen=True)
class ImageConfig:
    api_base_url: str
    api_key: str = field(repr=False)
    timeout_sec: float = 600.0
    concurrency: int = 1
    max_slides_with_images: int = 0
    width: int = 1024
    height: int = 1024
    steps: int = 4
    guidance_scale: float = 0.0
    stock_photo_enabled: bool = True
    clip_validation_enabled: bool = True
    clip_min_score: float = 0.22
    vlm_judge_enabled: bool = True


@dataclass(frozen=True)
class DesignConfig:
    """Current renderer boundary; no free-form coordinates are enabled."""

    controlled_layouts: Tuple[str, ...] = (
        "intro", "title_content", "two_columns", "comparison",
        "text_image", "timeline", "text_chart", "text_table", "big_quote", "thankyou",
    )
    allow_freeform_coordinates: bool = False


RUNTIME_CONFIG = RuntimeConfig(
    base_dir=legacy.BASE_DIR,
    upload_dir=legacy.UPLOAD_DIR,
    output_dir=legacy.OUTPUT_DIR,
    image_dir=legacy.IMAGE_DIR,
    redis_url=legacy.REDIS_URL,
    redis_offload_when_worker_alive=legacy.REDIS_OFFLOAD_WHEN_WORKER_ALIVE,
    redis_queue_min_chars=legacy.REDIS_QUEUE_MIN_CHARS,
    api_host=legacy.API_HOST,
    api_port=legacy.API_PORT,
    max_file_size=legacy.MAX_FILE_SIZE,
    allowed_extensions=tuple(legacy.ALLOWED_EXTENSIONS),
)

LLM_CONFIG = LLMConfig(
    model=legacy.LLM_MODEL,
    vllm_base_url=legacy.VLLM_API_BASE_URL,
    vllm_timeout_sec=legacy.VLLM_TIMEOUT_SEC,
    vllm_use_guided_json=legacy.VLLM_USE_GUIDED_JSON,
    vllm_guided_decoding_backend=legacy.VLLM_GUIDED_DECODING_BACKEND,
    vllm_basic_auth_user=legacy.VLLM_BASIC_AUTH_USER,
    vllm_basic_auth_pass=legacy.VLLM_BASIC_AUTH_PASS,
    gemini_model=legacy.GEMINI_MODEL,
    gemini_api_key=legacy.GEMINI_API_KEY,
    gemini_timeout_sec=legacy.GEMINI_TIMEOUT_SEC,
    vertex_enabled=legacy.GCP_VERTEX_AI_ENABLE,
    gcp_project_id=legacy.GCP_PROJECT_ID,
    gcp_region=legacy.GCP_REGION,
    gcp_service_account_json_path=legacy.GCP_SERVICE_ACCOUNT_JSON_PATH,
)

GENERATION_CONFIG = GenerationConfig(
    context_tokens=legacy.LLM_NUM_CTX,
    repeat_penalty=legacy.LLM_REPEAT_PENALTY,
    use_json_format=legacy.LLM_USE_JSON_FORMAT,
    chunk_threshold=legacy.LLM_CHUNK_THRESHOLD,
    single_pass_char_limit=legacy.LLM_SINGLE_PASS_CHAR_LIMIT,
    short_path_skip_summarize=legacy.LLM_SHORT_PATH_SKIP_SUMMARIZE,
    fast_mode=legacy.LLM_FAST_MODE,
    quality_mode=legacy.LLM_QUALITY_MODE,
    chunk_timeout_sec=legacy.LLM_CHUNK_TIMEOUT_SEC,
    chunk_fast_timeout_sec=legacy.LLM_CHUNK_FAST_TIMEOUT_SEC,
    subchunk_timeout_sec=legacy.LLM_SUBCHUNK_TIMEOUT_SEC,
    chunk_parallel=legacy.LLM_CHUNK_PARALLEL,
    retrieval_enabled=legacy.SOURCE_RETRIEVAL_ENABLED,
    embedding_enabled=legacy.SOURCE_EMBEDDING_ENABLED,
    embedding_model=legacy.SOURCE_EMBEDDING_MODEL,
    retrieval_min_confidence=legacy.SOURCE_RETRIEVAL_MIN_CONFIDENCE,
    retrieval_max_pages=legacy.SOURCE_RETRIEVAL_MAX_PAGES,
    embedding_cache_dir=legacy.SOURCE_EMBEDDING_CACHE_DIR,
)

QUALITY_CONFIG = QualityConfig(
    final_compose=legacy.LLM_FINAL_COMPOSE,
    final_compose_enforce_outline=legacy.LLM_FINAL_COMPOSE_ENFORCE_OUTLINE,
    refine_extra_if_truncated=legacy.LLM_REFINE_EXTRA_IF_TRUNCATED,
    refine_max_extra_passes=legacy.LLM_REFINE_MAX_EXTRA_PASSES,
    bullet_polish_pass=legacy.LLM_BULLET_POLISH_PASS,
    final_quality_gate=legacy.LLM_FINAL_QUALITY_GATE,
    final_quality_gate_max_fixes=legacy.LLM_FINAL_QUALITY_GATE_MAX_FIXES,
    presentation_style_mode=legacy.LLM_PRESENTATION_STYLE_MODE,
    final_density_gate=legacy.LLM_FINAL_DENSITY_GATE,
    final_density_min_bullets=legacy.LLM_FINAL_DENSITY_MIN_BULLETS,
    final_density_max_rewrites=legacy.LLM_FINAL_DENSITY_MAX_REWRITES,
)

IMAGE_CONFIG = ImageConfig(
    api_base_url=legacy.IMAGE_GEN_API_BASE_URL,
    api_key=legacy.IMAGE_GEN_API_KEY,
    timeout_sec=legacy.IMAGE_GEN_TIMEOUT_SEC,
    concurrency=legacy.IMAGE_GEN_CONCURRENCY,
    max_slides_with_images=legacy.IMAGE_MAX_SLIDES_WITH_IMAGES,
    width=legacy.IMAGE_WIDTH,
    height=legacy.IMAGE_HEIGHT,
    steps=legacy.IMAGE_STEPS,
    guidance_scale=legacy.IMAGE_GUIDANCE_SCALE,
    stock_photo_enabled=legacy.STOCK_PHOTO_ENABLE,
    clip_validation_enabled=legacy.IMAGE_CLIP_VALIDATE_ENABLE,
    clip_min_score=legacy.IMAGE_CLIP_MIN_SCORE,
    vlm_judge_enabled=legacy.IMAGE_VLM_JUDGE_ENABLE,
)

DESIGN_CONFIG = DesignConfig()

