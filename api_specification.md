# Mục lục tài liệu API LecGen

File này trước đây mô tả API AI cũ, gồm endpoint sinh PPTX trực tiếp và IP triển khai cố định. Luồng đó không còn là contract của hệ thống hiện tại.

## Frontend -> Java Backend

Tài liệu chính:

- [README_FE_API.md](README_FE_API.md): checklist tích hợp nhanh.
- [fe_api_spec.md](fe_api_spec.md): request/response contract đầy đủ.
- [back-end/document-service/document_api_spec.md](back-end/document-service/document_api_spec.md): chi tiết Document Service.

FE chỉ gọi API Gateway:

```txt
POST /api/document/projects
GET  /api/document/projects/{projectId}/progress
GET  /api/document/projects/{projectId}/pages
POST /api/document/projects/{projectId}/revise
POST /api/document/projects/{projectId}/pages/sync
```

## Java Backend -> AI Service

Tài liệu chính:

- [ai-service/api_specification.md](ai-service/api_specification.md)
- [ai-service/README.md](ai-service/README.md)

Endpoint nội bộ:

```txt
POST /api/generate-slide-spec
POST /api/revise-slide-spec
GET  /api/status/{task_id}
POST /api/cancel/{task_id}
```

AI Service trả deck JSON. FE chịu trách nhiệm render/editor và xuất PDF/PPTX; FE không yêu cầu AI Service sinh file PPTX hoàn chỉnh.

## Nguyên tắc revise

- FE gửi `revisionScope="auto"` và prompt tự nhiên.
- `contextSlideNumber` chỉ là context; AI có thể sửa slide khác nếu prompt chỉ định rõ.
- Sau khi hoàn thành, FE tải lại toàn bộ `/pages`.
- BE giữ task thành công cũ nếu revision mới thất bại.

## Base URL

Không ghi IP deploy cố định trong source. Gateway local mặc định là `http://localhost:8080`; AI Service nội bộ mặc định là `http://localhost:8000`. Production lấy URL từ `.env`.
