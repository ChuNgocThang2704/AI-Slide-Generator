# LecGen Frontend

Frontend React + Vite cho luồng tạo, render, chỉnh sửa và xuất slide của LecGen.

## Chức năng hiện tại

- Đăng ký, xác minh email, đăng nhập thường/Google, refresh token và quên mật khẩu.
- Dashboard có thumbnail thật, tiến độ task và phân trang.
- Tạo slide từ prompt, file mới hoặc tài liệu đã upload.
- Editor ba panel có thể thay đổi kích thước, trình chiếu, template và AI Assistant.
- Chỉnh text, font, màu, danh sách, căn lề, khoảng cách dòng, ảnh, bảng và biểu đồ.
- Autosave, undo/redo và đồng bộ slide pages với BE.
- AI revise bằng một ô prompt; AI tự xác định slide/deck cần sửa.
- Xuất PDF và PPTX editable theo khả năng mapping của PowerPoint.
- Gói Free/Pro/Ultra, quota và thanh toán PayOS/Stripe.

## Cài đặt

```bash
npm ci
```

Tạo `.env` từ `.env.example`:

```env
# Để trống để dùng hostname của trình duyệt và cổng Gateway bên dưới.
VITE_API_BASE_URL=
VITE_GATEWAY_PORT=8080
```

Gateway local mặc định là `http://localhost:8080`. Khi FE được truy cập qua IP server, để trống `VITE_API_BASE_URL` giúp FE tự dùng cùng hostname thay vì khóa cứng `localhost`.

```bash
npm run dev -- --host 0.0.0.0 --port 5173
```

Production build:

```bash
npm run build
```

## Quy tắc tích hợp

- FE chỉ gọi Java API Gateway.
- Contract request/response: [../fe_api_spec.md](../fe_api_spec.md).
- Tạo project: `POST /api/document/projects`.
- Poll: `GET /api/document/projects/{id}/progress`.
- Lấy deck: `GET /api/document/projects/{id}/pages`.
- Sửa AI: `POST /api/document/projects/{id}/revise` với `revisionScope="auto"`.
- Sau revise, tải lại toàn bộ pages; không merge delta AI ở client.
- FE không tự gửi plan, không tự bật/tắt ảnh và không suy luận table/chart từ bullet.

## Cấu trúc

```text
src/components/   UI và slide renderer/editor
src/pages/        Auth, Dashboard, Generate, Editor, Pricing, Admin
src/services/     API clients
src/store/        Zustand stores
src/utils/        Slide mapping, text/image fit và export helpers
```
