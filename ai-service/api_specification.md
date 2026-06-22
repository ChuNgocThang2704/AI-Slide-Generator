# AI Service API Specification

Tài liệu này chỉ mô tả các API BE/FE cần tích hợp. Các API/debug endpoint nội bộ không nằm trong tài liệu này.

Base URL ví dụ:

```txt
http://localhost:8000
```

Trong môi trường deploy, thay bằng domain/IP của AI Service.

## Tổng Quan Luồng Tích Hợp

FE/BE nên dùng luồng bất đồng bộ:

1. Gửi yêu cầu tạo slide bằng `POST /api/generate-slide-spec` hoặc `POST /api/generate-slide-full`.
2. API trả ngay `task_id`.
3. FE poll `GET /api/status/{task_id}` để cập nhật tiến độ.
4. Khi `status = completed`, đọc `result`.
5. Nếu sinh PPTX, dùng `download_url` hoặc `GET /api/view-slide/{task_id}` để tải file.

Các trạng thái chính:

```txt
pending | processing | completed | error | cancelled
```

## 1. Tạo Slide JSON Cho FE

API này tạo slide dạng JSON để FE render/preview/edit.

```txt
POST /api/generate-slide-spec
Content-Type: multipart/form-data
```

### Request Fields

Truyền ít nhất một trong hai field: `text`, `file`.

| Field | Type | Required | Mô tả |
|---|---:|---:|---|
| `text` | string | No | Prompt hoặc nội dung đầu vào dạng text. |
| `file` | file | No | File nguồn. Hỗ trợ `.docx`, `.pdf`, `.txt`. |
| `plan` | string | No | Gói giới hạn tài nguyên: `free`, `pro`, `ultra`. Mặc định `pro`. |
| `slide_count` | integer | No | Số slide mong muốn. Nếu truyền, service cố gắng trả đúng số slide. |
| `generate_images` | string | No | `"true"` hoặc `"false"`. Mặc định `"false"`. |
| `image_limit` | integer | No | Số ảnh tối đa được gắn vào deck. Chỉ có ý nghĩa khi `generate_images=true`. |

### Request Ví Dụ

```bash
curl -X POST "http://localhost:8000/api/generate-slide-spec" \
  -F "text=Tạo 4 slide tiếng Việt về bãi đỗ xe thông minh trong trường đại học" \
  -F "plan=pro" \
  -F "slide_count=4" \
  -F "generate_images=false"
```

### Response Ngay Khi Submit

API này xử lý bất đồng bộ, nên response ban đầu chưa chứa deck cuối cùng.

```json
{
  "task_id": "49f8685f-3971-49f6-a984-0bae0fbcb1ef",
  "status": "processing",
  "message": "Processing JSON Spec asynchronously in BackgroundTasks.",
  "check_status_url": "/api/status/49f8685f-3971-49f6-a984-0bae0fbcb1ef"
}
```

Sau đó FE poll:

```txt
GET /api/status/{task_id}
```

### Result Khi Hoàn Thành

Khi `GET /api/status/{task_id}` trả `status = completed`, deck JSON nằm trong `result`.

```json
{
  "status": "completed",
  "progress": 100,
  "result": {
    "task_id": "49f8685f-3971-49f6-a984-0bae0fbcb1ef",
    "status": "completed",
    "mode": "json_spec",
    "spec_version": "1.2",
    "slide_preset": "modern",
    "color_theme": "modern",
    "title_slide": {
      "title": "Bãi đỗ xe thông minh trong trường đại học",
      "subtitle": "AI Slide Generator"
    },
    "content_slide_footer": "AI Slide Generator",
    "deck": {
      "title": "Bãi đỗ xe thông minh trong trường đại học",
      "slides": [
        {
          "index": 0,
          "title": "Tổng quan hệ thống bãi đỗ xe thông minh",
          "bullets": [
            "Hệ thống giúp sinh viên biết tình trạng chỗ đỗ xe theo thời gian thực.",
            "Cảm biến IoT ghi nhận trạng thái từng vị trí đỗ và gửi dữ liệu về dashboard.",
            "Ban quản lý có thể theo dõi tải sử dụng và tối ưu vận hành bãi xe."
          ],
          "notes": "Ở slide này, em sẽ trình bày tổng quan về hệ thống bãi đỗ xe thông minh...",
          "chart": null,
          "table": null,
          "image": null,
          "layout": "text_only",
          "primary_visual": null,
          "likely_multi_pptx_slides": false
        }
      ]
    }
  }
}
```

### Slide Object

Mỗi item trong `result.deck.slides` có dạng:

| Field | Type | Mô tả |
|---|---:|---|
| `index` | integer | Thứ tự slide, bắt đầu từ `0`. |
| `title` | string | Tiêu đề slide. |
| `bullets` | string[] | Nội dung chính để render trên slide. |
| `notes` | string | Ghi chú/người nói. |
| `chart` | object/null | Spec biểu đồ nếu slide có chart. |
| `table` | object/null | Spec bảng nếu slide có table. |
| `image` | object/null | Thông tin ảnh nếu slide có ảnh. |
| `layout` | string | Gợi ý layout: `text_only`, `text_image`, `text_chart`, `text_table`. |
| `primary_visual` | string/null | Visual chính: `image`, `chart`, `table`, hoặc `null`. |
| `likely_multi_pptx_slides` | boolean | Gợi ý slide có thể bị tách khi render PPTX vì nhiều nội dung. |

### Chart Object

`chart` có thể khác nhẹ theo loại biểu đồ, nhưng thường có dạng:

