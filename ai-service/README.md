# LecGen AI Service

FastAPI service va Redis worker sinh/sua deck JSON cho LecGen. Service nay khong phai API truc tiep cho FE; Java Document Service la client chinh.

## Chuc nang

- Doc PDF, DOCX va TXT; ho tro chon pham vi/chapter bang prompt da ngon ngu.
- Tu nhan dien `lecture` va `presentation` nhung van ton trong yeu cau nguoi dung.
- Sinh title, bullets, speaker notes, layout va pedagogical metadata.
- Sinh bang va bieu do editable tu du lieu co bang chung.
- Trich anh tu PDF, tim stock hoac sinh anh bang FLUX.
- Duyet anh bang Qwen3-VL; Gemini/Vertex la fallback/review tuy cau hinh.
- Sua deck bang ngon ngu tu nhien, giu nguyen slide ngoai pham vi.

## Provider

### vLLM chinh

```bash
vllm serve Qwen/Qwen3-VL-8B-Instruct \
  --host 0.0.0.0 \
  --port 8000 \
  --dtype auto \
  --gpu-memory-utilization 0.90 \
  --max-model-len 16384 \
  --served-model-name Qwen3-VL-8B \
  --enable-prefix-caching \
  --limit-mm-per-prompt '{"image":1}'
```

Backend config:

```env
LLM_MODEL=Qwen3-VL-8B
VLLM_API_BASE_URL=http://<vllm-host>:<port>
IMAGE_VLM_JUDGE_MODEL=Qwen3-VL-8B
```

Khong them `/v1` vao `VLLM_API_BASE_URL`; client tu noi OpenAI-compatible path.

### FLUX image server

```bash
cd scripts
python flux_api_server.py
```

Bien moi truong khuyen nghi:

```env
FLUX_HOST=0.0.0.0
FLUX_PORT=8080
CLIP_DEVICE=cpu
```

`CLIP_DEVICE=cpu` tranh CLIP giu VRAM lam request FLUX tiep theo OOM. Server tu gioi han prompt theo tokenizer de tranh vuot 77 token CLIP.

Backend ket noi bang:

```env
IMAGE_MODEL_TYPE=flux
IMAGE_GEN_API_BASE_URL=http://<flux-host>:<port>
```

## Cau hinh fallback

Neu vLLM khong san sang, service co the dung Gemini/Vertex khi credential hop le. Cac bien phu thuoc che do dang cau hinh trong `backend/config.py`, gom Gemini API key hoac Google service account. Khong commit credential va `.env`.

## Chay bang Docker

```bash
docker compose up -d --build api worker redis
docker compose logs -f worker
```

Services:

- API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`
- Redis noi bo: `redis://redis:6379/0`

`api` va `worker` phai dung cung `.env`, Redis va volume `uploads/outputs`.

## Chay truc tiep

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt
```

Windows PowerShell:

```powershell
$env:PYTHONPATH="backend"
.venv\Scripts\python.exe backend\main.py
.venv\Scripts\python.exe backend\worker.py
```

Can Redis thi dat `REDIS_URL=redis://localhost:6379/0`. Khi Redis khong kha dung, hanh vi fallback phu thuoc cau hinh queue hien tai; production nen luon chay Redis.

## API chinh

### Tao deck

```http
POST /api/generate-slide-spec
Content-Type: multipart/form-data
```

Field quan trong: `text`, `file`, `plan`, `slide_count`, `image_limit`. Anh duoc bat mac dinh neu co it nhat mot image provider; client khong can gui `generate_images=true`.

### Sua deck

```http
POST /api/revise-slide-spec
Content-Type: multipart/form-data
```

Field bat buoc: `source_task_id`, `revision_prompt`. De `revision_scope=auto` cho o prompt tu nhien; `context_slide_number` chi la goi y. Chi dung `slide_number`/`slide_index` khi mot control chuong trinh muon khoa cung target.

### Poll

```http
GET /api/status/{task_id}
```

Trang thai: `pending`, `processing`, `completed`, `failed`/`error`, `cancelled`. Khi completed, deck nam trong `result.deck`.

Contract day du: [api_specification.md](api_specification.md).

## Nguyen tac output

- FE/BE thay toan bo deck sau revise, khong merge delta.
- `slide_id` la dinh danh on dinh; `index` la thu tu hien tai.
- Bang tra ve `headers` va `rows` day du.
- Bieu do tra ve labels/categories va values/series day du.
- Khong tao chart khi khong co it nhat hai diem du lieu co bang chung.
- Khong bia thong ke/ket qua; du lieu mo phong chi duoc dung khi prompt cho phep va phai gan nhan minh hoa.
- Neu visual that bai, text khong duoc noi rang visual do dang hien thi.

## Gioi han mac dinh

| Plan | Slide | Ky tu | Anh | Ti le anh |
|---|---:|---:|---:|---:|
| Free | 10 | 10,000 | 5 | 40% |
| Pro | 30 | 50,000 | 15 | 60% |
| Ultra | 50 | 100,000 | 35 | 80% |

Revision quota (2/10/30 moi ngay) do Java Subscription Service quan ly, khong phai AI Service.

## Test

```powershell
$env:PYTHONPATH="backend"
.venv\Scripts\python.exe -m pytest tests -q
```

Test lien quan revise, visual grounding, lecture mode va image routing nam trong `tests/`.
