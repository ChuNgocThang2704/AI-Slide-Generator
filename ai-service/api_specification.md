# Tài Liệu Tích Hợp API — AI Slide Generator

Tài liệu này mô tả chi tiết các API của hệ thống AI Slide Generator để lập trình viên Frontend (FE) dễ dàng tích hợp.

* **Base URL:** `http://20.196.129.89:8000`
* **Kiểu truyền dữ liệu đầu vào (Request):** Hỗ trợ `multipart/form-data` hoặc `application/x-www-form-urlencoded`.

---

## 1. API Sinh Dữ Liệu JSON Cấu Trúc Slide (Không Sinh File PPTX)

API này dùng để lấy về cấu trúc slide chi tiết định dạng JSON (tiêu đề, các đầu mục chữ, bố cục layout gợi ý, bảng biểu, biểu đồ và ảnh). Dữ liệu này cực kỳ thích hợp để FE dựng giao diện Preview, hiển thị slide trực tiếp trên trang web.

* **Endpoint:** `/api/generate-slide-spec` (hoặc alias `/generate-spec`)
* **Method:** `POST`
* **Content-Type:** `multipart/form-data` hoặc `application/x-www-form-urlencoded`

### Tham số đầu vào (Request Body)

| Tham số | Kiểu dữ liệu | Bắt buộc | Mô tả |
| :--- | :--- | :--- | :--- |
| `text` | String | Không * | Nội dung bài viết thô cần tạo slide. |
| `file` | File | Không * | File tài liệu nguồn tải lên (hỗ trợ `.docx`, `.pdf`, `.txt`). |
| `content` | String (JSON) | Không * | Chuỗi JSON chứa cấu trúc slide đã có sẵn nếu muốn Backend chỉ định dạng lại. |
| `plan` | String | Không | Gói dịch vụ: `free` (giới hạn 10 slide), `pro` (tối đa 30 slide - mặc định), `ultra` (tối đa 50 slide). |
| `slide_count` | Integer | Không | Số lượng slide mong muốn tạo (chỉ áp dụng cho gói `pro` và `ultra`). |
| `slide_theme` | String | Không | Giao diện slide: `modern` (indigo), `corporate` (navy), `minimal` (white). |
| `generate_images` | String | Không | Có sinh ảnh minh họa bằng AI không: `"true"` hoặc `"false"` (mặc định). |
| `image_limit` | Integer | Không | Giới hạn số lượng ảnh sinh ra. |
| `include_image_base64` | String | Không | Trả về dữ liệu ảnh trực tiếp dạng base64 trong JSON: `"true"` hoặc `"false"` (mặc định). |

*\* Lưu ý: Bắt buộc phải truyền ít nhất 1 trong 3 trường `text`, `file` hoặc `content`.*

### Ví dụ Request (CURL)
```bash
curl -X POST "http://20.196.129.89:8000/api/generate-slide-spec" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "text=Lịch sử phát triển của trí tuệ nhân tạo qua các thời kỳ từ năm 1950 đến nay." \
  -F "plan=pro" \
  -F "slide_theme=modern" \
  -F "generate_images=true"
```

### Phản hồi thành công (Response 200 OK)
```json
{
  "task_id": "0d9c4456-5be5-4d7a-be92-e427cf664188",
  "status": "completed",
  "mode": "json_spec",
  "spec_version": "1.2",
  "slide_preset": "modern",
  "color_theme": "indigo",
  "title_slide": {
    "title": "Lịch Sử Phát Triển Trí Tuệ Nhân Tạo",
    "subtitle": "Tạo bởi AI Slide Generator"
  },
  "content_slide_footer": "AI Slide Generator",
  "deck": {
    "title": "Lịch Sử Phát Triển Trí Tuệ Nhân Tạo",
    "slides": [
      {
        "index": 0,
        "title": "Sự Khởi Đầu Của AI (1950 - 1956)",
        "bullets": [
          "Phép thử Turing (Turing Test) năm 1950 đặt nền móng định nghĩa trí tuệ máy.",
          "Hội thảo Dartmouth năm 1956 chính thức khai sinh thuật ngữ 'Artificial Intelligence'.",
          "Những kỳ vọng ban đầu rất lớn nhưng bị giới hạn bởi năng lực tính toán của máy tính."
        ],
        "notes": "Nhấn mạnh vai trò của Alan Turing và John McCarthy trong giai đoạn khai sơn phá thạch này.",
        "layout": "text_image",
        "primary_visual": "image",
        "likely_multi_pptx_slides": false,
        "table": null,
        "chart": null,
        "image": {
          "path": "/home/datn/demodoan/outputs/0d9c4456_0.png",
          "url": "/outputs/0d9c4456_0.png",
          "base64": null,
          "mime": "image/png"
        }
      },
      {
        "index": 1,
        "title": "Thống Kê Ứng Dụng AI Hiện Nay",
        "bullets": [
          "Biểu đồ phân bổ tỷ lệ doanh nghiệp sử dụng AI theo từng lĩnh vực năm 2026."
        ],
        "notes": "",
        "layout": "text_chart",
        "primary_visual": "chart",
        "likely_multi_pptx_slides": false,
        "table": null,
        "chart": {
          "type": "column",
          "title": "Tỷ lệ ứng dụng AI (%)",
          "categories": ["Y tế", "Tài chính", "Sản xuất", "Giáo dục"],
          "series": [
            {
              "name": "Tỷ lệ %",
              "values": [45.2, 58.0, 35.1, 28.4]
            }
          ]
        },
        "image": null
      }
    ]
  }
}
```

