# Hệ thống tạo và quản lý slide tự động sử dụng AI

Hệ thống web cho phép người dùng nhập text, upload file (docx, pdf) và tự động tạo slide PowerPoint với ảnh minh họa được sinh bởi AI.

## Tính năng Core

- ✅ Upload file (docx, pdf, txt) hoặc nhập text trực tiếp
- ✅ Trích xuất và cấu trúc hóa nội dung sử dụng LLM (Ollama/Qwen)
- ✅ Tạo slide PowerPoint (PPTX) tự động
- ✅ Sinh ảnh minh họa cho slide sử dụng SDXL/FLUX
- ✅ Xem và tải slide đã tạo
- ✅ Xử lý bất đồng bộ với Redis queue

## Công nghệ

### Backend
- **FastAPI**: Framework web API
- **Python**: Ngôn ngữ lập trình
- **Ollama**: LLM để trích xuất nội dung (Qwen, Llama, etc.)
- **Diffusers**: Sinh ảnh với SDXL hoặc FLUX
- **Redis**: Queue bất đồng bộ
- **python-pptx**: Tạo file PowerPoint
- **python-docx, pdfplumber**: Xử lý file input

### Frontend
- **TypeScript + Node.js**: (Sẽ được triển khai)

## Cài đặt

### Yêu cầu
- Python 3.9+
- **Core dependencies** (bắt buộc): FastAPI, python-docx, pdfplumber, python-pptx
- **AI dependencies** (tùy chọn):
  - Ollama với model Qwen hoặc model LLM khác (cho trích xuất nội dung tốt hơn)
  - Diffusers + Torch (cho sinh ảnh, cần GPU để chạy nhanh)
- Redis (optional, có thể chạy không có Redis)

### Bước 1: Cài đặt Python dependencies

**Cài đặt cơ bản (bắt buộc):**
```bash
pip install -r requirements.txt
```

**Cài đặt AI features (tùy chọn):**
```bash
# Nếu muốn dùng LLM và Image Generation
pip install -r requirements-ai.txt

# Hoặc cài từng phần:
# - Chỉ Image Generation (cần GPU khuyến nghị):
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu  # CPU
pip install diffusers transformers accelerate safetensors
```

**Lưu ý**: Hệ thống có thể chạy được ngay chỉ với dependencies cơ bản. AI features sẽ tự động dùng fallback mode nếu không có.

### Bước 2: Cấu hình LLM (vLLM cloud)

Slide text dùng API OpenAI-compatible (`httpx` đã có trong `requirements.txt`). Đặt endpoint server vLLM:

```bash
set VLLM_API_BASE_URL=https://your-vllm-host:port   # gốc HTTP(S), không thêm /v1 (app tự nối /v1/...)
set LLM_MODEL=Qwen3-8B   # trùng --served-model-name trên vLLM
```

Nếu proxy có Basic Auth: `VLLM_BASIC_AUTH_USER`, `VLLM_BASIC_AUTH_PASS`.

### Bước 3: Cài đặt Redis (optional)

```bash
# Windows: Download từ https://redis.io/download
# Hoặc sử dụng Docker:
docker run -d -p 6379:6379 redis:latest
```

### Bước 4: Cấu hình model sinh ảnh (optional)

Model SDXL sẽ tự động download khi chạy lần đầu. Nếu muốn dùng FLUX:

```python
# Trong config.py hoặc environment variable
IMAGE_MODEL_TYPE = "flux"
```

## Chạy ứng dụng

### 1. Chạy API server

```bash
cd backend
python main.py
```

Hoặc:

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

API sẽ chạy tại: `http://localhost:8000`

### 2. Chạy worker (để xử lý queue bất đồng bộ)

```bash
cd backend
python worker.py
```

### 3. Xem API documentation

Truy cập: `http://localhost:8000/docs` (Swagger UI)

## API Endpoints

### 1. Upload text
```
POST /api/upload-text
Form data: text=<nội dung>
```

### 2. Upload file
```
POST /api/upload-file
Form data: file=<file>
```

### 3. Trích xuất nội dung
```
POST /api/extract-content
Form data: task_id=<task_id>
```

### 4. Tạo slide
```
POST /api/generate-slide
Form data: 
  - task_id=<task_id>
  - content=<nội dung đã cấu trúc> (optional)
  - plan=free/pro
  - slide_count=<number> (pro only)
  - image_limit=<max images> (pro only)
  - generate_images=true/false
```

### 5. API tổng hợp (khuyến nghị)
```
POST /api/generate-slide-full
Form data:
  - text=<nội dung> (optional)
  - file=<file> (optional)
  - plan=free/pro
  - slide_count=<number> (pro only)
  - image_limit=<max images> (pro only)
  - generate_images=true/false
```

### 6. Xem slide
```
GET /api/view-slide/{task_id}
```

### 7. Kiểm tra trạng thái
```
GET /api/status/{task_id}
```

## Cấu trúc dự án

