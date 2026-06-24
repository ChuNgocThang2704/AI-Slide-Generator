# Tài Liệu API: Theo Dõi Tiến Độ & Hủy Tác Vụ Dự Án AI Slide Generator

Tài liệu này hướng dẫn chi tiết cách tích hợp 2 API quan trọng để **theo dõi tiến độ sinh slide của AI** và **hủy bỏ tác vụ sinh slide** đang chạy.

---

## Cấu Hình Chung

* **Base Gateway URL:** `http://localhost:8080` (hoặc domain gateway thực tế)
* **API Prefix:** `/api/document`
* **Header bắt buộc:**
  * `Authorization: Bearer <JWT_TOKEN>` (Token xác thực của người dùng)
  * `Accept: application/json`

---

## 1. API Lấy Tiến Độ Dự Án (Project Progress)

Dùng để FE thực hiện polling định kỳ (ví dụ: mỗi 2-3 giây) để cập nhật tiến độ sinh slide dạng thanh phần trăm (%) và trạng thái xử lý lên giao diện.

* **Endpoint:** `/api/document/projects/{id}/progress`
* **Method:** `GET`
* **Path Variable:**
  * `{id}` (UUID): ID của dự án cần lấy tiến trình.

### Ví dụ Request (CURL)

```bash
curl -X GET "http://localhost:8080/api/document/projects/550e8400-e29b-41d4-a716-446655440000/progress" \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "Accept: application/json"
```

### Chi Tiết Cấu Trúc Response Body (200 OK)

Phản hồi trả về có dạng bọc ngoài là `ApiResponse<ProjectProgressResponse>`:

```json
{
  "code": 1000,
  "message": "Success",
  "data": {
    "projectId": "550e8400-e29b-41d4-a716-446655440000",
    "aiTaskId": "ai-task-xyz-12345",
    "projectStatus": 0,
    "aiStatus": "processing",
    "progress": 35,
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
| `errorMessage` | String | Thông điệp lỗi chi tiết từ AI Engine nếu quá trình sinh slide bị lỗi (mặc định là `null`). |

---

### Các Kịch Bản Phản Hồi Ví Dụ

#### Kịch Bản A: Dự án đang chạy ngầm sinh slide
```json
{
  "code": 1000,
  "message": "Success",
  "data": {
    "projectId": "550e8400-e29b-41d4-a716-446655440000",
    "aiTaskId": "ai-task-xyz-12345",
    "projectStatus": 0,
    "aiStatus": "processing",
    "progress": 60,
    "errorMessage": null
  }
}
```

#### Kịch Bản B: Sinh slide thành công hoàn toàn
```json
{
  "code": 1000,
  "message": "Success",
  "data": {
    "projectId": "550e8400-e29b-41d4-a716-446655440000",
    "aiTaskId": "ai-task-xyz-12345",
    "projectStatus": 1,
    "aiStatus": "completed",
    "progress": 100,
    "errorMessage": null
  }
}
```
*(Gợi ý cho FE: Khi nhận được `projectStatus: 1` hoặc `aiStatus: "completed"`, có thể dừng polling tiến trình và gọi sang API lấy danh sách trang slide `/projects/{id}/pages` để hiển thị).*

#### Kịch Bản C: Gặp lỗi giới hạn ký tự gói FREE hoặc lỗi hệ thống từ AI
```json
{
  "code": 1000,
  "message": "Success",
  "data": {
    "projectId": "550e8400-e29b-41d4-a716-446655440000",
    "aiTaskId": "ai-task-xyz-12345",
    "projectStatus": 2,
    "aiStatus": "failed",
    "progress": 0,
    "errorMessage": "Độ dài nội dung vượt quá giới hạn của gói FREE (24835 > 5000 ký tự)."
  }
}
```

---

## 2. API Hủy Tác Vụ Sinh Slide (Cancel Project Task)

Dùng khi người dùng ấn nút **"Hủy" (Cancel)** trên giao diện khi đang đợi slide tạo. Hệ thống sẽ gửi lệnh hủy tới AI Engine để dừng sinh slide và chuyển trạng thái dự án thành `FAILED`.

* **Endpoint:** `/api/document/projects/{id}/cancel`
* **Method:** `POST`
* **Path Variable:**
  * `{id}` (UUID): ID của dự án cần hủy tác vụ.

### Ví dụ Request (CURL)

```bash
curl -X POST "http://localhost:8080/api/document/projects/550e8400-e29b-41d4-a716-446655440000/cancel" \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "Accept: application/json"
```

### Phản hồi thành công (Response 200 OK)

```json
{
  "code": 1000,
  "message": "Success",
  "data": "Hủy tác vụ thành công"
}
```

---

## Các Mã Lỗi Thường Gặp (Error Responses)

Nếu xảy ra lỗi xác thực hoặc nghiệp vụ, hệ thống trả về mã trạng thái HTTP tương ứng (401, 403, 404,...) kèm định dạng lỗi chung:

### 1. Lỗi Không Tìm Thấy Dự Án (HTTP 404 Not Found)
Xảy ra khi ID dự án truyền vào không tồn tại trong hệ thống.
```json
{
  "code": 2003,
  "message": "Không tìm thấy dự án",
  "data": null
}
```

### 2. Lỗi Không Có Quyền Truy Cập (HTTP 403 Forbidden)
Xảy ra khi người dùng hiện tại cố gắng truy vấn tiến độ hoặc hủy dự án thuộc sở hữu của tài khoản khác.
```json
{
  "code": 1005,
  "message": "Bạn không có quyền truy cập tài nguyên này",
  "data": null
}
```
