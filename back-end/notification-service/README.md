# Notification Service - Asynchronous Email Dispatcher (Dịch vụ Thông báo & Gửi Mail)

## 1. Giới thiệu
Notification Service là một dịch vụ hạ tầng chạy ngầm không trạng thái (Stateless). Dịch vụ đăng ký lắng nghe (Subscribe) hàng đợi sự kiện **RabbitMQ**, tự động tiếp nhận các yêu cầu gửi email từ các service khác (như xác thực tài khoản từ User Service) để biên dịch nội dung động và thực hiện gửi email qua giao thức SMTP.

---

## 2. Công nghệ Sử dụng
- **Framework**: Spring Boot 3.x, Spring AMQP (Tích hợp lắng nghe hàng đợi RabbitMQ).
- **Trình gửi mail**: Spring Boot Starter Mail (Java Mail Sender).
- **Template Engine**: **Thymeleaf** biên dịch các template HTML động.
- **Database**: **Stateless** (Không sử dụng cơ sở dữ liệu).

---

## 3. Các Tính năng Chính & Cơ chế

### 3.1. Nhận Sự kiện Bất đồng bộ (RabbitMQ Consumer)
- Lắng nghe hàng đợi được cấu hình bởi biến `${RABBIT_QUEUE}` (Mặc định là `notification_queue`).
- Tiếp nhận payload JSON chứa: email người nhận, tiêu đề thư, loại email (Xác thực, Hóa đơn, Quota) và các biến dữ liệu động đi kèm.

### 3.2. Biên dịch Email bằng Thymeleaf
- Sử dụng các file giao diện email HTML thiết kế sẵn trong thư mục `src/main/resources/templates/`.
- Điền các thông tin động (như mã OTP, liên kết kích hoạt, họ tên khách hàng) vào template và thực hiện gửi đi bằng Gmail SMTP Server hoặc SMTP Relay khác.

---

## 4. Cấu hình & Biến Môi trường

Các cấu hình chính được định nghĩa trong file `application.yml`. Hãy khai báo các biến này trong file `.env` gốc mà không viết cứng giá trị bí mật:

```yaml
server:
  port: ${NOTIFICATION_PORT} # Cổng chạy (Mặc định: 8090)

spring:
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
    username: ${MAIL_USERNAME} # Địa chỉ Gmail gửi thư
    password: ${MAIL_PASSWORD} # Mật khẩu ứng dụng Gmail (App Password)
  thymeleaf:
    prefix: classpath:/templates/
    suffix: .html
    mode: HTML
    encoding: UTF-8

app:
  mail:
    from-name: ${MAIL_FROM_NAME} # Tên hiển thị người gửi (Ví dụ: LecGen)
  rabbitmq:
    queue: ${RABBIT_QUEUE}
```

---

## 5. Hướng dẫn Khởi chạy Local
1. Chạy RabbitMQ Broker và tạo queue tương ứng.
2. Thiết lập cấu hình tài khoản Gmail gửi thư (sử dụng mật khẩu ứng dụng 2 lớp).
3. Chạy lệnh:
   ```bash
   mvn clean package -DskipTests
   java -jar target/notification-service-0.0.1-SNAPSHOT.jar
   ```