```
DemoDoan/
├── backend/
│   ├── main.py              # FastAPI app
│   ├── worker.py            # Worker xử lý queue
│   ├── config.py            # Cấu hình
│   └── services/
│       ├── file_processor.py    # Xử lý file input
│       ├── content_extractor.py # Trích xuất nội dung với LLM
│       ├── slide_generator.py   # Tạo slide PPTX
│       ├── image_generator.py   # Sinh ảnh
│       └── redis_queue.py       # Quản lý queue
├── frontend/                # (Sẽ được triển khai)
├── uploads/                 # Thư mục lưu file upload
├── outputs/                 # Thư mục lưu slide và ảnh
├── requirements.txt
└── README.md
```

## Lưu ý

1. **Model sinh ảnh**: SDXL/FLUX cần GPU để chạy nhanh. Nếu không có GPU, có thể bỏ qua phần sinh ảnh (set `generate_images=false`).

   Giới hạn ảnh: `FREE_IMAGE_LIMIT` mặc định 5 ảnh cho gói Free; `PRO_IMAGE_LIMIT_MAX` mặc định 20 ảnh cho gói Pro. Backend vẫn clamp theo `IMAGE_MAX_SLIDES_WITH_IMAGES`.

2. **Ollama**: Đảm bảo Ollama đang chạy và đã pull model trước khi sử dụng.

3. **Redis**: Không bắt buộc. Nếu không có Redis, hệ thống sẽ dùng in-memory queue (không persist).

4. **File size**: Mặc định giới hạn 10MB cho file upload.

## Chạy 2 server (Backend + Image Server)

Phần này giúp bạn dễ đổi sang IP máy GPU khác khi triển khai.

### 1) Chạy backend tạo slide (máy API)

```bash
cd backend
python main.py
```

Backend mặc định chạy ở `http://localhost:8000`.

### 2) Chạy worker queue (máy API)

```bash
cd backend
python worker.py
```

Worker xử lý tác vụ dài: trích xuất nội dung, sinh chart/image, tạo PPTX.

### 3) Chạy image server SDXL/FLUX (máy GPU)

```bash
cd scripts
python sdxl_api_server.py
```

Hoặc chỉ định host/port:

Windows:

```bash
set SDXL_HOST=0.0.0.0
set SDXL_PORT=8080
python sdxl_api_server.py
```

Linux/macOS:

```bash
export SDXL_HOST=0.0.0.0
export SDXL_PORT=8080
python sdxl_api_server.py
```

### 4) Deploy image server lên máy GPU bằng SCP (khuyến nghị)

Nếu server sinh ảnh chạy ở máy GPU từ xa (không chạy local), copy thư mục `scripts` lên máy đó:

Windows PowerShell:

```bash
scp -r .\scripts <GPU_USER>@<GPU_SERVER_IP>:/home/<GPU_USER>/DemoDoan/
```

Linux/macOS:

```bash
scp -r ./scripts <GPU_USER>@<GPU_SERVER_IP>:/home/<GPU_USER>/DemoDoan/
```

Đăng nhập máy GPU và chạy server:

```bash
ssh <GPU_USER>@<GPU_SERVER_IP>
cd /home/<GPU_USER>/DemoDoan/scripts
export SDXL_HOST=0.0.0.0
export SDXL_PORT=8080
python sdxl_api_server.py
```

Nếu dùng `screen` để chạy nền:

```bash
screen -S sdxl
cd /home/<GPU_USER>/DemoDoan/scripts
python sdxl_api_server.py
# Ctrl+A, D để detach
```

### 5) Cấu hình backend gọi image server qua IP khác

Đặt biến môi trường ở máy backend:

```bash
set IMAGE_GEN_API_BASE_URL=http://<GPU_SERVER_IP>:8080
set IMAGE_MODEL_TYPE=sdxl
```

Ví dụ:

```bash
set IMAGE_GEN_API_BASE_URL=http://127.0.0.1:8080
set IMAGE_MODEL_TYPE=sdxl
```

Sau khi đổi IP/port, restart `main.py` và `worker.py`.

### 6) Kiểm tra image server trước khi gọi từ backend

```bash
curl http://<GPU_SERVER_IP>:8080/ping
curl http://<GPU_SERVER_IP>:8080/health
```

Windows (tránh proxy):

```bash
curl.exe --noproxy "*" http://<GPU_SERVER_IP>:8080/ping
curl.exe --noproxy "*" http://<GPU_SERVER_IP>:8080/health
```

### 7) Trình tự chạy khuyến nghị

1. Máy GPU: chạy `scripts/sdxl_api_server.py`.
2. Máy backend: set `IMAGE_GEN_API_BASE_URL`.
3. Chạy `backend/main.py`.
4. Chạy `backend/worker.py`.
5. Gọi API với `generate_images=true`.

## Phát triển tiếp

Các chức năng quản lý web sẽ được triển khai sau:
- Quản lý người dùng
- Quản lý tài liệu và slide
- Chức năng dùng thử
- Thanh toán trả phí

## License

MIT

vllm serve Qwen/Qwen3-8B \
  --host 0.0.0.0 \
  --port 8000 \
  --dtype auto \
  --gpu-memory-utilization 0.92 \
  --max-model-len 8192 \
  --max-num-seqs 6 \
  --served-model-name Qwen3-8B
