# Hướng dẫn nhanh tích hợp FE

Contract đầy đủ:

- [fe_api_spec.md](./fe_api_spec.md) là nguồn chuẩn cho FE.
- [back-end/document-service/document_api_spec.md](./back-end/document-service/document_api_spec.md) mô tả chi tiết Document Service.

## Base URL

Gateway local:

```txt
http://localhost:8080
```

FE chỉ gọi Java BE qua API Gateway, không gọi Python AI Service trực tiếp. Khi FE và Gateway dùng cùng hostname, để trống `VITE_API_BASE_URL` và đặt `VITE_GATEWAY_PORT=8080`; cách này dùng được cho cả localhost và IP deploy.

## Luồng chính

Tạo slide:

```txt
POST /api/document/projects
GET  /api/document/projects/{projectId}/progress
GET  /api/document/projects/{projectId}/pages
```

Dùng lại tài liệu đã upload:

```txt
GET  /api/document/source-documents
POST /api/document/projects với sourceDocId/file metadata và prompt có ý nghĩa
```

Sửa slide:

```txt
POST /api/document/projects/{projectId}/revise
GET  /api/document/projects/{projectId}/progress
GET  /api/document/projects/{projectId}/pages
```

## Quy tắc revise

- Gửi `revisionScope="auto"` cho ô prompt tự nhiên.
- `contextSlideNumber` là slide đang mở (1-based), chỉ đóng vai trò context và không khóa target.
- AI có thể chọn slide khác, nhiều slide hoặc toàn bộ deck theo `revisionPrompt`.
- Chỉ dùng `slideNumber`/`slideIndex` cho control chương trình cần khóa cứng target.
- Sau khi hoàn thành, tải lại toàn bộ `/pages` và thay state local; không merge delta.
- Nếu revise thất bại, BE khôi phục task của deck thành công trước đó để người dùng sửa tiếp.

Quota revise mỗi ngày: Free `2`, Pro `10`, Ultra `30`. BE xác định plan từ tài khoản, task thất bại được hoàn quota; FE không tự gửi plan.

## Trách nhiệm của FE

- Gửi prompt và metadata file cho BE.
- Với file, yêu cầu người dùng nhập prompt nêu mục đích và phạm vi; không tự tạo câu chung chung như `Tạo slide từ file`.
- Poll đến khi project hoàn thành rồi tải pages.
- Render trực tiếp các trường `title`, `bullets`, `notes`, `table`, `chart`, `imageUrl`, `layout`.
- Autosave chỉnh sửa thủ công qua pages/sync.
- Refresh access token trước khi coi một phản hồi 401 là lỗi đăng nhập vĩnh viễn.
- FE sở hữu editor và export PDF/PPTX.

## FE không nên làm

- Không gọi AI Service trực tiếp.
- Không gửi `generate_images`; AI Service bật ảnh mặc định.
- Không suy luận bảng/biểu đồ từ bullet; dùng structured fields.
- Không tự chọn plan thay người dùng đã xác thực.

## Thứ tự render visual

```txt
table != null       -> render table
else chart != null  -> render chart
else imageUrl set   -> render image
else                -> render text only
```

## Hành vi đã kiểm thử

- Sinh deck từ prompt hoặc tài liệu.
- Tự nhận diện text, table, chart và image.
- Sửa title, nội dung, bảng, biểu đồ và ảnh.
- Giữ nguyên slide ngoài phạm vi.
- Thêm, xóa, sắp xếp và sửa toàn deck.
- Hoàn trả bảng/chart đầy đủ sau revise.
- Loại chart không có dữ liệu hợp lệ và xóa câu hứa hẹn visual không tồn tại.
- Không cho quá trình mở rộng nội dung tự bịa thống kê hoặc kết quả nghiên cứu.
