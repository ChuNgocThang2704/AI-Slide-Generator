"""Cấu hình cho ứng dụng"""
import os
from pathlib import Path


def _load_env_file(path: Path) -> None:
    """Load KEY=VALUE entries into process env if not already set."""
    if not path.exists():
        return
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            raw = line.strip()
            if not raw or raw.startswith("#") or "=" not in raw:
                continue
            key, value = raw.split("=", 1)
            key = key.strip()
            if not key:
                continue
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                value = value[1:-1]
            os.environ.setdefault(key, value)
    except Exception:
        # Keep startup robust even with malformed .env content.
        pass

# Base directories
BASE_DIR = Path(__file__).parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
IMAGE_DIR = OUTPUT_DIR / "images"

# Load root/.env and backend/.env (if present) before reading config values.
_load_env_file(BASE_DIR / ".env")
_load_env_file(Path(__file__).resolve().parent / ".env")

# Tạo thư mục nếu chưa có
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
IMAGE_DIR.mkdir(exist_ok=True)

# Redis config
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
# true = mọi request generate đều đẩy qua Redis worker (nếu Redis + worker heartbeat).
# false = chỉ đẩy worker khi nội dung dài hơn REDIS_QUEUE_MIN_CHARS (hành vi cũ).
REDIS_OFFLOAD_WHEN_WORKER_ALIVE = os.getenv(
    "REDIS_OFFLOAD_WHEN_WORKER_ALIVE", "true"
).lower() in ("1", "true", "yes")
REDIS_QUEUE_MIN_CHARS = int(os.getenv("REDIS_QUEUE_MIN_CHARS", "10000"))

# LLM config — mặc định Qwen3-8B (vLLM: khớp --served-model-name, thường là Qwen3-8B).
# Nếu server không đặt served-model-name, dùng đúng repo HF: LLM_MODEL=Qwen/Qwen3-8B
LLM_MODEL = os.getenv("LLM_MODEL", "Qwen3-8B")
# vLLM (OpenAI-compatible). Bắt buộc cho extract slide (không còn Ollama local).
VLLM_API_BASE_URL = os.getenv("VLLM_API_BASE_URL", "http://45.83.205.200:46627")
# Structured output: guided_json (cần vLLM + backend outlines/lm-format-enforcer...). Lỗ HTTP 400 → client tự thử lại không guided.
VLLM_USE_GUIDED_JSON = os.getenv("VLLM_USE_GUIDED_JSON", "true").lower() in ("1", "true", "yes")
VLLM_GUIDED_DECODING_BACKEND = os.getenv("VLLM_GUIDED_DECODING_BACKEND", "outlines").strip() or "outlines"
# 8B nhanh hơn 14B; pipeline vẫn nhiều bước — nếu ReadTimeout thì tăng (vd. 450–600).
VLLM_TIMEOUT_SEC = float(os.getenv("VLLM_TIMEOUT_SEC", "300"))
# Nếu vLLM nằm sau reverse-proxy (vd Caddy) có Basic Auth thì set 2 env này.
# Ví dụ: VLLM_BASIC_AUTH_USER="admin" ; VLLM_BASIC_AUTH_PASS="xxxx"
VLLM_BASIC_AUTH_USER = os.getenv("VLLM_BASIC_AUTH_USER", "").strip()
VLLM_BASIC_AUTH_PASS = os.getenv("VLLM_BASIC_AUTH_PASS", "").strip()
# Hosted AI fallback for text/chart when vLLM is unavailable or errors.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite-preview").strip()
GEMINI_TIMEOUT_SEC = float(os.getenv("GEMINI_TIMEOUT_SEC", "120"))
# Ngữ cảnh / sampling (legacy tên biến; server vLLM có thể bỏ qua nếu không map vào API).
LLM_NUM_CTX = int(os.getenv("LLM_NUM_CTX", "8192"))
LLM_REPEAT_PENALTY = float(os.getenv("LLM_REPEAT_PENALTY", "1.08"))
# Gợi ý output JSON (client vẫn parse + guided_json trên vLLM khi bật).
LLM_USE_JSON_FORMAT = os.getenv("LLM_USE_JSON_FORMAT", "true").lower() in ("1", "true", "yes")
# FINAL SPEC:
# - Chunking khi nội dung dài để có summary tốt hơn.
# - Single-pass giới hạn thấp hơn để tránh prompt quá dài làm output bị cắt JSON.
LLM_CHUNK_THRESHOLD = int(os.getenv("LLM_CHUNK_THRESHOLD", "8000"))
LLM_SINGLE_PASS_CHAR_LIMIT = int(os.getenv("LLM_SINGLE_PASS_CHAR_LIMIT", "10000"))
# Đường ngắn (≤ LLM_CHUNK_THRESHOLD): bỏ bước summarize nếu true — tiết kiệm 1 gọi LLM, expand/group/dùng full text đã chuẩn hóa.
LLM_SHORT_PATH_SKIP_SUMMARIZE = os.getenv(
    "LLM_SHORT_PATH_SKIP_SUMMARIZE", "true"
).lower() in ("1", "true", "yes")
# true = ít slide hơn + output ngắn hơn → nhanh hơn (đổi lại kém chi tiết)
LLM_FAST_MODE = os.getenv("LLM_FAST_MODE", "false").lower() in ("1", "true", "yes")
# Quality mode: tăng độ đầy của bullet/slide (phù hợp khi chạy vLLM server mạnh).
LLM_QUALITY_MODE = os.getenv("LLM_QUALITY_MODE", "true").lower() in ("1", "true", "yes")
# FINAL_COMPOSE: compose thêm 1 lần để deck “thoải mái” và dày bullet hơn.
# Lưu ý: nếu vLLM server đang chạy max_model_len quá thấp thì có thể tăng timeout/JSON bị cắt.
LLM_FINAL_COMPOSE = os.getenv("LLM_FINAL_COMPOSE", "true").lower() in ("1", "true", "yes")
# Nếu true, đưa blueprint outline bắt buộc vào prompt compose (dễ cố định số slide).
# Mặc định false để AI tự phân bổ tự nhiên hơn theo các ý lớn.
LLM_FINAL_COMPOSE_ENFORCE_OUTLINE = os.getenv("LLM_FINAL_COMPOSE_ENFORCE_OUTLINE", "false").lower() in ("1", "true", "yes")

