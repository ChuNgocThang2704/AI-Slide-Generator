# 📡 Tài Liệu Tích Hợp API Dashboard Admin (Dành Cho Frontend)

Tài liệu này hướng dẫn chi tiết cách kết nối và hiển thị dữ liệu từ hai API Dashboard chính của `statistic-service` lên giao diện người dùng.

---

## 🔑 Thông Tin Chung
*   **Base URL (Qua API Gateway)**: `http://localhost:8080/api/statistic`
*   **Bảo mật & Phân quyền**: Yêu cầu bắt buộc gửi kèm Header `Authorization: Bearer <JWT_Token>`. API chỉ cấp quyền truy cập cho người dùng có quyền **`ADMIN`**.
*   **Bộ lọc chung**: Cả hai API đều nhận 2 tham số query parameter không bắt buộc:
    *   `startDate` (Định dạng: `yyyy-MM-dd` hoặc `dd/MM/yyyy`). Mặc định là **30 ngày trước**.
    *   `endDate` (Định dạng: `yyyy-MM-dd` hoặc `dd/MM/yyyy`). Mặc định là **Hôm nay**.

---

## 📈 1. Màn Hình 1: Dashboard Doanh Thu & Giao Dịch

*   **Endpoint**: `GET /dashboard/revenue`
*   **Tham số**: `?startDate=2026-02-01&endDate=2026-08-01`

### 🗂️ Phân Bản Đồ Dữ Liệu Lên UI

#### A. Thẻ Số Liệu Tổng Quan (Overview Cards)
Hiển thị ở trên cùng Dashboard để so sánh kỳ này so với kỳ trước.

| Thuộc tính JSON trong `data.summary` | Nhãn Hiển Thị (UI Label) | Ý nghĩa trường con | Cách hiển thị đề xuất |
| :--- | :--- | :--- | :--- |
| **`total_revenue_vnd`** | Doanh Thu VND (PayOS) | `current_value`: Giá trị kỳ này<br>`previous_value`: Giá trị kỳ trước<br>`growth`: Tỷ lệ % tăng trưởng | Hiển thị dạng thẻ số lớn.<br>Nếu `growth > 0` hiển thị màu xanh lá kèm icon mũi tên lên `↑`. Nếu `< 0` hiển thị màu đỏ kèm icon `↓`. |
| **`total_revenue_usd`** | Doanh Thu USD (Stripe) | Xem mô tả như trên | Tương tự thẻ Doanh Thu VND |
| **`active_subscriptions`** | Số Gói Đăng Ký Đang Hoạt Động | Xem mô tả như trên | Số lượng tài khoản trả phí đang hoạt động song song. |

#### B. Biểu Đồ Phân Bổ Gói Cước (Package Distribution Chart)
*   **Dữ liệu nguồn**: `data.package_distribution` (Dạng mảng)
*   **Loại biểu đồ đề xuất**: **Biểu đồ tròn (Pie Chart)** hoặc **Bánh Donut (Donut Chart)**.
*   **Cấu trúc dữ liệu và Ánh xạ**:
    ```json
    {
      "package_name": "Tên gói cước hiển thị trên chú thích (ví dụ: PRO_MONTH)",
      "count": "Số lượng giao dịch mua gói này (kiểu long)",
      "percent": "Tỷ lệ % hiển thị trên lát bánh biểu đồ (kiểu double)"
    }
    ```

#### C. Biểu Đồ Trạng Thái Giao Dịch (Transaction Status Chart)
*   **Dữ liệu nguồn**: `data.transaction_status_distribution` (Dạng mảng)
*   **Loại biểu đồ đề xuất**: **Biểu đồ cột nằm ngang (Horizontal Bar Chart)** hoặc **Biểu đồ tròn (Pie Chart)**.
*   **Cấu trúc dữ liệu và Ánh xạ**:
    ```json
    {
      "package_name": "Tên trạng thái giao dịch (ví dụ: SUCCESS, PENDING, FAILED)",
      "count": "Số lượng giao dịch ở trạng thái này",
      "percent": "Tỷ lệ phần trăm %"
    }
    ```

---

## 👥 2. Màn Hình 2: Dashboard Hoạt Động Người Dùng & AI Usage

*   **Endpoint**: `GET /dashboard/users`
*   **Tham số**: `?startDate=2026-02-01&endDate=2026-08-01`

### 🗂️ Phân Bản Đồ Dữ Liệu Lên UI

#### A. Thẻ Số Liệu Tổng Quan (Overview Cards)
Hiển thị ở trên cùng Dashboard.

