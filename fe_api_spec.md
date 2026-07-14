# FE API Spec - Slide Generation and Revision

This document is the contract FE should use when integrating the current slide flow.

FE calls the Java BE through API Gateway only. FE must not call the Python AI Service directly.

## Base URL

Local gateway:

```txt
http://localhost:8080
```

API prefix:

```txt
/api/document
```

Required headers for protected APIs:

```http
Authorization: Bearer <access_token>
Content-Type: application/json
Accept: application/json
```

Common response wrapper:

```json
{
  "code": 1000,
  "message": "Success",
  "data": {}
}
```

## Recommended FE Flow

Create from prompt:

```txt
1. POST /api/document/projects
2. Poll GET /api/document/projects/{projectId}/progress
3. When data.projectStatus = 1 and data.aiStatus = "completed":
4. GET /api/document/projects/{projectId}/pages
5. Render pages from JSON
```

Create from file:

```txt
1. POST /api/document/source-documents/upload
2. POST /api/document/projects with fileUrl/fileName/fileSize and optional prompt
3. Poll progress
4. Fetch pages
```

Revise existing deck:

```txt
1. POST /api/document/projects/{projectId}/revise
2. Poll progress
3. Fetch pages again and replace local slide state
```

## 1. Create Slide Project

```http
POST /api/document/projects
```

Request body:

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

Notes:

- `prompt` is the main natural-language requirement.
- For file input, upload the file first, then send `fileUrl`, `fileName`, and `fileSize`.
- FE does not send `generate_images`. AI image generation is enabled by default inside AI Service.
- FE does not send table/chart/image flags. AI Service detects visual type from prompt/content.

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

Project status used by this flow:

```txt
0 = processing
1 = completed
2 = failed
```

## 2. Poll Project Progress

```http
GET /api/document/projects/{projectId}/progress
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

FE should treat the deck as ready when:

```ts
progress.data.projectStatus === 1 && progress.data.aiStatus === "completed"
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
GET /api/document/projects/{projectId}/pages
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

Render priority:

```txt
1. If table is not null, render table.
2. Else if chart is not null, render chart.
3. Else if imageUrl has value, render image.
4. Else render text-only slide.
```

## 4. Revise Slides With Natural Language

```http
POST /api/document/projects/{projectId}/revise
```

Revision quota is enforced by BE from the authenticated user's subscription:

| Plan | Revisions per day |
|---|---:|
| Free | 2 |
| Pro | 10 |
| Ultra | 30 |

When exhausted, the endpoint returns `QUOTA_EXCEEDED` without creating an AI
task. Failed AI revisions are refunded. The quota appears under
`MAX_REVISIONS_PER_DAY` in the existing subscription quota response. FE does
not send a plan value; the Java BE resolves it from the authenticated user.

