# Template Service - Slide Layout Catalog (Quản lý Mẫu Slide & Thiết Kế)

## 1. Giới thiệu
Template Service là dịch vụ quản lý thư viện các mẫu thiết kế slide trong hệ thống. Nó lưu trữ cấu trúc mẫu slide (màu sắc, phông chữ, danh mục) và ánh xạ các file PowerPoint gốc (`.pptx` master layout) lưu trên S3 để Python AI Engine có thể tải về làm khung xương chèn nội dung.

---

## 2. Công nghệ Sử dụng
- **Framework**: Java 21, Spring Boot 3.x, Spring Web.
- **Truy cập Dữ liệu**: Spring Data JPA, Hibernate.
- **Cơ sở dữ liệu**: **MySQL** (`template_service_db`).
- **Lưu trữ file mẫu**: AWS S3 / MinIO Storage.

---

## 3. Tính năng Chính & Cơ chế
- Phân loại mẫu thiết kế slide theo các chủ đề: Business, Education, Technology, Art.
- Quản lý hạn mức truy cập mẫu thiết kế (nhãn `is_premium` để hạn chế người dùng miễn phí sử dụng các mẫu thiết kế Pro).
- Cung cấp liên kết S3 của file `.pptx` gốc (chứa các layout master). AI Worker sẽ tải file master này về, chèn văn bản và hình ảnh vào đúng các tọa độ định sẵn rồi lưu lại.

---

## 4. Chi tiết Cấu trúc Bảng Cơ sở dữ liệu (MySQL)

- **`categories`**: Danh mục mẫu thiết kế (id, name, description, các cột audit).
- **`templates`**: Các mẫu slide chi tiết (id, name, description, s3_url, num_slides, is_premium, category_id, các cột audit).

---

## 5. Cấu hình & Biến Môi trường

Các cấu hình chính được định nghĩa trong file `application.yml`. Hãy khai báo các biến này trong file `.env` gốc mà không viết cứng giá trị bí mật:

```yaml
server:
  port: ${TEMPLATE_SERVICE_PORT} # Cổng chạy (Mặc định: 8083)
  servlet:
    context-path: /api/template

spring:
  datasource:
    url: ${TEMPLATE_DB_URL}   # jdbc:mysql://<host>:<port>/template_service_db
    username: ${TEMPLATE_DB_USERNAME}
    password: ${TEMPLATE_DB_PASSWORD}
  servlet:
    multipart:
      max-file-size: 50MB
      max-request-size: 50MB

jwt:
  signerKey: ${JWT_SIGNER_KEY}

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
| `GET` | `/api/template/categories` | Có | Xem toàn bộ danh mục mẫu slide |
| `POST` | `/api/template/categories` | Có (Admin) | Thêm danh mục mẫu slide mới |
| `GET` | `/api/template/templates` | Có | Xem danh sách các mẫu slide trong kho (có thể lọc theo category) |
| `POST` | `/api/template/templates` | Có (Admin) | Upload file mẫu, ảnh đại diện mẫu và đăng ký lên S3 |
| `DELETE` | `/api/template/templates/{id}` | Có (Admin) | Xóa mềm mẫu slide khỏi hệ thống |

---

## 7. Hướng dẫn Khởi chạy Local
1. Chạy MySQL và tạo database `template_service_db`.
2. Khai báo các thông tin AWS S3 / MinIO.
3. Chạy lệnh:
   ```bash
   mvn clean package -DskipTests
   java -jar target/template-service-0.0.1-SNAPSHOT.jar
   ```
