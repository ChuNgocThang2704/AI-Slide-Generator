# API Gateway Service - Edge Gateway & Rate Limiter (Cổng Kết Nối & Giới Hạn Tải)

## 1. Giới thiệu
API Gateway Service là thành phần trung gian (Edge Layer) đứng trước toàn bộ hệ thống Microservices của dự án Tạo Slide bằng AI. Nó đóng vai trò là điểm đầu mối duy nhất (Single Entry Point) tiếp nhận, kiểm tra bảo mật, định tuyến và giới hạn tải các yêu cầu từ phía Client trước khi chuyển tiếp chúng đến các microservice nghiệp vụ nội bộ thích hợp.

---

## 2. Kiến trúc & Công nghệ Cốt lõi
- **Công nghệ sử dụng**: Java 21, Spring Boot 3.x, Spring Cloud Gateway, Reactive Spring WebFlux, Project Reactor.
- **Không trạng thái (Stateless)**: Gateway không sử dụng cơ sở dữ liệu lưu trữ trực tiếp. Nó chỉ kết nối với **Redis** để quản lý các khóa giới hạn tải (Rate Limiter).
- **Non-blocking IO**: Sử dụng máy chủ Netty làm nền tảng chạy bất đồng bộ để xử lý hàng nghìn kết nối đồng thời với lượng tài nguyên tối thiểu.

---

## 3. Các Tính năng Chính

### 3.1. Định tuyến Động & Lọc Context Path (Dynamic Routing)
Chuyển tiếp yêu cầu REST API hoặc WebSocket của Client tới các service đích chạy ngầm bên trong hệ thống mạng nội bộ, giúp che giấu vị trí vật lý của các service.

- `/api/auth/**` -> Chuyển tiếp tới `user-service` (loại bỏ prefix 1 cấp)
- `/api/users/**` -> Chuyển tiếp tới `user-service` (loại bỏ prefix 1 cấp)
- `/api/roles/**`, `/api/permissions/**` -> Chuyển tiếp tới `user-service` (loại bỏ prefix 1 cấp)
- `/api/document/**` -> Chuyển tiếp tới `document-service` (giữ nguyên prefix)
- `/api/template/**` -> Chuyển tiếp tới `template-service` (giữ nguyên prefix)
- `/api/subscription/**` -> Chuyển tiếp tới `subscription-service` (giữ nguyên prefix)
- `/api/payment/**` -> Chuyển tiếp tới `payment-service` (giữ nguyên prefix)

### 3.2. Bộ lọc Xác thực & Nhúng Thông tin Định danh (JWT Filter)
- Tích hợp một bộ lọc tùy chỉnh (`JwtAuthenticationFilter`) chặn mọi yêu cầu đi qua các endpoint yêu cầu bảo mật.
- Giải mã và xác thực chữ ký của Token JWT lấy từ Header `Authorization: Bearer <token>` bằng khóa bí mật chung `JWT_SIGNER_KEY`.
- Nếu hợp lệ, hệ thống sẽ trích xuất các claims gồm `userId`, `role`, `permissions` rồi nhúng ngược lại vào Header của request gửi đi tiếp:
  - `X-User-Id`
  - `X-User-Role`
  - `X-User-Permissions`
- Nhờ vậy, các service nghiệp vụ phía sau chỉ cần đọc Header này là có thể tin tưởng ngay danh tính người dùng mà không cần thực hiện giải mã JWT lại.

### 3.3. Giới hạn Tải Phân tán (Redis Token Bucket Rate Limiting)
- Triển khai giới hạn tần suất gọi API reactive sử dụng thuật toán Token Bucket lưu trữ trên Redis.
- Cấu hình với `replenishRate = 10` (số token được nạp lại mỗi giây) và `burstCapacity = 20` (dung lượng tối đa của bucket).
- Sử dụng bộ phân giải khóa `ipKeyResolver` để chặn các cuộc tấn công spam API hoặc DDoS từ một IP cụ thể.

---

## 4. Cấu hình & Biến Môi trường

Các cấu hình chính được định nghĩa trong file `application.yml`. Hãy khai báo các biến này trong file `.env` gốc mà không viết cứng giá trị bí mật vào mã nguồn:

```yaml
server:
  port: ${GATEWAY_PORT} # Cổng chạy của gateway (Mặc định: 8080)

spring:
  application:
    name: api-gateway
  codec:
    max-in-memory-size: 50MB # Cấu hình cho phép truyền tải file dung lượng lớn
  data:
    redis:
      url: ${REDIS_URL} # URL kết nối Redis (Ví dụ: redis://localhost:6379)
      ssl:
        enabled: ${REDIS_SSL_ENABLED}
      connect-timeout: 5000ms
      timeout: 5000ms
  cloud:
    gateway:
      globalcors:
        add-to-chain: true
        cors-configurations:
          '[/**]':
            allowedOrigins: "*"
            allowedMethods: [GET, POST, PUT, DELETE, OPTIONS]
            allowedHeaders: "*"
            maxAge: 3600
      routes:
        # Cấu hình định tuyến chi tiết đến từng service
jwt:
  signerKey: ${JWT_SIGNER_KEY} # Khóa bí mật ký JWT dùng chung
```

---

## 5. Hướng dẫn Khởi chạy Local

### Điều kiện cần
- Đã cài đặt JDK 21.
- Redis server đang chạy (Cổng `6379` hoặc custom).

### Các bước chạy
1. Khai báo các biến môi trường cần thiết (hoặc điền vào file `.env` ở thư mục root):
   - `GATEWAY_PORT=8080`
   - `REDIS_URL=redis://localhost:6379`
   - `JWT_SIGNER_KEY=your_32_characters_long_secret_key`
2. Build dự án:
   ```bash
   mvn clean package -DskipTests
   ```
3. Chạy file JAR đã biên dịch:
   ```bash
   java -jar target/api-gateway-0.0.1-SNAPSHOT.jar
   ```
