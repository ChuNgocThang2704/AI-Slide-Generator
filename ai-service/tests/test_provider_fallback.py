import asyncio

import pytest

from services import provider_health
from services.content.llm_client import LLMClientMixin


class _Client(LLMClientMixin):
    model_name = "Qwen3-VL-8B"
    vllm_available = True
    vllm_base_url = "http://127.0.0.1:1"
    vllm_basic_auth = None
    gemini_available = True
    gemini_model = "gemini-test"
    gemini_api_key = "test"

    async def _gemini_completion_plain_text(self, *args, **kwargs):
        return "gemini-fallback"


@pytest.mark.parametrize("provider", ["auto", "vllm"])
def test_open_vllm_circuit_uses_gemini(provider):
    provider_health.mark_vllm_unavailable()

    result = asyncio.run(
        _Client()._llm_completion_plain_text(
            [{"role": "user", "content": "test"}],
            provider=provider,
        )
    )

    assert result == "gemini-fallback"
