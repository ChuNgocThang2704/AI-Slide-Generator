"""LLM provider helpers for content extraction."""

from __future__ import annotations

from typing import Any, Dict, List

# pyrefly: ignore [missing-import]
import httpx

from config import (
    GEMINI_TIMEOUT_SEC,
    VLLM_TIMEOUT_SEC,
    GCP_VERTEX_AI_ENABLE,
    GCP_PROJECT_ID,
    GCP_REGION,
)


class LLMClientMixin:
    """Provider calls shared by the extraction pipeline.

    The owning class must define:
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
    ) -> str:
        """Run one chat completion and return plain text."""
        model_name = self.model_name
        if self.vllm_available:
            nothink_msgs = list(messages)
            if "qwen3" in (model_name or "").lower() and nothink_msgs:
                first = dict(nothink_msgs[0])
                if first.get("role") == "system":
                    content = first.get("content", "")
                    if not content.startswith("/nothink"):
                        first["content"] = "/nothink\n" + content
                    nothink_msgs[0] = first

            def _strip_think(text: str) -> str:
                text = text.strip()
                while "<think>" in text and "</think>" in text:
                    start = text.find("<think>")
                    end = text.find("</think>") + len("</think>")
                    text = (text[:start] + text[end:]).strip()
                return text

            timeout_cfg = httpx.Timeout(min(120.0, float(VLLM_TIMEOUT_SEC)), connect=25.0)
            payload: Dict[str, Any] = {
                "model": model_name,
                "messages": nothink_msgs,
                "temperature": float(temperature),
                "top_p": 0.92,
                "max_tokens": int(max_tokens),
            }
            try:
                async with httpx.AsyncClient(timeout=timeout_cfg) as client:
                    resp = await client.post(
                        f"{self.vllm_base_url}/v1/chat/completions",
                        json=payload,
                        auth=self.vllm_basic_auth,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                text = (data.get("choices", [{}])[0].get("message") or {}).get("content", "") or ""
                return _strip_think(text)
            except Exception as e:
                is_connection_error = isinstance(e, httpx.RequestError) or "connection" in str(e).lower() or "timeout" in str(e).lower()
                if is_connection_error:
                    print(f"[LLMClient] vLLM connection failed: {e}. Disabling vLLM for this session.")
                    self.vllm_available = False
                
                # Fallback to Gemini if available
                if self.gemini_available:
                    print("Falling back to Gemini plain text completion.")
                    return await self._gemini_completion_plain_text(
                        messages,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        json_mode=json_mode,
                    )
                raise

        if self.gemini_available:
            return await self._gemini_completion_plain_text(
                messages,
                max_tokens=max_tokens,
                temperature=temperature,
                json_mode=json_mode,
            )
        return ""

    @staticmethod
    def _messages_to_gemini_text(messages: List[Dict[str, str]]) -> str:
        parts: List[str] = []
        for msg in messages or []:
            role = str(msg.get("role") or "user").strip().upper()
            content = str(msg.get("content") or "").strip()
            if content:
                # Strip Qwen3-specific /nothink instruction for Gemini/Vertex
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
    ) -> str:
        use_vertex = GCP_VERTEX_AI_ENABLE and GCP_PROJECT_ID
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
                f"https://{GCP_REGION}-aiplatform.googleapis.com/v1/"
                f"projects/{GCP_PROJECT_ID}/locations/{GCP_REGION}/publishers/google/models/{self.gemini_model}:generateContent"
            )
        else:
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{self.gemini_model}:generateContent?key={self.gemini_api_key}"
            )
        timeout_cfg = httpx.Timeout(float(GEMINI_TIMEOUT_SEC), connect=25.0)
        
        # Increase token limits for Gemini fallback to prevent truncation
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
        async with httpx.AsyncClient(timeout=timeout_cfg) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
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