# FINAL SPEC: pipeline đã có final compose, không cần auto thêm lần nữa.
LLM_FINAL_COMPOSE_AUTO = os.getenv("LLM_FINAL_COMPOSE_AUTO", "false").lower() in ("1", "true", "yes")
LLM_FINAL_COMPOSE_AUTO_ONE_BULLET_RATIO = float(os.getenv("LLM_FINAL_COMPOSE_AUTO_ONE_BULLET_RATIO", "0.45"))
LLM_FINAL_COMPOSE_AUTO_AVG_BULLETS_BELOW = float(os.getenv("LLM_FINAL_COMPOSE_AUTO_AVG_BULLETS_BELOW", "3.2"))
# Timeout (giây) cho bước tóm từng chunk — 8B thường đủ; tăng nếu GPU tải cao / nội dung rất dài
LLM_CHUNK_TIMEOUT_SEC = float(os.getenv("LLM_CHUNK_TIMEOUT_SEC", "240"))
LLM_CHUNK_FAST_TIMEOUT_SEC = float(os.getenv("LLM_CHUNK_FAST_TIMEOUT_SEC", "200"))
LLM_SUBCHUNK_TIMEOUT_SEC = float(os.getenv("LLM_SUBCHUNK_TIMEOUT_SEC", "120"))
# Số chunk “map/summary” gọi LLM song song (khớp `--max-num-seqs` trên vLLM; Ollama thường 1). 1 = tuần tự.
LLM_CHUNK_PARALLEL = max(1, int(os.getenv("LLM_CHUNK_PARALLEL", "2")))
# Sau refine lần 1, nếu vẫn phát hiện bullet cụt → gọi refine thêm (lặp tối đa LLM_REFINE_MAX_EXTRA_PASSES).
LLM_REFINE_EXTRA_IF_TRUNCATED = os.getenv(
    "LLM_REFINE_EXTRA_IF_TRUNCATED", "true"
).lower() in ("1", "true", "yes")
LLM_REFINE_MAX_EXTRA_PASSES = int(os.getenv("LLM_REFINE_MAX_EXTRA_PASSES", "2"))
# Pass quality cao: polish bullet theo từng slide để giảm cụt nghĩa còn sót.
LLM_BULLET_POLISH_PASS = os.getenv("LLM_BULLET_POLISH_PASS", "true").lower() in ("1", "true", "yes")
# Cổng kiểm định cuối: chỉ sửa bullet chắc chắn lỗi (cụt/đuôi treo/quá ngắn không đủ nghĩa).
LLM_FINAL_QUALITY_GATE = os.getenv("LLM_FINAL_QUALITY_GATE", "true").lower() in ("1", "true", "yes")
# Giới hạn số bullet được sửa ở pass cuối để giữ thời gian ổn định.
LLM_FINAL_QUALITY_GATE_MAX_FIXES = int(os.getenv("LLM_FINAL_QUALITY_GATE_MAX_FIXES", "12"))
# Presentation style mode: bullet ngắn, keyword-first, và variation kiểu slide.
LLM_PRESENTATION_STYLE_MODE = os.getenv("LLM_PRESENTATION_STYLE_MODE", "false").lower() in ("1", "true", "yes")
# Density gate: ép mỗi slide đạt tối thiểu số bullet mong muốn ở bước cuối.
LLM_FINAL_DENSITY_GATE = os.getenv("LLM_FINAL_DENSITY_GATE", "true").lower() in ("1", "true", "yes")
LLM_FINAL_DENSITY_MIN_BULLETS = int(os.getenv("LLM_FINAL_DENSITY_MIN_BULLETS", "3"))
LLM_FINAL_DENSITY_MAX_REWRITES = int(os.getenv("LLM_FINAL_DENSITY_MAX_REWRITES", "10"))
# Luồng slide thống nhất trong code: sau merge/summary → expand → group → generate → refine
# (xem `ContentExtractor._expand_group_generate_refine_pipeline` trong content_extractor.py).

