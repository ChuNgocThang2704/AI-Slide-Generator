# LecGen AI Service

FastAPI service và Redis worker sinh/sửa deck JSON cho LecGen. Đây là API nội bộ dành cho Java Document Service; FE không gọi AI Service trực tiếp.

## Chức năng

- Đọc PDF, DOCX và TXT; hỗ trợ chọn phạm vi/chương bằng prompt đa ngôn ngữ.
- Tự nhận diện chế độ `lecture` và `presentation` nhưng vẫn ưu tiên yêu cầu của người dùng.
- Sinh title, bullets, speaker notes, layout và pedagogical metadata.
- Sinh bảng và biểu đồ editable từ dữ liệu có bằng chứng.
- Trích ảnh từ PDF, tìm stock hoặc sinh ảnh bằng FLUX.
- Duyệt ảnh bằng Qwen3-VL; Gemini/Vertex là fallback/review tùy cấu hình.
- Sửa deck bằng ngôn ngữ tự nhiên và giữ nguyên slide ngoài phạm vi.

## Provider

### vLLM chính

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

Cấu hình backend:

```env
LLM_MODEL=Qwen3-VL-8B
VLLM_API_BASE_URL=http://<vllm-host>:<port>
IMAGE_VLM_JUDGE_MODEL=Qwen3-VL-8B
```

Không thêm `/v1` vào `VLLM_API_BASE_URL`; client tự nối OpenAI-compatible path.

### FLUX image server

```bash
cd scripts
python flux_api_server.py
```

Biến môi trường khuyến nghị:

```env
FLUX_HOST=0.0.0.0
FLUX_PORT=8080
CLIP_DEVICE=cpu
```

`CLIP_DEVICE=cpu` tránh CLIP giữ VRAM làm request FLUX tiếp theo bị OOM. Server tự giới hạn prompt theo tokenizer để tránh vượt giới hạn 77 token của CLIP.

Backend kết nối bằng:

```env
IMAGE_MODEL_TYPE=flux
IMAGE_GEN_API_BASE_URL=http://<flux-host>:<port>
```

## Fallback

Nếu vLLM không sẵn sàng, service có thể dùng Gemini/Vertex khi credential hợp lệ. Các biến phụ thuộc chế độ được khai báo trong `backend/config.py`, gồm Gemini API key hoặc Google service account. Không commit credential và `.env`.

## Chạy bằng Docker

```bash
docker compose up -d --build api worker redis
docker compose logs -f worker
```

- API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`
- Redis nội bộ: `redis://redis:6379/0`

`api` và `worker` phải dùng cùng `.env`, Redis và volume `uploads/outputs`.

## Chạy trực tiếp

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

Khi cần Redis local, đặt `REDIS_URL=redis://localhost:6379/0`. Production nên luôn chạy Redis.

## API chính

### Tạo deck

```http
POST /api/generate-slide-spec
Content-Type: multipart/form-data
```

Field quan trọng: `text`, `file`, `plan`, `slide_count`, `image_limit`. Ảnh được bật mặc định nếu có ít nhất một image provider; client không cần gửi `generate_images=true`.

### Sửa deck

```http
POST /api/revise-slide-spec
Content-Type: multipart/form-data
```

Field bắt buộc: `source_task_id`, `revision_prompt`. Dùng `revision_scope=auto` cho prompt tự nhiên; `context_slide_number` chỉ là gợi ý. Chỉ dùng `slide_number`/`slide_index` khi một control chương trình cần khóa cứng target.

### Poll

```http
GET /api/status/{task_id}
```

Trạng thái: `pending`, `processing`, `completed`, `failed`/`error`, `cancelled`. Khi hoàn thành, deck nằm trong `result.deck`.

Contract đầy đủ: [api_specification.md](api_specification.md).

## Nguyên tắc output

- FE/BE thay toàn bộ deck sau revise, không merge delta.
- `slide_id` là định danh ổn định; `index` là thứ tự hiện tại.
- Bảng trả về `headers` và `rows` đầy đủ.
- Biểu đồ trả về labels/categories và values/series đầy đủ.
- Không tạo chart khi không có ít nhất hai điểm dữ liệu có bằng chứng.
- Không bịa thống kê/kết quả; dữ liệu mô phỏng chỉ được dùng khi prompt cho phép và phải gắn nhãn minh họa.
- Nếu visual thất bại, text không được nói rằng visual đó đang hiển thị.

## Giới hạn mặc định

| Plan | Slide | Ký tự | Ảnh | Tỷ lệ ảnh |
|---|---:|---:|---:|---:|
| Free | 10 | 10.000 | 5 | 40% |
| Pro | 30 | 50.000 | 15 | 60% |
| Ultra | 50 | 100.000 | 35 | 80% |

Revision quota (2/10/30 mỗi ngày) do Java Subscription Service quản lý, không phải AI Service.

## Test

```powershell
$env:PYTHONPATH="backend"
.venv\Scripts\python.exe -m pytest tests -q
```

Các test revise, visual grounding, lecture mode và image routing nằm trong `tests/`.
