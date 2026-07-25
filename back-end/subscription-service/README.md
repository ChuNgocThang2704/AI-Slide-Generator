# Subscription Service - Tier Management & Quota Controller (Quản lý Gói cước & Hạn mức)

## 1. Giới thiệu
Subscription Service chịu trách nhiệm quản lý các gói dịch vụ (Free, Pro, Enterprise), kiểm soát quyền lợi, hạn mức sử dụng (Quotas) của khách hàng theo thời gian thực (ví dụ: số lượt sinh slide hàng ngày, lượt tạo ảnh AI). Dịch vụ phối hợp với `payment-service` để gia hạn tự động sau khi giao dịch thành công.

---

## 2. Công nghệ Sử dụng
- **Framework**: Spring Boot 3.x, Spring Web.
- **Truy cập Dữ liệu**: Spring Data JPA, Hibernate.
- **Cơ sở dữ liệu**: **PostgreSQL** (`subscription_service_db`).
- **Cache & Message Broker**: Redis (lưu bộ đếm quota tạm thời), RabbitMQ (nhận sự kiện hoàn tất thanh toán từ payment-service).

---

## 3. Các Tính năng Chính & Luồng Nghiệp vụ

### 3.1. Cấu hình Quyền lợi Gói dịch vụ
- Định nghĩa giới hạn sử dụng các tính năng dưới dạng các cặp key-value lưu ở bảng `package_features` (Ví dụ: `DAILY_GENERATIONS = 5` đối với gói Free, `50` đối với gói Pro).

### 3.2. Cung cấp API Kiểm tra & Khấu trừ Hạn mức (Quota)
- Cung cấp API nội bộ thông qua OpenFeign để `document-service` gọi:
  - `checkQuota(userId, featureKey)`: Kiểm tra xem người dùng còn lượt dùng tính năng này hay không.
  - `consumeQuota(userId, featureKey, amount)`: Trừ bớt lượt sử dụng sau khi slide được sinh thành công.
  - `resetQuotas()`: Scheduler chạy ngầm để thiết lập lại số lượt sử dụng về 0 khi bắt đầu ngày mới hoặc chu kỳ gia hạn mới.

### 3.3. Lắng nghe Sự kiện Thanh toán thành công
- Lắng nghe message hoàn thành giao dịch từ RabbitMQ để tự động:
  - Chuyển trạng thái gói cước sang `ACTIVE`.
  - Cập nhật thời hạn sử dụng gói cước (`start_date`, `expire_date`).
  - Thiết lập lại hoặc mở rộng hạn mức sử dụng cao cấp của tài khoản.

---

## 4. Chi tiết Cấu trúc Bảng Cơ sở dữ liệu (PostgreSQL)

- **`subscription_packages`**: Chứa thông tin các gói cước (id, code, name, description, price_vnd, price_usd, billing_cycle, các cột audit).
- **`package_features`**: Quy định hạn mức tính năng của từng gói (id, package_id, feature_key, feature_value, các cột audit).
- **`user_subscriptions`**: Theo dõi gói cước hiện tại của người dùng (id, user_id, package_id, start_date, expire_date, status, quota_reset_date, order_code, các cột audit).
- **`user_feature_usages`**: Lưu trữ số lượt đã dùng thực tế của người dùng (id, user_id, feature_key, usage_value, last_reset_time, các cột audit).
- **`subscription_history`**: Nhật ký thay đổi gói cước để đối soát (id, user_id, action, previous_package_code, new_package_code, note, các cột audit).

---

## 5. Cấu hình & Biến Môi trường

Các cấu hình chính được định nghĩa trong file `application.yml`. Hãy khai báo các biến này trong file `.env` gốc mà không viết cứng giá trị bí mật:

```yaml
server:
  port: ${SUBSCRIPTION_SERVICE_PORT} # Cổng chạy (Mặc định: 8084)
  servlet:
    context-path: /api/subscription

spring:
  datasource:
    url: ${SUB_DB_URL}         # jdbc:postgresql://<host>:<port>/subscription_service_db
    username: ${SUB_DB_USERNAME}
    password: ${SUB_DB_PASSWORD}
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
  payment-service:
    url: ${PAYMENT_SERVICE_URL} # Địa chỉ cổng thanh toán để điều hướng nâng cấp
  rabbitmq:
    queue: ${RABBIT_QUEUE}

payos:
  return-url: ${PAYOS_RETURN_URL}
  cancel-url: ${PAYOS_CANCEL_URL}
```

---

## 6. Danh sách API Endpoints

| Phương thức | Đường dẫn API | Xác thực JWT | Mô tả |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/subscription/packages` | Có | Xem toàn bộ các gói cước đang hoạt động |
| `POST` | `/api/subscription/users/upgrade` | Có | Yêu cầu nâng cấp gói cước (gọi payment-service tạo link thanh toán) |
| `GET` | `/api/subscription/users/current` | Có | Xem chi tiết gói đang sử dụng và hạn mức quota còn lại của tôi |
| `POST` | `/api/subscription/internal/check-quota` | Nội bộ (Feign) | Kiểm tra xem user có đủ quota gọi AI không |
| `POST` | `/api/subscription/internal/consume-quota` | Nội bộ (Feign) | Thực hiện trừ quota sau khi AI hoàn thành nhiệm vụ |

---

## 7. Hướng dẫn Khởi chạy Local
1. Chạy PostgreSQL và tạo database `subscription_service_db`.
2. Khởi chạy Redis và RabbitMQ.
3. Chạy lệnh:
   ```bash
   mvn clean package -DskipTests
   java -jar target/subscription-service-0.0.1-SNAPSHOT.jar
   ```
