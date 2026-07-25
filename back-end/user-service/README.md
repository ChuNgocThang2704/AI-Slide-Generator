# User Service - Identity, Access Management & Authentication (Định Danh & Phân Quyền)

## 1. Giới thiệu
User Service là dịch vụ quản lý định danh cốt lõi (Core Identity Service) của hệ thống tạo slide bằng AI. Dịch vụ chịu trách nhiệm đăng ký, đăng nhập tài khoản người dùng (qua email/mật khẩu truyền thống và Google OAuth2), quản lý hồ sơ cá nhân, phân quyền truy cập chi tiết (RBAC) và cấp phát cặp Token bảo mật (JWT).

---

## 2. Công nghệ Sử dụng
- **Framework**: Spring Boot 3.x, Spring Security (Cấu hình xác thực JWT).
- **Truy cập Dữ liệu**: Spring Data JPA, Hibernate.
- **Cơ sở dữ liệu**: **PostgreSQL** (`user_service_db`).
- **Cache & Message Broker**: Redis (lưu vết token), RabbitMQ (gửi sự kiện kích hoạt xác thực email).

---

## 3. Các Tính năng Chính & Luồng Nghiệp vụ

### 3.1. Xác thực Tài khoản đa dạng
- **Đăng nhập Email/Mật khẩu**: 
  - Mã hóa mật khẩu lưu trữ bằng thuật toán **BCrypt** (`BCryptPasswordEncoder`).
  - Quản lý cờ kích hoạt email (`email_verified`).
- **Đăng nhập Google OAuth2**:
  - Tiếp nhận mã token từ phía Google, xác thực và đồng bộ thông tin tài khoản người dùng (`email`, `googleId`, `name`) vào hệ thống cục bộ.
- **Cấp phát JWT Tokens**:
  - Sinh **Access Token** chứa thông tin định danh và danh sách quyền hạn cụ thể (hiệu lực ngắn).
  - Sinh **Refresh Token** lưu dưới DB hoặc Redis giúp gia hạn tự động (hiệu lực dài).

### 3.2. Phân quyền Theo Vai trò (RBAC - Role-Based Access Control)
Phân quyền truy cập các API chức năng thông qua mô hình:
- **PermissionEntity (`permissions`)**: Các quyền thao tác chi tiết (Ví dụ: `CREATE_PROJECT`, `EXPORT_PPTX`).
- **RoleEntity (`roles`)**: Nhóm các quyền hạn lại (Ví dụ: `ROLE_FREE`, `ROLE_PRO`, `ROLE_ADMIN`).
- **UserEntity (`users`)**: Liên kết đa-đa với các vai trò để tự động kế thừa tập quyền hạn tương ứng khi thực hiện yêu cầu qua Gateway.

### 3.3. Gửi Thông tin Xác thực qua RabbitMQ
- Khi người dùng đăng ký tài khoản mới, hệ thống tự động đẩy một thông điệp chứa thông tin tài khoản và mã xác thực vào hàng đợi `notification_queue`.
- Dịch vụ `notification-service` sẽ lắng nghe hàng đợi này để biên dịch email và gửi đi.

---

## 4. Chi tiết Cấu trúc Bảng Cơ sở dữ liệu (PostgreSQL)

- **`users`**: Lưu thông tin tài khoản (id, username, password, email, google_id, status, email_verified, last_login_at, các cột audit).
- **`user_profiles`**: Thông tin cá nhân (user_id, full_name, avatar_url, date_of_birth, phone_number, các cột audit).
- **`roles`**: Danh mục vai trò (name, description, các cột audit).
- **`permissions`**: Quyền chi tiết (name, description, các cột audit).
- **`user_roles`**: Bảng nối ánh xạ người dùng - vai trò (`user_id`, `role_name`).
- **`role_permission`**: Bảng nối ánh xạ vai trò - quyền (`role_name`, `permission_name`).

---

## 5. Cấu hình & Biến Môi trường

Các cấu hình chính được định nghĩa trong file `application.yml`. Hãy khai báo các biến này trong file `.env` gốc mà không viết cứng giá trị bí mật:

```yaml
server:
  port: ${USER_SERVICE_PORT} # Cổng chạy (Mặc định: 8081)

spring:
  datasource:
    url: ${USER_DB_URL}       # jdbc:postgresql://<host>:<port>/user_service_db
    username: ${USER_DB_USERNAME}
    password: ${USER_DB_PASSWORD}
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
  mail:
    host: smtp.gmail.com
    port: 587
    username: ${MAIL_USERNAME}
    password: ${MAIL_PASSWORD}

jwt:
  signerKey: ${JWT_SIGNER_KEY}
  valid-duration: ${JWT_VALID_DURATION}
  refreshable-duration: ${JWT_REFRESH_DURATION}

google:
  client-id: ${GOOGLE_CLIENT_ID}
  client-secret: ${GOOGLE_SECRET}
  redirect-uri: ${GOOGLE_REDIRECT_URL}
  user-info-uri: ${USER_INFO_URI}
  token-uri: ${TOKEN_GOOGLE_URI}

app:
  rabbitmq:
    queue: ${RABBIT_QUEUE} # Mặc định: notification_queue
```

---

## 6. Danh sách API Endpoints

| Phương thức | Đường dẫn API | Xác thực JWT | Mô tả |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/auth/register` | Không | Đăng ký tài khoản người dùng mới |
| `POST` | `/api/auth/login` | Không | Đăng nhập bằng Email/Password (trả về Access/Refresh Token) |
| `POST` | `/api/auth/refresh` | Không | Sử dụng Refresh Token lấy Access Token mới |
| `POST` | `/api/auth/google` | Không | Đăng nhập/Đăng ký thông qua Google OAuth2 Token |
| `GET` | `/api/users/profile` | Có | Lấy thông tin hồ sơ của tài khoản đang đăng nhập |
| `PUT` | `/api/users/profile` | Có | Cập nhật thông tin họ tên, ảnh đại diện, ngày sinh, SĐT |
| `POST` | `/api/users/change-password` | Có | Thay đổi mật khẩu người dùng |

---

## 7. Hướng dẫn Khởi chạy Local
1. Chạy PostgreSQL và tạo database `user_service_db`.
2. Khởi tạo RabbitMQ và Redis server.
3. Xuất biến môi trường từ file `.env` và chạy lệnh:
   ```bash
   mvn clean package -DskipTests
   java -jar target/user-service-0.0.1-SNAPSHOT.jar
   ```
