# Tài Liệu API: Theo Dõi Tiến Độ, Hủy Tác Vụ & Quản Lý Slide Page (Document Service)

Tài liệu này hướng dẫn chi tiết cách tích hợp các API quan trọng để **theo dõi tiến độ sinh slide của AI** (kèm chi tiết chunks/images), **hủy bỏ tác vụ sinh slide** và **quản lý dữ liệu Slide Page (bao gồm kịch bản thuyết trình `script`)**.

---

## Cấu Hình Chung

* **Base Gateway URL:** `http://localhost:8080` (hoặc domain gateway thực tế)
* **API Prefix:** `/api/document`
* **Header bắt buộc:**
  * `Authorization: Bearer <JWT_TOKEN>` (Token xác thực của người dùng)
  * `Accept: application/json`

---

## 1. API Lấy Tiến Độ Dự Án (Project Progress)

Dùng để FE thực hiện polling định kỳ (ví dụ: mỗi 2-3 giây) để cập nhật tiến độ sinh slide dạng thanh phần trăm (%), chi tiết tiến trình `chunks` hoặc `images` lên giao diện.

* **Endpoint:** `/api/document/projects/{id}/progress`
* **Method:** `GET`
* **Path Variable:**
  * `{id}` (UUID): ID của dự án cần lấy tiến trình.

### Chi Tiết Cấu Trúc Response Body (200 OK)

Phản hồi trả về có dạng bọc ngoài là `ApiResponse<ProjectProgressResponse>`:

```json
{
  "code": 1000,
  "message": "Success",
  "data": {
    "projectId": "550e8400-e29b-41d4-a716-446655440000",
    "aiTaskId": "fefe5469-9952-4714-b938-c651b3f911c7",
    "projectStatus": 0,
    "aiStatus": "processing",
    "progress": 45,
    "result": {
      "chunks": {
        "done": 13,
        "total": 18
      }
    },
    "errorMessage": null
  }
}
```

#### Giải thích các trường dữ liệu trong `data`:

| Trường | Kiểu dữ liệu | Mô tả |
| :--- | :--- | :--- |
| `projectId` | UUID | ID của dự án đang được truy vấn. |
| `aiTaskId` | String | ID tác vụ được sinh ra bởi AI Engine (có thể `null` ở giây đầu tiên khi vừa submit). |
| `projectStatus` | Integer | Trạng thái dự án dưới Database: <br>• `0`: `CREATE` (Đang khởi tạo/đang xử lý)<br>• `1`: `DONE` (Hoàn thành sinh slide)<br>• `2`: `FAILED` (Tạo slide thất bại) |
| `aiStatus` | String | Trạng thái trả về từ AI Engine: <br>• `"processing"`: Đang xử lý<br>• `"completed"`: AI hoàn tất sinh slide spec<br>• `"failed"` / `"error"`: AI xảy ra lỗi khi tạo |
| `progress` | Integer | Tiến độ phần trăm hoàn thành, nhận giá trị từ `0` đến `100`. |
| `result` | Object | **[MỚI]** Đối tượng chi tiết tiến trình từ AI Engine. Trong lúc xử lý văn bản sẽ trả về `chunks: { done, total }`, trong lúc sinh ảnh sẽ trả về `images: { done, total }`. |
| `errorMessage` | String | Thông điệp lỗi chi tiết từ AI Engine nếu quá trình sinh slide bị lỗi (mặc định là `null`). |

---

### Các Kịch Bản Phản Hồi Ví Dụ

#### Kịch Bản A: Đang trích xuất và cấu trúc hóa văn bản (Chunks Progress)
```json
{
  "code": 1000,
  "message": "Success",
  "data": {
    "projectId": "550e8400-e29b-41d4-a716-446655440000",
    "aiTaskId": "fefe5469-9952-4714-b938-c651b3f911c7",
    "projectStatus": 0,
    "aiStatus": "processing",
    "progress": 45,
    "result": {
      "chunks": {
        "done": 13,
        "total": 18
      }
    },
    "errorMessage": null
  }
}
```

#### Kịch Bản B: Đang sinh ảnh minh họa AI cho slide (Images Progress)
```json
{
  "code": 1000,
  "message": "Success",
  "data": {
    "projectId": "550e8400-e29b-41d4-a716-446655440000",
    "aiTaskId": "fefe5469-9952-4714-b938-c651b3f911c7",
    "projectStatus": 0,
    "aiStatus": "processing",
    "progress": 72,
    "result": {
      "images": {
        "done": 2,
        "total": 5
      }
    },
    "errorMessage": null
  }
}
```

#### Kịch Bản C: Sinh slide thành công hoàn toàn
```json
{
  "code": 1000,
  "message": "Success",
  "data": {
    "projectId": "550e8400-e29b-41d4-a716-446655440000",
    "aiTaskId": "fefe5469-9952-4714-b938-c651b3f911c7",
    "projectStatus": 1,
    "aiStatus": "completed",
    "progress": 100,
    "result": null,
    "errorMessage": null
  }
}
```

---

## 2. API Lấy & Cập Nhật Danh Sách Trang Slide (Slide Pages API)

### 🔹 Lấy danh sách các trang slide của dự án
* **Endpoint:** `/api/document/projects/{projectId}/pages`
* **Method:** `GET`

### 🔹 Phản hồi cấu trúc Slide Page (200 OK)
Mỗi trang slide trả về bao gồm nội dung, ghi chú (`notes`) và kịch bản thuyết trình (`script`):

```json
{
  "code": 1000,
  "message": "Success",
  "data": [
    {
      "id": "b7d19a2e-...",
      "projectId": "550e8400-e29b-41d4-a716-446655440000",
      "pageIndex": 0,
      "title": "Nguyên lý hoạt động của thuật toán Karp-Rabin",
      "bullets": [
        "Thuật toán Karp-Rabin sử dụng hàm băm để đơn giản hóa việc so sánh chuỗi.",
        "Phương pháp này kiểm tra sự tương đồng giữa hai chuỗi con một cách hiệu quả."
      ],
      "notes": "Chào mừng quý vị đến với phần trình bày về thuật toán Karp-Rabin...",
      "script": "Chào mừng quý vị đến với phần trình bày về thuật toán Karp-Rabin. Đây là một thuật toán tìm kiếm chuỗi mạnh mẽ...",
      "chart": null,
      "table": null,
      "imageUrl": "http://localhost:8000/outputs/images/fefe5469_1.jpg",
      "layout": "text_image",
      "primaryVisual": "image",
      "likelyMultiPptxSlides": false
    }
  ]
}
```

---

## 3. API Hủy Tác Vụ Sinh Slide (Cancel Project Task)

* **Endpoint:** `/api/document/projects/{id}/cancel`
* **Method:** `POST`

```json
{
  "code": 1000,
  "message": "Success",
  "data": "Hủy tác vụ thành công"
}
```
