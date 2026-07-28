# LecGen Frontend

Giao diện ứng dụng tạo và chỉnh sửa slide thuyết trình tự động bằng AI (AI Presentation Generator), được xây dựng trên nền tảng **React + Vite** hiện đại, mượt mà và tối ưu trải nghiệm người dùng.

---

## ✨ Tính Năng Chính

* 🚀 **Tạo Slide bằng AI**: Nhập chủ đề/prompt hoặc tải lên tệp tài liệu (`.pdf`, `.docx`, `.txt`) để AI tự động tổng hợp và thiết kế bài thuyết trình.
* ✍️ **Trình Chỉnh Sửa Tương Tác**:
  * Chỉnh sửa trực tiếp tiêu đề, nội dung bullet, ghi chú (Speaker Notes).
  * Đổi màu sắc chủ đề (Template Themes: *Soft Blue, Royal Purple, Clean White, Modern Dark...*).
  * Thay đổi emoji, hình ảnh minh họa trên từng slide.
* 🤖 **AI Assistant (Chỉnh Sửa Slide Bằng AI)**:
  * Nhập câu lệnh tự nhiên để sửa lại nội dung 1 slide cụ thể hoặc toàn bộ deck.
  * Tự động cập nhật giao diện mà không cần tải lại trang.
* 📊 **Xuất File**:
  * Export trực tiếp ra tệp **PowerPoint (`.pptx`)** vật lý giữ nguyên chuẩn định dạng và hình ảnh.
  * Xuất tài liệu PDF.
* 💳 **Nâng Cấp Gói Cước**:
  * Tích hợp thanh toán Quét mã VietQR qua **PayOS** (VNĐ).
  * Tích hợp thanh toán Thẻ quốc tế Visa/Mastercard qua **Stripe Checkout** (USD).
* 🛡️ **Quản Trị Viên (Admin Dashboard)**: Trang quản lý người dùng, gói cước và phân quyền hệ thống.

---

## 🛠️ Công Nghệ Sử Dụng

* **Core**: React 18, Vite
* **State Management**: Zustand
* **Styling**: Vanilla CSS, Responsive Layout, Dark/Light Glassmorphism Mode
* **Icons & Animations**: Lucide React, Framer Motion
* **Export**: Custom XML PPTX Generator Engine

---

## 🚀 Hướng Dẫn Cài Đặt & Chạy Ứng Dụng

### 1. Yêu Cầu Tiền Trạm
* **Node.js**: Phiên bản `>= 18.x`
* **npm** hoặc **yarn** / **pnpm**

### 2. Cài Đặt Thư Viện
Mở terminal tại thư mục gốc của dự án và chạy:
```bash
npm install
```

### 3. Cấu Hình Biến Môi Trường (`.env`)
Tạo file `.env` tại thư mục gốc (hoặc sao chép từ `.env.example`):
```env
VITE_API_BASE_URL=http://localhost:7172/api
```
*(Thay đổi URL API Gateway theo cổng Backend tương ứng của bạn).*

### 4. Chạy Môi Trường Phát Triển (Development)
```bash
npm run dev
```
Trình duyệt sẽ tự động mở tại địa chỉ: `http://localhost:5173/`

### 5. Đóng Gói Production (Build)
```bash
npm run build
```
Thư mục `dist/` sẽ chứa toàn bộ mã nguồn đã được tối ưu hóa sẵn sàng cho việc deployment.

---

## 📁 Cấu Trúc Thư Mục

```
src/
├── assets/          # Hình ảnh tĩnh và tài nguyên dự án
├── components/      # Các linh kiện tái sử dụng (Navbar, SlideRenderer, EditableSlide, Toast...)
├── pages/           # Màn hình chính (Landing, Auth, Dashboard, Generate, Editor, Pricing, Admin...)
├── services/        # Các hàm gọi API (authService, documentService, pptxExportService, subscriptionService...)
├── store/           # Quản lý State toàn cục bằng Zustand (authStore, uiStore...)
├── App.jsx          # Định tuyến (Routing) chính của ứng dụng
└── main.jsx         # Điểm khởi chạy React app
```