# Image generation (SDXL) — máy/host KHÁC với API tạo slide (FastAPI /generate).
# Chỉ set khi đã có service sinh ảnh (vd. scripts/sdxl_api_server.py trên GPU).
# Ví dụ map: ngoài :26229 -> trong :8080 thì URL đầy đủ là http://IP:26229 (không phải port API slide).
# Để trống = tắt ảnh. Mặc định trỏ server SDXL (đổi bằng env khi deploy khác).
IMAGE_GEN_API_BASE_URL = os.getenv(
    "IMAGE_GEN_API_BASE_URL", "http://104.188.118.187:49381"
).strip().rstrip("/")
IMAGE_GEN_API_KEY = os.getenv("IMAGE_GEN_API_KEY", "").strip()
IMAGE_GEN_TIMEOUT_SEC = float(os.getenv("IMAGE_GEN_TIMEOUT_SEC", "600"))

# Secondary AI image fallback — now uses Gemini Imagen (Together/FLUX had persistent rate limits).
# IMAGE_FALLBACK_MODEL: set to "imagen-4.0-generate-001" (default) or "imagen-4.0-fast-generate-001".
# IMAGE_FALLBACK_API_BASE_URL and IMAGE_FALLBACK_API_KEY are no longer used but kept for compatibility.
IMAGE_FALLBACK_API_BASE_URL = os.getenv(
    "IMAGE_FALLBACK_API_BASE_URL", ""
).strip().rstrip("/")
IMAGE_FALLBACK_API_KEY = os.getenv("IMAGE_FALLBACK_API_KEY", "").strip()
IMAGE_FALLBACK_TIMEOUT_SEC = float(os.getenv("IMAGE_FALLBACK_TIMEOUT_SEC", "60"))
IMAGE_FALLBACK_MODEL = os.getenv(
    "IMAGE_FALLBACK_MODEL", "imagen-4.0-generate-001"
).strip()
# Giới hạn số slide có ảnh (mỗi ảnh một gọi SDXL — có thể lâu).
IMAGE_MAX_SLIDES_WITH_IMAGES = int(os.getenv("IMAGE_MAX_SLIDES_WITH_IMAGES", "12"))

