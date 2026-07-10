# Document Service API Spec - Slide JSON Flow

This document describes the API that FE should call through API Gateway.

Base gateway URL:

```txt
http://localhost:8080
```

API prefix:

```txt
/api/document
```

Required header:

```http
Authorization: Bearer <JWT_TOKEN>
Accept: application/json
```

## Important Integration Rule

FE calls Document Service only. Document Service calls AI Service internally.

FE does not need to know or send AI-specific fields such as:

```txt
generate_images
source_task_id
target_slide_indices
target_slide_numbers
```

Image generation is enabled by default in AI Service. AI Service also decides whether a slide should be text, table, chart, or image.

## 1. Create Project And Start AI Generation

```http
POST /api/document/projects
Content-Type: application/json
```

Request:

```json
{
  "prompt": "Tao dung 4 slide tieng Viet ve he thong bai do xe thong minh. Slide 2 la bang so sanh, slide 3 la bieu do duong, slide 4 co anh minh hoa.",
  "templateId": null,
  "sourceDocId": null,
  "fileUrl": null,
  "fileName": null,
  "fileSize": null
}
```

Response:

```json
{
  "code": 1000,
  "message": "Success",
  "data": {
    "id": "57c354ca-cfde-40f9-8733-57bb69d303e5",
    "name": "He thong bai do xe thong minh",
    "ownerId": "986b8ebf-d232-4b22-a8e6-7e6af4d717cf",
    "sourceDocId": null,
    "templateId": null,
    "initialPrompt": "Tao dung 4 slide tieng Viet...",
    "slideUrl": null,
    "status": 0,
    "aiTaskId": null,
    "createdAt": "2026-07-10T08:00:00Z",
    "updatedAt": "2026-07-10T08:00:00Z"
  }
}
```

Project status in the current AI flow:

```txt
0 = processing
1 = completed
2 = failed
```

## 2. Get Project Progress

```http
GET /api/document/projects/{id}/progress
```

Processing response:

```json
{
  "code": 1000,
  "message": "Success",
  "data": {
    "projectId": "57c354ca-cfde-40f9-8733-57bb69d303e5",
    "aiTaskId": "95915ceb-eda2-4890-a954-efff6069c547",
    "projectStatus": 0,
    "aiStatus": "processing",
    "progress": 68,
    "result": {
      "images": {
        "done": 1,
        "total": 4
      }
    },
    "errorMessage": null
  }
}
```

Completed response:

```json
{
  "code": 1000,
  "message": "Success",
  "data": {
    "projectId": "57c354ca-cfde-40f9-8733-57bb69d303e5",
    "aiTaskId": "95915ceb-eda2-4890-a954-efff6069c547",
    "projectStatus": 1,
    "aiStatus": "completed",
    "progress": 100,
    "result": null,
    "errorMessage": null
  }
}
```

FE should consider the deck ready when:

```txt
projectStatus = 1
aiStatus = completed
```

Failed response:

```json
{
  "code": 1000,
  "message": "Success",
  "data": {
    "projectStatus": 2,
    "aiStatus": "failed",
    "progress": 0,
    "errorMessage": "AI error message"
  }
}
```

## 3. Get Slide Pages

```http
GET /api/document/projects/{id}/pages
```

Response:

```json
{
  "code": 1000,
  "message": "Success",
  "data": [
    {
      "id": "slide-page-id",
      "projectId": "57c354ca-cfde-40f9-8733-57bb69d303e5",
      "pageIndex": 0,
      "title": "Tong quan he thong",
      "bullets": [
        "He thong bai do xe thong minh tu dong hoa quy trinh ra vao.",
        "Camera, cam bien IoT va bang dien tu cap nhat du lieu theo thoi gian thuc."
      ],
      "notes": "Noi dung thuyet trinh cho slide.",
      "chart": null,
      "table": null,
      "imageUrl": null,
      "layout": "text_only",
      "primaryVisual": null,
      "likelyMultiPptxSlides": false,
      "createdAt": "2026-07-10T08:00:00Z",
      "updatedAt": "2026-07-10T08:00:00Z"
    }
  ]
}
```

Common layouts:

```txt
text_only
text_image
text_chart
text_table
```

Render rule:

```txt
table != null       -> render table
else chart != null  -> render chart
else imageUrl set   -> render image
else                -> render text only
```

## 4. Revise Project Slides

```http
POST /api/document/projects/{id}/revise
Content-Type: application/json
```

Request:

```json
{
  "revisionPrompt": "Sua rieng slide 4: doi anh thanh bai do xe trong truong dai hoc hien dai co camera ANPR, cam bien IoT va bang dien tu hien thi so cho trong. Giu nguyen cac slide con lai.",
  "revisionScope": "auto",
  "slideNumber": 4,
  "slideIndex": null,
  "imageLimit": null
}
```

Minimum request:

