"""
Chỉ dịch vụ SINH ẢNH (SDXL) — không phải API tạo slide PowerPoint (DemoDoan chạy host/port khác).

Copy lên máy GPU, rồi ví dụ:

  export HF_HOME=/path/to/cache   # tùy chọn
  export SDXL_PORT=8080           # khớp map container :8080 (vd. ngoài :26229 -> :8080)
  python sdxl_api_server.py

Hoặc: uvicorn sdxl_api_server:app --host 0.0.0.0 --port 8080

Backend slide (máy khác) gọi HTTP tới URL này qua IMAGE_GEN_API_BASE_URL — không trùng VLLM/slide API.

Giao diện web: mở http://HOST:PORT/ hoặc http://HOST:PORT/ui/

Test local (Windows, tránh proxy làm reset kết nối):
  curl.exe --noproxy "*" -sS http://127.0.0.1:8080/ping
  curl.exe --noproxy "*" -sS http://127.0.0.1:8080/health

Yêu cầu: torch + diffusers + transformers + accelerate + fastapi + uvicorn + pillow
Model mặc định: SG161222/RealVisXL_V5.0 (tải lần đầu, cần VRAM ~12GB+ fp16).
"""
import base64
import io
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

STATIC_DIR = Path(__file__).resolve().parent / "sdxl_static"

# Lazy load pipeline
_pipe = None
_clip_model = None
_clip_processor = None


def _clip_token_len(pipe, text: str) -> int:
    if not text:
        return 0
    lengths = []
    for name in ("tokenizer", "tokenizer_2"):
        tok = getattr(pipe, name, None)
        if tok is None:
            continue
        ids = tok(
            text,
            truncation=False,
            add_special_tokens=True,
            return_attention_mask=False,
        )["input_ids"]
        lengths.append(len(ids))
    return max(lengths) if lengths else len(text.split())


def _truncate_to_clip_budget(pipe, text: str, budget: int = 75) -> str:
    cleaned = " ".join((text or "").split()).strip()
    if not cleaned:
        return ""
    if _clip_token_len(pipe, cleaned) <= budget:
        return cleaned
    words = cleaned.split()
    lo, hi = 1, len(words)
    best = words[0]
    while lo <= hi:
        mid = (lo + hi) // 2
        candidate = " ".join(words[:mid]).strip(" ,.;")
        if _clip_token_len(pipe, candidate) <= budget:
            best = candidate
            lo = mid + 1
        else:
            hi = mid - 1
    return best


def get_pipe():
    global _pipe
    if _pipe is not None:
        return _pipe
    import torch
    from diffusers import FluxPipeline, StableDiffusionXLPipeline

    model_type = (os.getenv("IMAGE_MODEL_TYPE", "sdxl") or "sdxl").strip().lower()
    model_id = os.getenv("SDXL_MODEL_ID", "SG161222/RealVisXL_V5.0")

    if model_type == "flux":
        model_id = os.getenv("FLUX_MODEL_ID", "black-forest-labs/FLUX.1-schnell")
        dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
        _pipe = FluxPipeline.from_pretrained(model_id, torch_dtype=dtype)
    else:
        dtype = torch.float16 if torch.cuda.is_available() else torch.float32
        _pipe = StableDiffusionXLPipeline.from_pretrained(
            model_id,
            torch_dtype=dtype,
            variant="fp16" if dtype == torch.float16 else None,
        )

    if torch.cuda.is_available():
        _pipe = _pipe.to("cuda")
    return _pipe


def _get_clip():
    """Lazy-load CLIP model for image-text similarity scoring."""
    global _clip_model, _clip_processor
    if _clip_model is not None and _clip_processor is not None:
        return _clip_model, _clip_processor
    import torch
    from transformers import CLIPModel, CLIPProcessor

    model_id = os.getenv("CLIP_MODEL_ID", "openai/clip-vit-base-patch32").strip() or "openai/clip-vit-base-patch32"
    _clip_processor = CLIPProcessor.from_pretrained(model_id)
    _clip_model = CLIPModel.from_pretrained(model_id)
    if torch.cuda.is_available():
        _clip_model = _clip_model.to("cuda")
    _clip_model.eval()
    return _clip_model, _clip_processor


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warmup optional — bỏ qua để khởi động nhanh; load lần đầu gọi /generate
    yield
    global _pipe
    _pipe = None


app = FastAPI(title="SDXL API", lifespan=lifespan)


@app.get("/")
async def root():
    """Chuyển tới giao diện thử ảnh."""
    return RedirectResponse(url="/ui/")


@app.get("/ping")
async def ping():
    """Không import torch — dùng để kiểm tra HTTP/proxy (curl: thêm --noproxy '*')."""
    return {"ok": True, "service": "sdxl-api"}


