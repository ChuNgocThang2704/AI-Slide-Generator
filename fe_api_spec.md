# FE API Spec - Slide Generation Flow

Base URL khi chạy local qua gateway:

```txt
http://localhost:8080
```

Tất cả API cần đăng nhập dùng header:

```http
Authorization: Bearer <access_token>
Content-Type: application/json
```

Response chung:

```json
{
  "code": 200,
  "message": null,
  "data": {}
}
```

## 1. Đăng ký

```http
POST /api/auth/register
```

Request:

```json
{
  "email": "user@example.com",
  "password": "12345678"
}
```

Response:

```json
{
  "code": 200,
  "data": "Create user successfully"
}
```

Ghi chú: user mới có thể cần verify email trước khi login, tùy môi trường.

## 2. Đăng nhập

```http
POST /api/auth/login
```

Request:

```json
{
  "email": "user@example.com",
  "password": "12345678"
}
```

Response:

```json
{
  "code": 200,
  "data": {
    "token": "access_token",
    "refreshToken": "refresh_token"
  }
}
```

FE lưu `data.token` để gọi các API bên dưới.

## 3. Tạo project slide từ prompt

```http
POST /api/document/projects
```

Request:

```json
{
  "prompt": "Tạo 3 slide tiếng Việt về lợi ích bãi đỗ xe thông minh trong trường đại học",
  "templateId": null,
  "sourceDocId": null
}
```

Response:

```json
{
  "code": 200,
  "data": {
    "id": "1954ca70-660c-43a7-aa50-97160f41e532",
    "name": "Tổng quan về Bãi đỗ xe thông minh trong trường đại học",
    "ownerId": "e4ecca90-9195-4f71-90ea-2412374f202d",
    "sourceDocId": null,
    "templateId": null,
    "initialPrompt": "Tạo 3 slide tiếng Việt về lợi ích...",
    "slideUrl": null,
    "status": 3,
    "createdAt": "2026-06-21T16:36:24.411362Z",
    "updatedAt": "2026-06-21T16:36:24.411362Z"
  }
}
```

Status project:

```txt
0 = DRAFT
1 = REVIEWING
2 = PROCESSING
3 = DONE
4 = FAILED
```

Hiện tại API này xử lý đồng bộ từ góc nhìn FE: BE sẽ chờ AI sinh xong, lưu DB xong rồi mới trả response. Vì vậy request có thể mất vài chục giây đến vài phút.

## 4. Upload file nguồn

```http
POST /api/document/source-documents/upload
Content-Type: multipart/form-data
```

Form field:

```txt
file=<pdf/docx/txt>
```

Response:

```json
{
  "code": 200,
  "data": {
    "fileName": "report.pdf",
    "fileUrl": "https://...",
    "fileSize": 123456
  }
}
```

Sau khi upload, FE tạo project bằng cách gửi kèm thông tin file:

```json
{
  "prompt": "Tạo slide từ tài liệu này",
  "fileUrl": "https://...",
  "fileName": "report.pdf",
  "fileSize": 123456
}
```

## 5. Lấy danh sách project

```http
GET /api/document/projects?page=0&size=10&search=
```

Response:

```json
{
  "code": 200,
  "data": {
    "page": 0,
    "size": 10,
    "totalElements": 1,
    "totalPages": 1,
    "items": [
      {
        "id": "1954ca70-660c-43a7-aa50-97160f41e532",
        "name": "Tổng quan về Bãi đỗ xe thông minh trong trường đại học",
        "status": 3,
        "createdAt": "2026-06-21T16:36:24.411362Z"
      }
    ]
  }
}
```

## 6. Lấy chi tiết project

```http
GET /api/document/projects/{projectId}
```

Response `data` là object `ProjectResponse` giống API tạo project.

## 7. Lấy danh sách slide pages

```http
GET /api/document/projects/{projectId}/pages
```

Response:

```json
{
  "code": 200,
  "data": [
    {
      "id": "slide-page-id",
      "projectId": "1954ca70-660c-43a7-aa50-97160f41e532",
      "pageIndex": 0,
      "title": "Khác với các bãi đỗ xe truyền thống",
      "bullets": [
        "Ý chính 1",
        "Ý chính 2"
      ],
      "notes": "Kịch bản thuyết trình cho slide này...",
      "chart": null,
      "table": null,
      "imageUrl": "http://localhost:8000/outputs/images/example.jpg",
      "layout": "text_image",
      "primaryVisual": "image",
      "likelyMultiPptxSlides": false,
      "createdAt": "2026-06-21T16:38:00Z",
      "updatedAt": "2026-06-21T16:38:00Z"
    }
  ]
}
```

