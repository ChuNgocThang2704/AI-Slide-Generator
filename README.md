# LecGen

LecGen là hệ thống tạo, quản lý và chỉnh sửa bài giảng/bài thuyết trình bằng AI. Người dùng có thể nhập prompt, dùng lại tài liệu đã tải lên hoặc gửi PDF/DOCX/TXT; hệ thống trả về deck JSON để giao diện web render, chỉnh sửa và xuất PDF/PPTX.

## Kiến trúc hiện tại

```mermaid
flowchart LR
    FE[React + Vite] --> GW[Spring Cloud Gateway :8080]
    GW --> USER[User Service :8081]
    GW --> DOC[Document Service :8082]
    GW --> TEMPLATE[Template Service :8083]
    GW --> SUB[Subscription Service :8084]
    GW --> PAY[Payment Service :8085]
    GW --> STAT[Statistic Service :8086]
    DOC --> AI[FastAPI AI Service :8000]
    AI --> REDIS[(Redis Queue)]
    REDIS --> WORKER[AI Worker]
    WORKER --> VLLM[Qwen3-VL-8B qua vLLM]
    WORKER --> FLUX[FLUX image server]
    WORKER --> STOCK[Pexels/stock fallback]
    WORKER --> GEMINI[Gemini/Vertex fallback]
```

- FE chỉ gọi Java BE qua API Gateway, không gọi AI Service trực tiếp.
- Document Service lưu project, slide pages và điều phối task AI.
- AI Service sinh deck JSON, bảng, biểu đồ, ảnh và speaker notes. FE chịu trách nhiệm render, editor và export.
- Qwen3-VL là provider chính; Gemini/Vertex là fallback và lớp review khi được cấu hình.
- FLUX sinh ảnh tổng quát; ảnh stock hoặc ảnh trong tài liệu được ưu tiên khi cần tính xác thực.
- Redis Queue tách API khỏi các tác vụ AI chạy lâu.

## Thư mục

```text
back-end/       Java microservices
front-end/      React/Vite application
ai-service/     FastAPI, worker và AI pipeline
docker/         Khởi tạo database
docker-compose.yml
fe_api_spec.md  Contract FE -> Java BE (nguồn chuẩn)
ai-service/api_specification.md  Contract Java BE -> AI Service
```

## Chạy local

### 1. Java backend và hạ tầng

Tạo `.env` ở thư mục gốc, sau đó chạy:

```bash
docker compose up -d --build
```

Gateway: `http://localhost:8080`.

### 2. AI Service

Tạo `ai-service/.env` và `ai-service/backend/.env` theo môi trường. Các biến quan trọng:

```env
REDIS_URL=redis://redis:6379/0
LLM_MODEL=Qwen3-VL-8B
VLLM_API_BASE_URL=http://<vllm-host>:<port>
IMAGE_GEN_API_BASE_URL=http://<flux-host>:<port>
```

```bash
cd ai-service
docker compose up -d --build api worker redis
```

AI Swagger: `http://localhost:8000/docs`.

### 3. Frontend

```bash
cd front-end
npm ci
npm run dev -- --host 0.0.0.0 --port 5173
```

Mặc định FE dùng hostname hiện tại và gateway port `8080`. Chỉ đặt `VITE_API_BASE_URL` khi Gateway nằm ở URL khác.

## Luồng tạo slide

1. FE upload tài liệu nếu có.
2. FE gọi `POST /api/document/projects` với prompt và metadata file.
3. FE poll `GET /api/document/projects/{projectId}/progress`.
4. Khi `projectStatus=1` và `aiStatus=completed`, FE lấy `/pages` và render deck.
5. FE autosave thay đổi thủ công qua API `pages/sync`.
6. FE xuất PDF hoặc PPTX từ editor. PPTX editable dùng các object PowerPoint; chi tiết trang trí phức tạp có thể được flatten để giữ hình thức.

## Luồng sửa bằng AI

1. FE gọi `POST /api/document/projects/{projectId}/revise`.
2. Gửi `revisionScope="auto"`; `contextSlideNumber` chỉ là slide đang mở, không khóa target.
3. AI tự hiểu cần sửa một slide, nhiều slide, thêm/xóa slide hay toàn bộ deck.
4. FE poll progress, sau đó tải lại toàn bộ `/pages` thay vì merge delta.
5. Nếu revise thất bại, BE khôi phục `aiTaskId` của deck thành công gần nhất để người dùng có thể sửa tiếp.

## Chất lượng và an toàn dữ liệu

- Table/chart chỉ được trả về khi schema đầy đủ và dữ liệu có bằng chứng.
- Nếu chart bị loại, nội dung không còn nhắc tới một biểu đồ không tồn tại.
- Pipeline không được tự bịa thống kê, tỷ lệ, ngày tháng, nghiên cứu hoặc kết quả đo lường.
- Slide ngoài phạm vi revise được giữ nguyên theo `slide_id`.
- Tài liệu nguồn có thể được dùng lại từ trang Tài liệu, không cần upload lại.

## Gói và giới hạn AI

Giá trị mặc định trong AI Service, có thể thay đổi bằng environment:

| Plan | Slide tối đa | Ký tự tối đa | Ảnh tối đa | Tỷ lệ slide có ảnh |
|---|---:|---:|---:|---:|
| Free | 10 | 10.000 | 5 | 40% |
| Pro | 30 | 50.000 | 15 | 60% |
| Ultra | 50 | 100.000 | 35 | 80% |

Quota nghiệp vụ và quyền plan do Java Subscription Service xác định từ tài khoản đăng nhập; FE không được tự gửi plan.

## Tài liệu tích hợp

- [README_FE_API.md](README_FE_API.md): checklist nhanh cho FE.
- [fe_api_spec.md](fe_api_spec.md): contract FE -> Java BE.
- [ai-service/api_specification.md](ai-service/api_specification.md): contract Java BE -> AI Service.
- [back-end/document-service/document_api_spec.md](back-end/document-service/document_api_spec.md): chi tiết Document Service.
- [ai-service/README.md](ai-service/README.md): vận hành AI/vLLM/FLUX.