| Thuộc tính JSON trong `data.summary` | Nhãn Hiển Thị (UI Label) | Ý nghĩa trường con | Cách hiển thị đề xuất |
| :--- | :--- | :--- | :--- |
| **`total_users`** | Tổng Người Dùng Đăng Ký | `current_value`: Số user mới kỳ này<br>`previous_value`: Số user mới kỳ trước<br>`growth`: Tốc độ tăng trưởng % | Thống kê số lượng tài khoản mới đăng ký tham gia hệ thống. |
| **`slides_generated`** | Số Slide Sinh Bằng AI | Xem mô tả như trên | Tổng số trang slide được sinh ra từ AI. |
| **`average_slides_per_user`** | Trung Bình Slide / User | Xem mô tả như trên | Hiệu suất sử dụng AI trung bình của một người dùng. |

#### B. Các Chỉ Số Cảnh Báo Vận Hành (Operational Warnings)
Hiển thị dưới dạng các thẻ cảnh báo màu vàng/đỏ (Alert Cards) để admin nắm bắt các điểm bất thường.

*   **Dữ liệu nguồn**: `data.user_warnings`

| Khóa JSON | Nhãn Hiển Thị (UI Label) | Ý nghĩa hiển thị | Cách xử lý UI đề xuất |
| :--- | :--- | :--- | :--- |
| **`inactive_users_30d`** | User Không Hoạt Động (30 ngày) | Số lượng user đăng ký nhưng không hề tạo slide nào trong 30 ngày qua. | Hiện thị cảnh báo nguy cơ rời bỏ dịch vụ (Churn Rate). |
| **`package_expiring_3d`** | Gói Premium Sắp Hết Hạn (3 ngày) | Số lượng người dùng sắp hết hạn gói cước trả phí trong vòng 3 ngày tới. | Cảnh báo để chuẩn bị gửi mail nhắc gia hạn. |
| **`unverified_emails`** | Tài Khoản Chưa Xác Thực Email | Số lượng người dùng đăng ký nhưng chưa nhấp liên kết xác minh tài khoản. | Đánh giá chất lượng đăng ký tài khoản mới. |

#### C. Các Bảng Xếp Hạng Người Dùng (Rankings Tables)
Hiển thị dạng bảng (Table) chia làm 3 Tab hoặc 3 Cột để Admin theo dõi hành vi người dùng.

*   **Dữ liệu nguồn**: 
    *   Tab 1 (Hoạt động nhiều nhất): `data.top_active_users` (Top 5)
    *   Tab 2 (Tăng trưởng tạo slide mạnh nhất): `data.top_increasers` (Top 3)
    *   Tab 3 (Sụt giảm tạo slide nhiều nhất): `data.top_decreasers` (Top 3)
*   **Cấu trúc dòng trong bảng**:
    ```json
    {
      "email": "Email người dùng (ví dụ: user@example.com)",
      "package_tier": "Gói cước hiện tại (FREE / PRO / ULTRA)",
      "slides_count": "Tổng số slide đã tạo trong kỳ lọc",
      "growth": "Tốc độ tăng/giảm số slide tạo ra so với kỳ trước (%)"
    }
    ```

#### D. Biểu Đồ Cột Lượng Slide Theo Tháng (Monthly Slides Chart)
*   **Dữ liệu nguồn**: `data.yearly_slides_chart` (Mảng dữ liệu từ Tháng 1 đến tháng hiện tại)
*   **Loại biểu đồ đề xuất**: **Biểu đồ cột (Bar Chart)**.
*   **Cấu trúc dữ liệu và Ánh xạ**:
    ```json
    {
      "month": "Tháng (1.0 = Tháng 1, 2.0 = Tháng 2, ...)",
      "total_slides": "Tổng số slide tạo ra trong tháng đó"
    }
    ```

#### E. Biểu Đồ Xu Hướng Slide Theo Ngày (Daily Slides Trend Chart)
*   **Dữ liệu nguồn**: `data.daily_slides_chart` (Mảng chứa tất cả các ngày trong khoảng thời gian lọc)
*   **Loại biểu đồ đề xuất**: **Biểu đồ đường (Line Chart)**.
*   **Cấu trúc dữ liệu và Ánh xạ**:
    ```json
    {
      "date": "Ngày (Định dạng: yyyy-MM-dd, ví dụ: 2026-08-01)",
      "total_slides": "Số lượng slide tạo ra trong ngày đó (tự động gán 0 nếu ngày đó không có slide nào)"
    }
    ```