class GenerateBody(BaseModel):
    prompt: str = Field(..., min_length=1)
    negative_prompt: str = ""
    width: int = Field(1024, ge=512, le=1536)
    height: int = Field(768, ge=512, le=1536)
    steps: int = Field(30, ge=1, le=80)
    guidance_scale: float = Field(7.0, ge=0.0, le=15.0)
    seed: Optional[int] = None
    return_base64: bool = False


class ClipScoreBody(BaseModel):
    """Compute CLIP similarity between an image and text."""
    text: str = Field(..., min_length=1)
    image_b64: str = Field(..., min_length=16)


@app.get("/health")
async def health():
    try:
        import torch
    except Exception as e:
        return {
            "ok": False,
            "cuda": False,
            "device": None,
            "torch_error": str(e),
        }
    try:
        return {
            "ok": True,
            "cuda": torch.cuda.is_available(),
            "device": (
                torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu"
            ),
        }
    except Exception as e:
        return {"ok": False, "cuda": False, "device": None, "error": str(e)}


@app.post("/generate")
async def generate(body: GenerateBody) -> Any:
    import torch

    pipe = get_pipe()
    model_type = (os.getenv("IMAGE_MODEL_TYPE", "sdxl") or "sdxl").strip().lower()
    gen = None
    if body.seed is not None:
        gen = torch.Generator(device=pipe.device)
        gen.manual_seed(int(body.seed))

    try:
        prompt = body.prompt
        negative_prompt = body.negative_prompt or ""
        if model_type == "sdxl":
            clipped_prompt = _truncate_to_clip_budget(pipe, prompt, budget=75)
            clipped_negative = _truncate_to_clip_budget(pipe, negative_prompt, budget=75)
            if clipped_prompt != prompt:
                print(
                    f"[sdxl_api] prompt clipped for CLIP budget: "
                    f"{_clip_token_len(pipe, prompt)} -> {_clip_token_len(pipe, clipped_prompt)}"
                )
            if clipped_negative != negative_prompt:
                print(
                    f"[sdxl_api] negative_prompt clipped for CLIP budget: "
                    f"{_clip_token_len(pipe, negative_prompt)} -> {_clip_token_len(pipe, clipped_negative)}"
                )
            prompt = clipped_prompt
            negative_prompt = clipped_negative

        steps = body.steps
        guidance_scale = body.guidance_scale
        if model_type == "flux":
            model_id = os.getenv("FLUX_MODEL_ID", "black-forest-labs/FLUX.1-schnell").lower()
            if "schnell" in model_id:
                steps = min(max(1, steps), 8)
                guidance_scale = 0.0

        kwargs = {
            "prompt": prompt,
            "width": body.width,
            "height": body.height,
            "num_inference_steps": steps,
            "guidance_scale": guidance_scale,
            "generator": gen,
        }
        # FluxPipeline does not support negative_prompt in common setups.
        if model_type != "flux":
            kwargs["negative_prompt"] = negative_prompt or None
        out = pipe(**kwargs)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    image = out.images[0]
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    raw = buf.getvalue()

    if body.return_base64:
        return {
            "format": "png",
            "image_b64": base64.b64encode(raw).decode("ascii"),
        }
    return Response(content=raw, media_type="image/png")


@app.post("/clip-score")
async def clip_score(body: ClipScoreBody) -> Any:
    """Return cosine similarity score between image and text (CLIP)."""
    import torch
    from PIL import Image

    text = (body.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is empty")
    try:
        raw = base64.b64decode(body.image_b64)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid base64 image")

    try:
        img = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception:
        raise HTTPException(status_code=400, detail="invalid image bytes")

    model, processor = _get_clip()
    inputs = processor(
        text=[text],
        images=[img],
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=77,
    )
    if torch.cuda.is_available():
        inputs = {k: v.to("cuda") for k, v in inputs.items()}
    with torch.no_grad():
        out = model(**inputs)
        img_emb = out.image_embeds
        txt_emb = out.text_embeds
        img_emb = img_emb / img_emb.norm(dim=-1, keepdim=True).clamp_min(1e-8)
        txt_emb = txt_emb / txt_emb.norm(dim=-1, keepdim=True).clamp_min(1e-8)
        score = float((img_emb * txt_emb).sum(dim=-1).mean().item())

    return {
        "ok": True,
        "model_id": os.getenv("CLIP_MODEL_ID", "openai/clip-vit-base-patch32"),
        "score": round(score, 6),
    }


if STATIC_DIR.is_dir():
    app.mount(
        "/ui",
        StaticFiles(directory=str(STATIC_DIR), html=True),
        name="ui",
    )


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("SDXL_HOST", "0.0.0.0")
    port = int(os.getenv("SDXL_PORT", "8080"))
    uvicorn.run(app, host=host, port=port)