# Giới hạn Slide
FREE_SLIDE_LIMIT = int(os.getenv("FREE_SLIDE_LIMIT", "10"))
PRO_SLIDE_LIMIT_MAX = int(os.getenv("PRO_SLIDE_LIMIT_MAX", "30"))
ULTRA_SLIDE_LIMIT_MAX = int(os.getenv("ULTRA_SLIDE_LIMIT_MAX", "50"))

# Giới hạn số ảnh minh họa tối đa
FREE_IMAGE_LIMIT = int(os.getenv("FREE_IMAGE_LIMIT", "5"))
PRO_IMAGE_LIMIT_MAX = int(os.getenv("PRO_IMAGE_LIMIT_MAX", "15"))
ULTRA_IMAGE_LIMIT_MAX = int(os.getenv("ULTRA_IMAGE_LIMIT_MAX", "35"))

# Giới hạn ký tự đầu vào (được trích xuất từ text hoặc file)
FREE_CHAR_LIMIT = int(os.getenv("FREE_CHAR_LIMIT", "5000"))
PRO_CHAR_LIMIT = int(os.getenv("PRO_CHAR_LIMIT", "20000"))
ULTRA_CHAR_LIMIT = int(os.getenv("ULTRA_CHAR_LIMIT", "50000"))

# Số lượng luồng sinh ảnh song song đồng thời.
IMAGE_GEN_CONCURRENCY = int(os.getenv("IMAGE_GEN_CONCURRENCY", "3"))

# Negative: cấm chữ/diagram/infographic + style không phù hợp (cartoon/horror/isometric)
IMAGE_NEGATIVE_PROMPT = os.getenv(
    "IMAGE_NEGATIVE_PROMPT",
    "text, typography, letters, words, writing, caption, label, watermark, logo, signature, "
    "infographic, chart, graph, bar chart, pie chart, line chart, flowchart, flowchart boxes, "
    "diagram, decision tree, mindmap, UI, user interface, dashboard, "
    "screenshot, mockup, powerpoint, slide, slide layout, split panels, grid layout, "
    "whiteboard, chalkboard, blackboard, sign with text, poster with text, banner, billboard, "
    "sticky notes, notebook with writing, paper with text, screen showing text, document, "
    "cartoon, anime, isometric art, flat icon collage, logo collage, game art, "
    "monster, creature, zombie, horror, dark fantasy, robot, mecha, "
    "chaotic clutter, overwhelming mess, too many objects, "
    "blurry, low quality, distorted, ugly, bad anatomy, nsfw",
)

# Style khóa chung cả deck — dùng STOCK PHOTO để thoát prior infographic của SDXL.
IMAGE_STYLE_LOCKED = os.getenv(
    "IMAGE_STYLE_LOCKED",
    "professional stock photography, shallow depth of field, soft natural light, "
    "clean commercial look, sharp focus on subject, high quality",
)

# Hậu tố ngắn — chỉ cấm chữ/biển (không nhồi thêm style, tránh loãng token)
IMAGE_PROMPT_SUFFIX = os.getenv(
    "IMAGE_PROMPT_SUFFIX",
    ", no text, no signs, no screens with writing, no whiteboard, no diagrams",
)

IMAGE_MODEL_TYPE = os.getenv("IMAGE_MODEL_TYPE", "sdxl").strip().lower()  # "sdxl" or "flux"
# 1024² ổn với nhiều service SDXL; tăng từ 896×672 để ổn định layout khi cắt vào slide.
IMAGE_WIDTH = int(os.getenv("IMAGE_WIDTH", "1024"))
IMAGE_HEIGHT = int(os.getenv("IMAGE_HEIGHT", "1024"))
_IMAGE_DEFAULT_STEPS = "4" if IMAGE_MODEL_TYPE == "flux" else "35"
_IMAGE_DEFAULT_GUIDANCE = "0.0" if IMAGE_MODEL_TYPE == "flux" else "8.0"
IMAGE_STEPS = int(os.getenv("IMAGE_STEPS", _IMAGE_DEFAULT_STEPS))
# FLUX.1-schnell thường dùng guidance 0; SDXL realistic bám prompt tốt hơn với CFG cao hơn.
IMAGE_GUIDANCE_SCALE = float(os.getenv("IMAGE_GUIDANCE_SCALE", _IMAGE_DEFAULT_GUIDANCE))