---

## 2. API Tạo File PowerPoint `.pptx` Toàn Diện (Bất Đồng Bộ)

API này dùng để gửi yêu cầu sinh file PowerPoint hoàn chỉnh. Với nội dung dài hoặc yêu cầu sinh ảnh AI nặng, API sẽ tự động đẩy vào hàng đợi bất đồng bộ (Redis Queue) để xử lý nhằm tránh timeout.

* **Endpoint:** `/api/generate-slide-full` (hoặc alias `/generate`)
* **Method:** `POST`
* **Content-Type:** `multipart/form-data` hoặc `application/x-www-form-urlencoded`

### Tham số đầu vào (Request Body)
*(Tương tự như API ở mục 1, ngoại trừ việc không có trường `include_image_base64`)*

### Ví dụ Response trả về ngay lập tức (Chờ xử lý bất đồng bộ)
```json
{
  "task_id": "0d9c4456-5be5-4d7a-be92-e427cf664188",
  "status": "processing",
  "message": "Processing via Redis worker (vLLM)...",
  "check_status_url": "/api/status/0d9c4456-5be5-4d7a-be92-e427cf664188"
}
```

---

## 3. API Kiểm Tra Trạng Thái Sinh Slide (Polling API)

FE sử dụng API này để cập nhật thanh tiến trình (progress bar) và biết khi nào slide được tạo xong hoặc gặp lỗi.

* **Endpoint:** `/api/status/{task_id}`
* **Method:** `GET`

### Phản hồi mẫu khi đang xử lý (Processing):
```json
{
  "task_id": "0d9c4456-5be5-4d7a-be92-e427cf664188",
  "status": "processing",
  "progress": 35,
  "result": {
    "chunks": {
      "done": 2,
      "total": 6
    }
  }
}
```

### Phản hồi mẫu khi hoàn thành (Completed):
```json
{
  "task_id": "0d9c4456-5be5-4d7a-be92-e427cf664188",
  "status": "completed",
  "progress": 100,
  "result": {
    "download_url": "/outputs/lich_su_phat_trien_tri_tue_nhan_tao_0d9c4456.pptx",
    "view_url": "/api/view-slide/0d9c4456-5be5-4d7a-be92-e427cf664188"
  }
}
```
* **`download_url`**: Đường dẫn tĩnh để người dùng tải file trực tiếp. Ghép thêm domain của server: `http://20.196.129.89:8000/outputs/lich_su_phat_trien_tri_tue_nhan_tao_0d9c4456.pptx`
* **`view_url`**: Đường dẫn API để tải file (sẽ gọi trực tiếp đến API tải file ở mục 4).

### Phản hồi mẫu khi gặp lỗi (Error):
```json
{
  "task_id": "0d9c4456-5be5-4d7a-be92-e427cf664188",
  "status": "error",
  "progress": 0,
  "result": {
    "error": "Chi tiết thông tin lỗi từ Server..."
  }
}
```

---

## 4. API Tải File PowerPoint (.pptx)

* **Endpoint:** `/api/view-slide/{task_id}`
* **Method:** `GET`
* **Response:** Trả về file nhị phân PPTX để trình duyệt tự động kích hoạt tiến trình tải xuống.

---

## 5. API Dừng / Hủy Tiến Trình Đang Chạy

Khi người dùng nhấn nút "Dừng" (Cancel) ở giao diện, FE gọi API này để báo server hủy tác vụ, giải phóng tài nguyên CPU/GPU.

* **Endpoint:** `/api/cancel/{task_id}`
* **Method:** `POST`
