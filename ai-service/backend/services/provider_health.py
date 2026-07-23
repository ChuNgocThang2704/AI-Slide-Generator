from __future__ import annotations

import os
import time


_VLLM_UNAVAILABLE_UNTIL = 0.0
_VLLM_FAILURE_COOLDOWN_SEC = max(
    30.0,
    float(os.getenv("VLLM_FAILURE_COOLDOWN_SEC", "300")),
)


def mark_vllm_unavailable() -> None:
    global _VLLM_UNAVAILABLE_UNTIL
    _VLLM_UNAVAILABLE_UNTIL = max(
        _VLLM_UNAVAILABLE_UNTIL,
        time.monotonic() + _VLLM_FAILURE_COOLDOWN_SEC,
    )


def vllm_circuit_open() -> bool:
    return time.monotonic() < _VLLM_UNAVAILABLE_UNTIL