```json
{
  "revisionPrompt": "Sua slide 2 thanh bang so sanh ro rang hon"
}
```

Fields:

| Field | Required | Description |
|---|---:|---|
| `revisionPrompt` | Yes | Natural-language edit request. |
| `revisionScope` | No | `auto`, `slide`, or `deck`. Default/recommended: `auto`. |
| `slideNumber` | No | 1-based slide number. Useful when FE selected a slide. |
| `slideIndex` | No | 0-based slide index. |
| `imageLimit` | No | Optional cap for regenerated images. |
| `generateImages` | No | Deprecated for FE. AI Service defaults to image generation enabled. |

Response:

```json
{
  "code": 1000,
  "message": "Success",
  "data": {
    "id": "57c354ca-cfde-40f9-8733-57bb69d303e5",
    "status": 0,
    "aiTaskId": "64c7ea2d-2dcd-4768-991e-593736dbc600"
  }
}
```

After submit:

```txt
1. Poll GET /api/document/projects/{id}/progress
2. When completed, call GET /api/document/projects/{id}/pages
3. Replace FE slide state with the new pages
```

Supported behavior:

- Edit text/title/bullets of one slide.
- Regenerate image for one slide.
- Convert or update table/chart.
- Add new slides.
- Delete slides.
- Rewrite the full deck.

Examples:

```txt
Sua rieng slide 1: doi tieu de thanh "Tong quan he thong bai do xe thong minh". Giu nguyen cac slide con lai.
```

```txt
Sua rieng slide 2 thanh bang so sanh gom cot Tieu chi, Thu cong, Thong minh, Nhan xet.
```

```txt
Sua rieng slide 3: giu bieu do duong va cap nhat so lieu Q1 50%, Q2 62%, Q3 76%, Q4 88%.
```

```txt
Sua rieng slide 4: doi anh thanh bai do xe dai hoc co camera ANPR, cam bien IoT va bang dien tu.
```

```txt
Them 1 slide cuoi ve loi ich khi trien khai he thong bai do xe thong minh.
```

```txt
Xoa slide 3 vi noi dung chua can thiet, giu cac slide con lai.
```

## 5. Table Contract

```json
{
  "title": "Bang so sanh",
  "headers": ["Tieu chi", "Thu cong", "Thong minh", "Nhan xet"],
  "rows": [
    ["Toc do xu ly", "Cham", "Nhanh", "He thong thong minh tot hon"],
    ["Do chinh xac", "Thap", "Cao", "Giam sai sot"]
  ]
}
```

## 6. Chart Contract

Single-series:

```json
{
  "title": "Hieu qua su dung bai do xe theo quy",
  "chart_type": "line",
  "type": "line",
  "labels": ["Q1", "Q2", "Q3", "Q4"],
  "categories": ["Q1", "Q2", "Q3", "Q4"],
  "values": [50, 62, 76, 88],
  "unit": "percent",
  "is_percent": true
}
```

Multi-series:

```json
{
  "title": "So sanh hieu suat",
  "chart_type": "bar",
  "type": "bar",
  "labels": ["A", "B", "C"],
  "categories": ["A", "B", "C"],
  "series": [
    {
      "name": "Nam 2025",
      "values": [10, 20, 30]
    }
  ],
  "unit": "number",
  "is_percent": false
}
```

FE chart rule:

```txt
type = chart.chart_type || chart.type
labels = chart.labels || chart.categories
if chart.series exists, render multi-series; otherwise render chart.values
```

## 7. Source Document Upload

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
  "code": 1000,
  "message": "Success",
  "data": {
    "fileName": "report.pdf",
    "fileUrl": "https://...",
    "fileSize": 123456
  }
}
```

## 8. Manual Slide Page Update

```http
POST /api/document/projects/{projectId}/pages/{pageId}
```

Request can be partial:

```json
{
  "title": "Tieu de moi",
  "bullets": ["Y 1", "Y 2"],
  "notes": "Script moi",
  "chart": null,
  "table": null,
  "imageUrl": "http://...",
  "layout": "text_image",
  "primaryVisual": "image",
  "likelyMultiPptxSlides": false
}
```

## 9. Sync Slide Pages

```http
POST /api/document/projects/{id}/pages/sync
```

Request:

```json
[
  {
    "id": "existing-page-id",
    "title": "Slide 1",
    "bullets": ["Y 1"],
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

## 10. Cancel Task

```http
POST /api/document/projects/{id}/cancel
```

Response:

```json
{
  "code": 1000,
  "message": "Success",
  "data": "Huy tac vu thanh cong"
}
```

## 11. Other Project APIs

```http
GET /api/document/projects?page=0&size=10&search=
GET /api/document/projects/{id}
DELETE /api/document/projects
GET /api/document/projects/{id}/task-logs
GET /api/document/projects/{id}/exports
```