Request body:

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
  "revisionPrompt": "Anh slide 3 chua khop, doi thanh bai do xe dai hoc hien dai co cam bien IoT va bang dien tu"
}
```

Field notes:

| Field | Required | Description |
|---|---:|---|
| `revisionPrompt` | Yes | Natural-language edit request. |
| `revisionScope` | No | `auto`, `slide`, or `deck`. Send `slide` when the editor has one selected slide; use `deck` only for an explicit full-deck rewrite. |
| `slideNumber` | No | 1-based selected slide number. Prefer this field when FE has a selected slide. |
| `slideIndex` | No | 0-based selected slide index. Do not send both `slideIndex` and `slideNumber`. |
| `imageLimit` | No | Optional image-generation cap. |
| `generateImages` | No | Deprecated for FE. Do not send unless intentionally disabling image generation. |

Target precedence:

- A structured `slideNumber`/`slideIndex` from FE takes precedence over slide numbers inferred from text.
- For one selected slide, send `revisionScope="slide"` and `slideNumber`.
- For edits mentioning multiple slides, current Java BE has no multi-target array field. Send the slide numbers in `revisionPrompt` with `revisionScope="auto"`.
- For a full-deck rewrite, send `revisionScope="deck"` and omit slide target fields.

Response when submitted:

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

After this, poll progress and fetch pages again.

Supported revise examples:

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

Behavior:

- If user asks to edit one slide, AI Service preserves every other slide, including text, table, chart, image, and layout.
- A title-only request changes only the title field unless the prompt explicitly requests another change.
- Table revisions return the complete final table, not a row/cell delta; FE renders the returned headers and rows as-is.
- Chart revisions return the complete final chart, including type, labels, values/series, and unit.
- Image revisions keep slide text unchanged unless the prompt also asks to edit text.
- If user asks to add a slide, old slides are preserved and the new slide is appended.
- If user asks to delete a slide, remaining slides are preserved and their indexes are normalized.
- Split/merge/reorder/full-deck requests may change multiple slides or the slide count.
- After revise, BE replaces `slide_pages` with the new AI result. FE should reload pages.

## 5. Table Schema

When `table` is not null:

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

FE should render:

```txt
table.headers as header row
table.rows as body rows
```

## 6. Chart Schema

Single-series chart:

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

Multi-series chart:

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
    },
    {
      "name": "Nam 2026",
      "values": [12, 24, 36]
    }
  ],
  "unit": "number",
  "is_percent": false
}
```

FE chart rules:

```txt
chart type = chart.chart_type || chart.type
x axis labels = chart.labels || chart.categories
if chart.series exists, render multi-series
else render chart.values
```

Common chart types:

```txt
bar
column
line
pie
radar
```

## 7. Image Field

BE returns image URL in:

```txt
imageUrl
```

Example:

```json
{
  "imageUrl": "http://localhost:8000/outputs/images/task_4_external.jpg",
  "layout": "text_image",
  "primaryVisual": "image"
}
```

FE can render `imageUrl` directly. It may be an absolute URL or a URL resolved by BE from AI Service output.

## 8. Upload Source Document

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

Then create project:

```json
{
  "prompt": "Tao slide tu tai lieu nay, tap trung vao ket qua va khuyen nghi.",
  "fileUrl": "https://...",
  "fileName": "report.pdf",
  "fileSize": 123456
}
```

## 9. Update Slide Page Manually

Use this when FE editor changes a slide manually, not through AI revise.

```http
POST /api/document/projects/{projectId}/pages/{pageId}
```

Request body can include partial fields:

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

## 10. Sync Multiple Pages

```http
POST /api/document/projects/{projectId}/pages/sync
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

## 11. Cancel Running Task

```http
POST /api/document/projects/{projectId}/cancel
```

Response:

```json
{
  "code": 1000,
  "message": "Success",
  "data": "Huy tac vu thanh cong"
}
```

Cancel is best-effort. FE should still poll progress after cancel if it needs final state.

## 12. Project List and Detail

List:

```http
GET /api/document/projects?page=0&size=10&search=
```

Detail:

```http
GET /api/document/projects/{projectId}
```

Delete:

```http
DELETE /api/document/projects
```

Delete body:

```json
[
  "project-id-1",
  "project-id-2"
]
```

## 13. FE Integration Notes

- FE should render from `/pages`, not from AI task result.
- FE should reload `/pages` after every successful revise.
- FE should not expose controls for slide count, image count, table/chart/image mode unless product requires it later.
- User-facing revise UI can be a single text box plus an optional selected slide context.
- For a selected slide, FE should send `revisionScope="slide"` and `slideNumber`; AI Service can infer scope only when no structured target is available.
- Do not merge a revise delta in FE. After completion, replace local slide state with the latest `/pages` response.
- Use the same project for subsequent revisions; BE tracks the newest completed AI task internally.
- FE should handle `table`, `chart`, and `imageUrl` as optional nullable fields.
- FE should not infer table/chart from bullet text. Use the structured fields only.