```json
{
  "type": "column",
  "title": "Mức độ hài lòng",
  "categories": ["Moodle", "Google Classroom", "Canvas"],
  "series": [
    {
      "name": "Điểm",
      "values": [7.8, 8.5, 8.2]
    }
  ]
}
```

FE nên render tolerant: nếu thiếu chart hoặc chart không hỗ trợ thì bỏ qua hoặc hiển thị fallback.

### Table Object

`table` thường có dạng:

```json
{
  "title": "So sánh nền tảng học trực tuyến",
  "headers": ["Tiêu chí", "Moodle", "Google Classroom", "Canvas"],
  "rows": [
    ["Chi phí", "Thấp", "Miễn phí cơ bản", "Cao"],
    ["Tùy biến", "Cao", "Trung bình", "Cao"]
  ]
}
```

### Image Object

`image` có dạng:

```json
{
  "path": "E:\\DemoDoan\\ai-service\\outputs\\images\\task_0_external.jpg",
  "url": "/outputs/images/task_0_external.jpg",
  "mime": null
}
```

FE/BE nên dùng `image.url`. AI Service không yêu cầu FE gửi theme; giao diện/theme do FE tự quyết.

## 2. Kiểm Tra Trạng Thái Task

FE dùng API này để poll tiến độ và lấy kết quả cuối cùng.

```txt
GET /api/status/{task_id}
```

### Processing Response

```json
{
  "status": "processing",
  "progress": 65,
  "result": {
    "chunks": {
      "done": 3,
      "total": 5
    }
  }
}
```

Khi đang sinh ảnh, `result` có thể có:

```json
{
  "images": {
    "done": 1,
    "total": 2
  }
}
```

### Completed Response Cho JSON Spec

```json
{
  "status": "completed",
  "progress": 100,
  "result": {
    "task_id": "...",
    "mode": "json_spec",
    "deck": {
      "title": "...",
      "slides": []
    }
  }
}
```

### Completed Response Cho PPTX

```json
{
  "status": "completed",
  "progress": 100,
  "result": {
    "download_url": "/outputs/deck_name_taskid.pptx",
    "view_url": "/api/view-slide/taskid"
  }
}
```

### Error Response

```json
{
  "status": "error",
  "progress": 0,
  "result": {
    "error": "Error message"
  }
}
```

### Cancelled Response

```json
{
  "status": "cancelled",
  "progress": 0,
  "result": {
    "message": "Task cancelled by user"
  }
}
```

## 3. Tạo File PPTX

API này tạo file PowerPoint thật. Luồng vẫn là async giống JSON spec.

```txt
POST /api/generate-slide-full
Content-Type: multipart/form-data
```

### Request Fields

| Field | Type | Required | Mô tả |
|---|---:|---:|---|
| `text` | string | No | Prompt hoặc nội dung đầu vào dạng text. |
| `file` | file | No | File nguồn `.docx`, `.pdf`, `.txt`. |
| `plan` | string | No | `free`, `pro`, `ultra`. Mặc định `pro`. |
| `slide_count` | integer | No | Số slide mong muốn. |
| `image_limit` | integer | No | Số ảnh tối đa. |
| `generate_images` | string | No | `"true"` hoặc `"false"`. |

Truyền ít nhất một trong hai field: `text`, `file`.

### Request Ví Dụ

```bash
curl -X POST "http://localhost:8000/api/generate-slide-full" \
  -F "text=Tạo 5 slide tiếng Việt về lịch sử phát triển Internet tại Việt Nam" \
  -F "plan=pro" \
  -F "slide_count=5" \
  -F "generate_images=false"
```

### Response Ngay Khi Submit

```json
{
  "task_id": "bc9015eb-db85-4a36-b7a8-2631f57a9525",
  "status": "processing",
  "message": "Processing asynchronously in BackgroundTasks.",
  "check_status_url": "/api/status/bc9015eb-db85-4a36-b7a8-2631f57a9525"
}
```

Sau đó poll:

```txt
GET /api/status/{task_id}
```

Khi xong:

```json
{
  "status": "completed",
  "progress": 100,
  "result": {
    "download_url": "/outputs/deck_name_taskid.pptx",
    "view_url": "/api/view-slide/taskid"
  }
}
```

## 4. Tải Hoặc Xem File PPTX

```txt
GET /api/view-slide/{task_id}
```

Response là file `.pptx`.

FE có thể:

- mở `view_url` trong tab mới,
- hoặc tải từ `download_url`,
- hoặc gọi endpoint này và xử lý blob.

## 5. Hủy Task

```txt
POST /api/cancel/{task_id}
```

### Response

```json
{
  "task_id": "49f8685f-3971-49f6-a984-0bae0fbcb1ef",
  "status": "cancelled",
  "message": "Task cancellation requested"
}
```

Lưu ý: hủy task là best-effort. Nếu task đã gần hoàn thành hoặc đang gọi API ngoài, việc hủy có thể không dừng ngay lập tức.

## Khuyến Nghị Cho FE

- Luôn poll `/api/status/{task_id}` sau khi submit.
- Không giả định `POST /api/generate-slide-spec` trả deck ngay.
- Với JSON spec, đọc dữ liệu tại `status.result.deck`.
- Với PPTX, đọc `status.result.download_url` hoặc `status.result.view_url`.
- Render tolerant: `chart`, `table`, `image` có thể là `null`.
- Hiển thị kịch bản thuyết trình từ trường `notes`.
- Nếu `generate_images=true`, thời gian xử lý sẽ lâu hơn đáng kể.
- Không phụ thuộc vào field mới chưa document; service có thể thêm field nhưng sẽ cố gắng không đổi/xóa field cũ.