Các layout thường gặp:

```txt
text_only
text_image
text_chart
text_table
```

FE nên ưu tiên render theo dữ liệu:

```txt
Nếu table != null -> render table
Nếu chart != null -> render chart
Nếu imageUrl có giá trị -> render image
Nếu không có visual -> render text only
```

## 8. Chart schema

Khi slide có chart, field `chart` là object JSON:

```json
{
  "type": "bar",
  "title": "Điểm trung bình theo môn",
  "labels": ["Toán", "Cấu trúc dữ liệu", "Mạng máy tính"],
  "series": [
    {
      "name": "Điểm TB",
      "values": [8.2, 7.8, 8.5]
    }
  ]
}
```

Chart type có thể gặp:

```txt
bar
column
line
pie
radar
```

## 9. Table schema

Khi slide có table, field `table` là object JSON:

```json
{
  "title": "So sánh trước và sau",
  "headers": ["Tiêu chí", "Trước", "Sau"],
  "rows": [
    ["Tìm chỗ đỗ", "Thủ công", "Tự động"],
    ["Thời gian", "Lâu", "Nhanh"]
  ]
}
```

FE nên render `headers` làm dòng đầu, `rows` làm nội dung.

## 10. Cập nhật slide page

```http
POST /api/document/projects/{projectId}/pages/{pageId}
```

Request có thể gửi một phần hoặc toàn bộ field:

```json
{
  "title": "Tiêu đề mới",
  "bullets": ["Ý 1", "Ý 2"],
  "notes": "Script mới",
  "chart": null,
  "table": null,
  "imageUrl": "http://...",
  "layout": "text_image",
  "primaryVisual": "image",
  "likelyMultiPptxSlides": false
}
```

Response `data` là slide page đã cập nhật.

## 11. Đồng bộ nhiều slide page

```http
POST /api/document/projects/{projectId}/pages/sync
```

Request:

```json
[
  {
    "id": "existing-page-id",
    "title": "Slide 1",
    "bullets": ["Ý 1"],
    "notes": "Script",
    "chart": null,
    "table": null,
    "imageUrl": "",
    "layout": "text_only",
    "primaryVisual": null,
    "likelyMultiPptxSlides": false
  }
]
```

Response `data` là danh sách slide pages sau khi sync.

## 12. Task logs

```http
GET /api/document/projects/{projectId}/task-logs
```

Response:

```json
{
  "code": 200,
  "data": [
    {
      "id": "task-log-id",
      "projectId": "project-id",
      "taskType": 0,
      "status": 2,
      "errorMessage": null,
      "startedAt": "2026-06-21T16:36:24Z",
      "completedAt": "2026-06-21T16:38:24Z",
      "createdAt": "2026-06-21T16:36:24Z"
    }
  ]
}
```

Task type:

```txt
0 = EXTRACT_TEXT
1 = GEN_IMAGE
2 = RENDER_PPTX
```

Task status:

```txt
0 = PENDING
1 = PROCESSING
2 = SUCCESS
3 = FAILED
```

## 13. Xóa project

```http
DELETE /api/document/projects
```

Request:

```json
[
  "project-id-1",
  "project-id-2"
]
```

Response:

```json
{
  "code": 200,
  "data": "Projects deleted successfully"
}
```

## FE Flow Khuyến Nghị

Flow tạo slide từ prompt:

```txt
1. Login -> lấy token
2. POST /api/document/projects
3. Lấy projectId từ response
4. GET /api/document/projects/{projectId}/pages
5. Render slides từ pages
```

Flow tạo slide từ file:

```txt
1. Login -> lấy token
2. POST /api/document/source-documents/upload
3. POST /api/document/projects với fileUrl/fileName/fileSize
4. GET /api/document/projects/{projectId}/pages
5. Render slides từ pages
```

Lưu ý quan trọng:

```txt
FE không gọi trực tiếp AI service.
FE chỉ gọi BE qua /api/document/** và /api/auth/**.
BE tự gọi AI, poll status AI, lưu DB, rồi trả JSON cho FE.
```
