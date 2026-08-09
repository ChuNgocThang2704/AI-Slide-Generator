# LecGen API Documentation Index

Tep nay truoc day mo ta API AI cu, bao gom endpoint sinh PPTX truc tiep va IP deploy co dinh. Luong do khong con la contract cua he thong hien tai.

## Tai lieu dung hien nay

### Frontend -> Java Backend

Doc chinh:

- [README_FE_API.md](README_FE_API.md): checklist tich hop nhanh.
- [fe_api_spec.md](fe_api_spec.md): request/response contract day du.
- [back-end/document-service/document_api_spec.md](back-end/document-service/document_api_spec.md): chi tiet Document Service.

FE chi goi API Gateway:

```txt
POST /api/document/projects
GET  /api/document/projects/{projectId}/progress
GET  /api/document/projects/{projectId}/pages
POST /api/document/projects/{projectId}/revise
POST /api/document/projects/{projectId}/pages/sync
```

### Java Backend -> AI Service

Doc chinh:

- [ai-service/api_specification.md](ai-service/api_specification.md)
- [ai-service/README.md](ai-service/README.md)

Endpoint noi bo:

```txt
POST /api/generate-slide-spec
POST /api/revise-slide-spec
GET  /api/status/{task_id}
POST /api/cancel/{task_id}
```

AI Service tra deck JSON. FE render/editor va xuat PDF/PPTX; AI Service khong con la noi FE yeu cau sinh file PPTX hoan chinh.

## Nguyen tac revise

- FE gui `revisionScope="auto"` va prompt tu nhien.
- `contextSlideNumber` chi la context; AI co the sua slide khac neu prompt noi ro.
- Sau khi completed, FE tai lai toan bo `/pages`.
- BE giu task thanh cong cu neu revision moi that bai.

## Base URL

Khong ghi IP deploy co dinh trong source. Local Gateway mac dinh `http://localhost:8080`; AI Service noi bo mac dinh `http://localhost:8000`. Production lay URL tu `.env`.
