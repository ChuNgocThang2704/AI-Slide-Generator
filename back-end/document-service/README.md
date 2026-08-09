# Document Service - Project Orchestrator & Document Processor (Quản lý & Điều phối Sinh Slide)

## 1. Giới thiệu
Document Service là dịch vụ hạt nhân điều phối nghiệp vụ tạo slide bằng AI. Nó quản lý project, tài liệu nguồn, slide pages và task AI; gọi bất đồng bộ sang Python AI Service để nhận deck JSON. Frontend render, chỉnh sửa và xuất PDF/PPTX từ dữ liệu này.

---

## 2. Công nghệ Sử dụng
- **Framework**: Java 21, Spring Boot 3.x, Spring Web.
- **Giao tiếp nội bộ**: **Spring Cloud OpenFeign** (gọi dịch vụ `subscription-service` để kiểm tra và trừ quota), RestTemplate (gọi API của `ai-service`).
- **Cơ sở dữ liệu**: **MySQL** (`document_service_db`).
- **Lưu trữ tập tin**: AWS SDK for Java (S3 / MinIO Integration) dùng để lưu tài liệu nguồn và media liên quan.
- **Hàng đợi thông điệp**: RabbitMQ (báo sự kiện tạo slide hoàn thành).

---

## 3. Các Tính năng Chính & Luồng Nghiệp vụ

### 3.1. Quản lý Dự án & Tài liệu tải lên
- Hỗ trợ tải lên file gốc của người dùng lên Object Storage (S3/MinIO).
- Lưu trữ siêu dữ liệu (metadata) của tài liệu và cấu trúc của từng trang slide chi tiết dưới MySQL.

### 3.2. Điều phối tiến trình AI
Dịch vụ điều phối quy trình sinh slide qua các bước:
1. **Khởi tạo**: Gửi yêu cầu phân tích tài liệu tới `/api/generate-slide-spec` của FastAPI `ai-service` bằng liên kết file S3. Nhận về mã tác vụ `ai_task_id`.
2. **Sinh deck JSON**: Worker trích xuất nội dung, sinh text/notes, bảng, biểu đồ và ảnh rồi trả spec hoàn chỉnh.
3. **Đồng bộ**: Client poll `/progress`; khi hoàn thành, Document Service lưu `slide_pages` để FE render và autosave chỉnh sửa thủ công.
4. **AI revise**: `/projects/{id}/revise` gửi prompt tự nhiên cùng task thành công gần nhất. AI tự xác định phạm vi; FE poll rồi tải lại `/pages`.
5. **Khôi phục an toàn**: Nếu revise thất bại, project giữ lại `aiTaskId` của deck thành công trước đó và hoàn revision quota.
6. **Xuất file**: FE sở hữu renderer/export PDF và PPTX editable; Document Service lưu dữ liệu trang làm nguồn đồng bộ.

---

## 4. Cấu trúc Bảng Cơ sở dữ liệu (MySQL)

- **`source_documents`**: Lưu trữ tài liệu gốc (id, user_id, file_name, file_type, file_size, url, các cột audit).
- **`projects`**: Lưu trữ dự án (id, name, owner_id, source_doc_id, template_id, initial_prompt, slide_url, status, ai_task_id, các cột audit).
- **`slide_pages`**: Nội dung slide chi tiết (id, project_id, page_index, title, bullets, notes, chart, table_data, rich_text, elements, image_url, layout, primary_visual, likely_multi_pptx_slides, các cột audit).
- **`ai_task_logs`**: Lịch sử chạy tác vụ AI (id, project_id, task_type, status, error_message, started_at, completed_at, các cột audit).
- **`project_exports`**: Lịch sử xuất bản slide ra file cứng (id, project_id, export_type, s3_url, các cột audit).

---

## 5. Cấu hình & Biến Môi trường

Các cấu hình chính được định nghĩa trong file `application.yml`. Hãy khai báo các biến này trong file `.env` gốc mà không viết cứng giá trị bí mật:

```yaml
server:
  port: ${DOCUMENT_SERVICE_PORT} # Cổng chạy (Mặc định: 8082)
  servlet:
    context-path: /api/document

spring:
  servlet:
    multipart:
      max-file-size: 50MB
      max-request-size: 50MB
  datasource:
    url: ${DOC_DB_URL}         # jdbc:mysql://<host>:<port>/document_service_db
    username: ${DOC_DB_USERNAME}
    password: ${DOC_DB_PASSWORD}
  data:
    redis:
      url: ${REDIS_URL}
  rabbitmq:
    host: ${RABBIT_HOST}
    port: ${RABBIT_PORT}
    username: ${RABBIT_USER}
    password: ${RABBIT_PASS}
    virtual-host: ${RABBIT_VHOST}
    ssl:
      enabled: ${RABBIT_SSL_ENABLED}

jwt:
  signerKey: ${JWT_SIGNER_KEY}

app:
  rabbitmq:
    queue: ${RABBIT_QUEUE}
  ai:
    url: ${AI_URL} # Địa chỉ API của Python FastAPI AI Service
  subscription-service:
    url: ${APP_SUBSCRIPTION_SERVICE_URL} # Địa chỉ API nội bộ của Subscription Service

aws:
  access-key: ${AWS_ACCESS_KEY}
  secret-key: ${AWS_SECRET_KEY}
  region: ${AWS_REGION}
  s3:
    bucket: ${AWS_S3_BUCKET}
```

---

## 6. Danh sách API Endpoints

| Phương thức | Đường dẫn API | Xác thực JWT | Mô tả |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/document/projects` | Có | Tải file tài liệu, chọn mẫu slide và khởi chạy sinh dàn bài bằng AI |
| `GET` | `/api/document/projects/{id}/progress` | Có | Lấy tiến độ xử lý và nhật ký chạy tác vụ AI |
| `GET` | `/api/document/projects/{id}/pages` | Có | Lấy nội dung danh sách slide (dạng nháp hoặc bản cuối) |
| `POST` | `/api/document/projects/{id}/pages/sync` | Có | Đồng bộ nội dung slide người dùng đã sửa về CSDL |
| `POST` | `/api/document/projects/{id}/revise` | Có | Gửi các yêu cầu/nhận xét chỉnh sửa slide gửi lại AI |

---

## 7. Hướng dẫn Khởi chạy Local
1. Chạy MySQL và tạo database `document_service_db`.
2. Khởi động MinIO (hoặc AWS S3) tạo bucket như cấu hình.
3. Chạy lệnh:
   ```bash
   mvn clean package -DskipTests
   java -jar target/document-service-0.0.1-SNAPSHOT.jar
   ```
