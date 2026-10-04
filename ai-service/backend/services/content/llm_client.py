"""Các hàm hỗ trợ nhà cung cấp LLM để trích xuất nội dung."""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List

# pyrefly: ignore [missing-import]
import httpx
from services.provider_health import mark_vllm_unavailable, vllm_circuit_open
from services.llm_telemetry import infer_call_purpose, monotonic_start, record_llm_call

from config_groups import LLM_CONFIG


def llm_gateway_headers() -> Dict[str, str]:
    """Bearer key for an OpenAI-compatible gateway (e.g. 9Router) in front of the LLM providers."""
    key = os.getenv("VLLM_API_KEY", "").strip()
    return {"Authorization": f"Bearer {key}"} if key else {}


_PRIMARY_HOST_DOWN_UNTIL = [0.0]  # monotonic deadline: the self-hosted LLM host failed, go straight to the gateway
_PRIMARY_HOST_FAILURES = [0]  # failures in a row, for the growing cooldown


async def _primary_host_completion(payload: Dict[str, Any], basic_auth: Any) -> str | None:
    """One completion from the self-hosted LLM (LLM_PRIMARY_BASE_URL), or None so the caller uses the gateway.

    The self-hosted model is the preferred one; the gateway (9Router) is the first fallback and direct
    Gemini the last. A failed host is skipped for LLM_PRIMARY_COOLDOWN_SEC so a dead host costs one
    short connect attempt, not one per call.
    """
    base = os.getenv("LLM_PRIMARY_BASE_URL", "").strip().rstrip("/")
    if not base or time.monotonic() < _PRIMARY_HOST_DOWN_UNTIL[0]:
        return None
    body = dict(payload)
    body["model"] = os.getenv("LLM_PRIMARY_MODEL", "").strip() or body.get("model")
    key = os.getenv("LLM_PRIMARY_API_KEY", "").strip()
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=5.0)) as client:
            resp = await client.post(
                f"{base}/v1/chat/completions",
                json=body,
                headers={"Authorization": f"Bearer {key}"} if key else {},
                auth=basic_auth,
            )
            resp.raise_for_status()
            text = ((resp.json().get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        if text.strip():
            _PRIMARY_HOST_FAILURES[0] = 0
            return text
    except Exception as error:
        # The host is only rented for demos: each failure in a row doubles the wait (3 min up to 30),
        # so an absent host costs one short connect attempt every half hour instead of every 3 minutes.
        _PRIMARY_HOST_FAILURES[0] += 1
        base = float(os.getenv("LLM_PRIMARY_COOLDOWN_SEC", "180"))
        cooldown = min(1800.0, base * (2 ** (_PRIMARY_HOST_FAILURES[0] - 1)))
        _PRIMARY_HOST_DOWN_UNTIL[0] = time.monotonic() + cooldown
        print(f"[LLMClient] primary LLM host failed ({type(error).__name__}); using the gateway for the next "
              f"{int(cooldown)}s")
    return None


class LLMClientMixin:
    """Các lệnh gọi nhà cung cấp LLM dùng chung cho pipeline trích xuất.

    Lớp sở hữu (owning class) phải định nghĩa:
    - model_name
    - vllm_available
    - vllm_base_url
    - vllm_basic_auth
    - gemini_available
    - gemini_model
    - gemini_api_key
    """

    async def _llm_completion_plain_text(
        self,
        messages: List[Dict[str, str]],
        *,
        max_tokens: int = 200,
        temperature: float = 0.55,
        json_mode: bool = False,
        provider: str = "auto",
        call_purpose: str | None = None,
        model_override: str | None = None,
    ) -> str:
        """Thực hiện một lượt hoàn thành trò chuyện (chat completion) và trả về văn bản thuần túy."""
        provider = (provider or "auto").strip().lower()
        purpose = call_purpose or infer_call_purpose()
        if vllm_circuit_open():
            self.vllm_available = False
        if provider == "gemini":
            # The "escalate to a stronger model" passes also go through the gateway first
            # (its stronger combo, if one is configured); the direct Gemini call below is
            # only reached if the gateway is down or exhausted, so it stays the last resort.
            if self.vllm_available and self.vllm_base_url and llm_gateway_headers():
                strong = os.getenv("NINE_ROUTER_STRONG_MODEL", "").strip() or None
                return await self._llm_completion_plain_text(
                    messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    json_mode=json_mode,
                    provider="vllm",
                    call_purpose=purpose,
                    model_override=strong,
                )
            return await self._gemini_completion_plain_text(
                messages,
                max_tokens=max_tokens,
                temperature=temperature,
                json_mode=json_mode,
                call_purpose=purpose,
            )
        model_name = model_override or self.model_name
        if self.vllm_available and provider in {"auto", "vllm", "vllm_only"}:
            nothink_msgs = list(messages)

            def _strip_think(text: str) -> str:
                text = text.strip()
                while "<think>" in text and "</think>" in text:
                    start = text.find("<think>")
                    end = text.find("</think>") + len("</think>")
                    text = (text[:start] + text[end:]).strip()
                return text

            timeout_cfg = httpx.Timeout(min(120.0, float(LLM_CONFIG.vllm_timeout_sec)), connect=25.0)
            payload: Dict[str, Any] = {
                "model": model_name,
                "messages": nothink_msgs,
                "temperature": float(temperature),
                "top_p": 0.92,
                "max_tokens": int(max_tokens),
                "stream": False,
            }
            if json_mode:
                payload["response_format"] = {"type": "json_object"}
            if "qwen3.5" in (model_name or "").lower():
                payload["extra_body"] = {
                    "chat_template_kwargs": {"enable_thinking": False}
                }
            if model_override is None:
                primary_text = await _primary_host_completion(payload, self.vllm_basic_auth)
                if primary_text is not None:
                    return _strip_think(primary_text)
            try:
                attempt_started = monotonic_start()
                async with httpx.AsyncClient(timeout=timeout_cfg) as client:
                    resp = await client.post(
                        f"{self.vllm_base_url}/v1/chat/completions",
                        json=payload,
                        headers=llm_gateway_headers(),
                        auth=self.vllm_basic_auth,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                text = (data.get("choices", [{}])[0].get("message") or {}).get("content", "") or ""
                record_llm_call(
                    self, purpose=purpose, provider="vllm", model=model_name,
                    started_at=attempt_started, status="success", max_tokens=max_tokens,
                    json_mode=json_mode,
                )
                return _strip_think(text)
            except Exception as e:
                record_llm_call(
                    self, purpose=purpose, provider="vllm", model=model_name,
                    started_at=attempt_started, status="error", max_tokens=max_tokens,
                    json_mode=json_mode, error=e,
                )
                is_connection_error = isinstance(e, httpx.RequestError) or "connection" in str(e).lower() or "timeout" in str(e).lower()
                if is_connection_error:
                    print(f"[LLMClient] vLLM connection failed: {e}. Disabling vLLM for this session.")
                    self.vllm_available = False
                    mark_vllm_unavailable()
                
                # Dự phòng (fallback) sang Gemini nếu có sẵn
                if provider in {"auto", "vllm"} and self.gemini_available:
                    print("Falling back to Gemini plain text completion.")
                    return await self._gemini_completion_plain_text(
                        messages,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        json_mode=json_mode,
                        call_purpose=purpose,
                        fallback_from="vllm",
                    )
                raise

        if provider == "vllm" and self.gemini_available:
            print("[LLMClient] vLLM unavailable; using Gemini for the requested review pass.")
            return await self._gemini_completion_plain_text(
                messages,
                max_tokens=max_tokens,
                temperature=temperature,
                json_mode=json_mode,
                call_purpose=purpose,
                fallback_from="vllm",
            )
        if provider in {"vllm", "vllm_only"}:
            raise RuntimeError("vLLM is not available for the requested review pass.")
        if self.gemini_available:
            return await self._gemini_completion_plain_text(
                messages,
                max_tokens=max_tokens,
                temperature=temperature,
                json_mode=json_mode,
                call_purpose=purpose,
            )
        return ""

    @staticmethod
    def _messages_to_gemini_text(messages: List[Dict[str, str]]) -> str:
        parts: List[str] = []
        for msg in messages or []:
            role = str(msg.get("role") or "user").strip().upper()
            content = str(msg.get("content") or "").strip()
            if content:
                # Loại bỏ chỉ dẫn /nothink đặc thù của Qwen3 đối với Gemini/Vertex
                if content.startswith("/nothink"):
                    content = content.replace("/nothink", "", 1).strip()
                parts.append(f"{role}:\n{content}")
        return "\n\n".join(parts).strip()

    async def _gemini_completion_plain_text(
        self,
        messages: List[Dict[str, str]],
        *,
        max_tokens: int,
        temperature: float,
        json_mode: bool = False,
        call_purpose: str | None = None,
        fallback_from: str | None = None,
    ) -> str:
        use_vertex = LLM_CONFIG.vertex_enabled and LLM_CONFIG.gcp_project_id
        if not use_vertex and not self.gemini_available:
            raise RuntimeError("Gemini fallback is not configured.")
        prompt_text = self._messages_to_gemini_text(messages)
        if not prompt_text:
            return ""
        
        headers: Dict[str, str] = {}
        if use_vertex:
            from services.vertex_auth import get_vertex_access_token
            token = get_vertex_access_token()
            if not token:
                raise RuntimeError("Vertex AI enabled but failed to obtain access token.")
            headers["Authorization"] = f"Bearer {token}"
            url = (
                f"https://{LLM_CONFIG.gcp_region}-aiplatform.googleapis.com/v1/"
                f"projects/{LLM_CONFIG.gcp_project_id}/locations/{LLM_CONFIG.gcp_region}/publishers/google/models/{self.gemini_model}:generateContent"
            )
        else:
            headers["x-goog-api-key"] = self.gemini_api_key
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{self.gemini_model}:generateContent"
            )
        timeout_cfg = httpx.Timeout(float(LLM_CONFIG.gemini_timeout_sec), connect=25.0)
        
        # Tăng giới hạn token cho dự phòng Gemini để ngăn chặn việc bị cắt cụt văn bản
        max_output_tokens = max(2048, int(max_tokens * 1.5))
        if json_mode:
            max_output_tokens = max(4096, max_output_tokens)

        payload: Dict[str, Any] = {
            "contents": [{
                "role": "user",
                "parts": [{"text": prompt_text}]
            }],
            "generationConfig": {
                "temperature": float(temperature),
                "topP": 0.92,
                "maxOutputTokens": max_output_tokens,
            },
        }
        if json_mode:
            payload["generationConfig"]["responseMimeType"] = "application/json"

        if use_vertex:
            payload["generationConfig"]["thinkingConfig"] = {
                "thinkingBudget": 0
            }
        purpose = call_purpose or infer_call_purpose()
        attempt_started = monotonic_start()
        try:
            async with httpx.AsyncClient(timeout=timeout_cfg) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
            record_llm_call(
                self, purpose=purpose, provider="vertex" if use_vertex else "gemini",
                model=self.gemini_model, started_at=attempt_started, status="success",
                max_tokens=max_tokens, json_mode=json_mode, fallback_from=fallback_from,
            )
        except Exception as error:
            record_llm_call(
                self, purpose=purpose, provider="vertex" if use_vertex else "gemini",
                model=self.gemini_model, started_at=attempt_started, status="error",
                max_tokens=max_tokens, json_mode=json_mode, error=error,
                fallback_from=fallback_from,
            )
            raise
        candidates = data.get("candidates") or []
        if not candidates:
            return ""
        content = (candidates[0] or {}).get("content") or {}
        text_chunks: List[str] = []
        for part in content.get("parts") or []:
            text = (part or {}).get("text")
            if text:
                text_chunks.append(str(text))
        return "\n".join(text_chunks).strip()
