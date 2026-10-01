from dataclasses import FrozenInstanceError

import config
from config_groups import DESIGN_CONFIG, GENERATION_CONFIG, IMAGE_CONFIG, LLM_CONFIG, QUALITY_CONFIG, RUNTIME_CONFIG


def test_typed_groups_preserve_legacy_environment_values():
    assert LLM_CONFIG.model == config.LLM_MODEL
    assert LLM_CONFIG.vllm_base_url == config.VLLM_API_BASE_URL
    assert GENERATION_CONFIG.chunk_threshold == config.LLM_CHUNK_THRESHOLD
    assert QUALITY_CONFIG.final_density_gate == config.LLM_FINAL_DENSITY_GATE
    assert IMAGE_CONFIG.api_base_url == config.IMAGE_GEN_API_BASE_URL
    assert RUNTIME_CONFIG.redis_url == config.REDIS_URL


def test_secrets_are_not_exposed_by_repr():
    rendered = repr(LLM_CONFIG)
    assert "gemini_api_key=" not in rendered
    assert "vllm_basic_auth_pass=" not in rendered


def test_groups_are_immutable_and_design_rejects_freeform_coordinates():
    try:
        LLM_CONFIG.model = "changed"
        raise AssertionError("frozen config accepted mutation")
    except FrozenInstanceError:
        pass
    assert DESIGN_CONFIG.allow_freeform_coordinates is False
    assert "text_chart" in DESIGN_CONFIG.controlled_layouts

