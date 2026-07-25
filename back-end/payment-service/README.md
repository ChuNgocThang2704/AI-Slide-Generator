# Payment Service - Stripe & PayOS Gateway Integrator (Tích hợp Thanh toán)

## 1. Giới thiệu
Payment Service là dịch vụ xử lý giao dịch thanh toán không lưu trạng thái (Stateless). Nó chịu trách nhiệm tích hợp trực tiếp các cổng thanh toán Stripe (phục vụ thanh toán thẻ quốc tế) và PayOS (hỗ trợ thanh toán VietQR ngân hàng nội địa), đồng thời kiểm duyệt các cuộc gọi Webhook từ đối tác để kích hoạt gói cước tương ứng.

---

## 2. Công nghệ Sử dụng
- **Framework**: Spring Boot 3.x, Spring Web.
- **Thư viện tích hợp**: Stripe Java SDK, PayOS Java SDK.
- **Database**: **Stateless** (Không có database lưu dữ liệu riêng).
- **Giao tiếp**: RestTemplate (gọi API của `subscription-service`), RabbitMQ (đẩy event giao dịch thành công).

---

## 3. Tính năng Chính & Cơ chế Hoạt động

### 3.1. Tích hợp Stripe Checkout
- Khởi tạo phiên thanh toán Stripe (Stripe Checkout Session) khi người dùng chọn gói Pro và click nâng cấp.
- Trả về đường dẫn của Stripe, FE sẽ điều hướng người dùng tới trang Stripe để thanh toán bảo mật.
- Cấu hình API nhận Webhook Stripe (`/api/payment/stripe/webhook`). Xác thực chữ ký payload (`Stripe-Signature`) bằng khóa mã hóa `STRIPE_WEBHOOK_SECRET` để đảm bảo request gửi đến thực sự là từ Stripe, tránh bị giả mạo hóa đơn.

### 3.2. Tích hợp PayOS (VietQR)
- Khởi tạo link thanh toán (Payment Link) qua API PayOS, sinh mã VietQR động có sẵn số tiền và mã hóa đơn nội bộ.
- Cấu hình nhận Webhook PayOS (`/api/payment/payos/webhook`).
- Xác thực chữ ký webhook bằng cách tính toán chữ ký SHA256 dựa trên dữ liệu payload và khóa `PAYOS_CHECKSUM_KEY`, đảm bảo thông điệp không bị thay đổi trên đường truyền.

---

## 4. Cấu hình & Biến Môi trường

Các cấu hình chính được định nghĩa trong file `application.yml`. Hãy khai báo các biến này trong file `.env` gốc mà không viết cứng giá trị bí mật:

```yaml
server:
  port: ${PORT} # Cổng chạy (Mặc định: 8085)
  servlet:
    context-path: /api/payment

payos:
  client-id: ${PAYOS_CLIENT_ID}
  api-key: ${PAYOS_API_KEY}
  checksum-key: ${PAYOS_CHECKSUM_KEY}

stripe:
  secret-key: ${STRIPE_SECRET_KEY}
  webhook-secret: ${STRIPE_WEBHOOK_SECRET}
  currency: ${STRIPE_CURRENCY} # Loại tiền tệ giao dịch (usd hoặc vnd)

jwt:
  signerKey: ${JWT_SIGNER_KEY}

app:
  subscription-service:
    url: ${SUBSCRIPTION_SERVICE_URL} # URL đích để kích hoạt gói khi thanh toán xong
```

---

## 5. Danh sách API Endpoints

| Phương thức | Đường dẫn API | Xác thực JWT | Mô tả |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/payment/stripe/create-session` | Có | Tạo phiên thanh toán Stripe (Trả về URL thanh toán) |
| `POST` | `/api/payment/payos/create-link` | Có | Tạo link thanh toán PayOS VietQR (Trả về URL quét mã) |
| `POST` | `/api/payment/stripe/webhook` | Không (Public) | Webhook callback nhận kết quả giao dịch tự động từ Stripe |
| `POST` | `/api/payment/payos/webhook` | Không (Public) | Webhook callback nhận kết quả giao dịch tự động từ PayOS |

---

## 6. Hướng dẫn Khởi chạy Local
1. Đảm bảo dịch vụ `subscription-service` đang chạy.
2. Lấy các khóa API key test từ Stripe Dashboard và PayOS Dashboard điền vào file `.env`.
3. Chạy lệnh:
   ```bash
   mvn clean package -DskipTests
   java -jar target/payment-service-0.0.1-SNAPSHOT.jar
   ```