# External image fallback. Wikimedia works without key; Pexels is optional.
STOCK_PHOTO_ENABLE = os.getenv("STOCK_PHOTO_ENABLE", "true").lower() in ("1", "true", "yes")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "").strip()

# Optional CLIP alignment validation (requires image server to expose /clip-score).
# When enabled, backend will reject generated images whose CLIP cosine score vs the
# final prompt is below the threshold, then retry alternate/simplified prompts.
IMAGE_CLIP_VALIDATE_ENABLE = os.getenv("IMAGE_CLIP_VALIDATE_ENABLE", "true").lower() in ("1", "true", "yes")
IMAGE_CLIP_MIN_SCORE = float(os.getenv("IMAGE_CLIP_MIN_SCORE", "0.22"))
IMAGE_CLIP_SCORE_TIMEOUT_SEC = float(os.getenv("IMAGE_CLIP_SCORE_TIMEOUT_SEC", "12"))

# Multimodal quality/fidelity judge (Gemini vision).
IMAGE_VLM_JUDGE_ENABLE = os.getenv("IMAGE_VLM_JUDGE_ENABLE", "true").lower() in ("1", "true", "yes")
# Default to GEMINI_MODEL so text/chart fallback and image judge stay aligned.
IMAGE_VLM_JUDGE_MODEL = os.getenv("IMAGE_VLM_JUDGE_MODEL", GEMINI_MODEL).strip()
IMAGE_VLM_JUDGE_MIN_RELEVANCE = float(os.getenv("IMAGE_VLM_JUDGE_MIN_RELEVANCE", "0.60"))
IMAGE_VLM_JUDGE_MAX_ARTIFACT = float(os.getenv("IMAGE_VLM_JUDGE_MAX_ARTIFACT", "0.45"))
IMAGE_VLM_JUDGE_MIN_STYLE = float(os.getenv("IMAGE_VLM_JUDGE_MIN_STYLE", "0.75"))
IMAGE_VLM_JUDGE_TIMEOUT_SEC = float(os.getenv("IMAGE_VLM_JUDGE_TIMEOUT_SEC", "25"))

# Lightweight image quality gate thresholds (tunable without code edits).
IMAGE_VALIDATION_MIN_ENTROPY = float(os.getenv("IMAGE_VALIDATION_MIN_ENTROPY", "2.2"))
IMAGE_VALIDATION_MIN_CONTRAST = float(os.getenv("IMAGE_VALIDATION_MIN_CONTRAST", "18.0"))
IMAGE_VALIDATION_MIN_EDGE_MEAN = float(os.getenv("IMAGE_VALIDATION_MIN_EDGE_MEAN", "6.0"))
IMAGE_VALIDATION_MIN_EDGE_STDDEV = float(os.getenv("IMAGE_VALIDATION_MIN_EDGE_STDDEV", "15.0"))
IMAGE_VALIDATION_MAX_NEAR_WHITE_RATIO = float(os.getenv("IMAGE_VALIDATION_MAX_NEAR_WHITE_RATIO", "0.82"))
IMAGE_VALIDATION_MAX_NEAR_BLACK_RATIO = float(os.getenv("IMAGE_VALIDATION_MAX_NEAR_BLACK_RATIO", "0.82"))
IMAGE_VALIDATION_MIN_SYMMETRY_ERROR = float(os.getenv("IMAGE_VALIDATION_MIN_SYMMETRY_ERROR", "7.0"))
IMAGE_VALIDATION_HUMAN_MIN_EDGE_MEAN = float(os.getenv("IMAGE_VALIDATION_HUMAN_MIN_EDGE_MEAN", "7.5"))

# Google Cloud Vertex AI Config
GCP_VERTEX_AI_ENABLE = os.getenv("GCP_VERTEX_AI_ENABLE", "false").lower() in ("1", "true", "yes")
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "").strip()
GCP_REGION = os.getenv("GCP_REGION", "us-central1").strip()
GCP_SERVICE_ACCOUNT_JSON_PATH = os.getenv("GCP_SERVICE_ACCOUNT_JSON_PATH", "service-account.json").strip()

# API config
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))

# File upload config
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = [".docx", ".pdf", ".txt"]
