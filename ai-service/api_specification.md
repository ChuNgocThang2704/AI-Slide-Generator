# AI Service API Specification

Tai lieu nay mo ta cac API BE/FE can tich hop voi AI Service de sinh va sua slide dang JSON. BE/FE chi can xu ly data output; toan bo xu ly AI nam trong AI Service.

Base URL vi du:

```txt
http://localhost:8000
```

Trong moi truong deploy, thay bang domain/IP cua AI Service.

## Tong Quan Luong Tich Hop

Luong chinh:

1. BE/FE gui prompt hoac file den `POST /api/generate-slide-spec`.
2. AI Service tra ngay `task_id`.
3. BE/FE poll `GET /api/status/{task_id}`.
4. Khi `status = completed`, doc deck JSON tai `result.deck`.
5. Neu nguoi dung yeu cau sua, goi `POST /api/revise-slide-spec`.
6. Poll task revise qua `GET /api/status/{task_id}` va render lai `result.deck`.

Trang thai task:

```txt
pending | processing | completed | error | cancelled
```

## 1. Generate Slide Spec

Tao deck slide dang JSON de FE render/edit/export.

```txt
POST /api/generate-slide-spec
Content-Type: multipart/form-data
```

### Request Fields

Truyen it nhat mot trong hai field: `text`, `file`.

| Field | Type | Required | Description |
|---|---:|---:|---|
| `text` | string | No | Prompt hoac noi dung dau vao. Neu gui kem `file`, field nay duoc xem la yeu cau/huong dan them cho file. |
| `file` | file | No | File nguon. Ho tro `.docx`, `.pdf`, `.txt`. |
| `plan` | string | No | Goi gioi han tai nguyen: `free`, `pro`, `ultra`. Mac dinh `pro`. |
| `slide_count` | integer | No | So slide mong muon. Neu khong truyen, AI Service tu uoc luong theo noi dung/prompt. |
| `generate_images` | string | No | `"true"` hoac `"false"`. Neu prompt co yeu cau anh, service co the tu bat sinh anh. |
| `image_limit` | integer | No | So anh toi da muon sinh. Neu khong truyen, service tu tinh theo plan/so slide. |

### Request Example

```bash
curl -X POST "http://localhost:8000/api/generate-slide-spec" \
  -F "text=Tao 8 slide tieng Viet ve he thong bai do xe thong minh trong truong dai hoc. Hay co bieu do Q1 45%, Q2 58%, Q3 72%, Q4 81%. Hay co bang so sanh quan ly thu cong va he thong thong minh theo cac tieu chi: toc do xu ly, do chinh xac, chi phi van hanh, trai nghiem sinh vien." \
  -F "plan=pro" \
  -F "generate_images=true"
```

### Submit Response

API xu ly bat dong bo, nen response ban dau chi co `task_id`.

```json
{
  "task_id": "95915ceb-eda2-4890-a954-efff6069c547",
  "status": "processing",
  "message": "Processing JSON Spec via Redis worker...",
  "check_status_url": "/api/status/95915ceb-eda2-4890-a954-efff6069c547"
}
```

Sau do poll:

```txt
GET /api/status/95915ceb-eda2-4890-a954-efff6069c547
```

## 2. Revise Slide Spec

Sua deck da sinh bang prompt tu nhien. API nay dung de user yeu cau sua noi dung, bang, chart, anh, hoac toan bo deck.

```txt
POST /api/revise-slide-spec
Content-Type: multipart/form-data
```

### Request Fields

| Field | Type | Required | Description |
|---|---:|---:|---|
| `source_task_id` | string | Yes | `task_id` cua deck da completed truoc do. |
| `revision_prompt` | string | Yes | Yeu cau sua bang ngon ngu tu nhien. |
| `plan` | string | No | `free`, `pro`, `ultra`. Mac dinh `pro`. |
| `generate_images` | string | No | Nen gui `"true"` neu muon cho phep sua/sinh anh. |
| `revision_scope` | string | No | `auto`, `slide`, `deck`. Mac dinh nen de `auto`. |
| `slide_index` | integer | No | Slide can sua, 0-based. Thuong khong can truyen neu prompt da noi ro. |
| `slide_number` | integer | No | Slide can sua, 1-based. Thuong khong can truyen neu prompt da noi ro. |
| `target_slide_indices` | string | No | Danh sach index 0-based, co the la JSON array hoac chuoi cach nhau boi dau phay. |
| `target_slide_numbers` | string | No | Danh sach so slide 1-based, co the la JSON array hoac chuoi cach nhau boi dau phay. |
| `image_limit` | integer | No | So anh toi da khi yeu cau sua/sinh anh. |

Khuyen nghi BE/FE chi can gui:

```txt
source_task_id
revision_prompt
plan=pro
generate_images=true
revision_scope=auto
```

AI Service se tu hieu sua slide nao hay sua full deck dua tren prompt.

### Request Examples

Sua anh mot slide:

```bash
curl -X POST "http://localhost:8000/api/revise-slide-spec" \
  -F "source_task_id=95915ceb-eda2-4890-a954-efff6069c547" \
  -F "revision_prompt=Anh o slide 3 chua khop, hay doi thanh bai do xe dai hoc hien dai co cam bien IoT, camera giam sat va bang dien tu hien thi so cho trong." \
  -F "plan=pro" \
  -F "generate_images=true"
```

Sua bang:

```bash
curl -X POST "http://localhost:8000/api/revise-slide-spec" \
  -F "source_task_id=95915ceb-eda2-4890-a954-efff6069c547" \
  -F "revision_prompt=Chuyen slide so sanh phuong an thanh bang ro rang hon, gom cac cot: Tieu chi, Quan ly thu cong, He thong thong minh, Nhan xet." \
  -F "plan=pro" \
  -F "generate_images=true"
```

Sua chart:

```bash
curl -X POST "http://localhost:8000/api/revise-slide-spec" \
  -F "source_task_id=95915ceb-eda2-4890-a954-efff6069c547" \
  -F "revision_prompt=O slide co so lieu Q1-Q4, hay doi thanh bieu do duong de the hien xu huong tang theo thoi gian." \
  -F "plan=pro" \
  -F "generate_images=true"
```

Sua full deck:

```bash
curl -X POST "http://localhost:8000/api/revise-slide-spec" \
  -F "source_task_id=95915ceb-eda2-4890-a954-efff6069c547" \
  -F "revision_prompt=Sua toan bo bai cho giong van chuyen nghiep hon, tieu de ngan gon hon, bullet cu the hon va giam cac cau chung chung." \
  -F "plan=pro" \
  -F "generate_images=true"
```

### Submit Response

```json
{
  "task_id": "64c7ea2d-2dcd-4768-991e-593736dbc600",
  "source_task_id": "95915ceb-eda2-4890-a954-efff6069c547",
  "revision_scope": "slide",
  "target_slide_indices": [5],
  "status": "processing",
  "message": "Revising JSON Spec via Redis worker...",
  "check_status_url": "/api/status/64c7ea2d-2dcd-4768-991e-593736dbc600"
}
```

Sau do poll `GET /api/status/{task_id}` giong generate.

## 3. Get Task Status

Dung de poll tien do va lay ket qua cuoi cung.

```txt
GET /api/status/{task_id}
```

### Processing Response

```json
{
  "status": "processing",
  "progress": 68,
  "result": {
    "images": {
      "done": 1,
      "total": 4
    }
  }
}
```

`result` trong luc processing co the rong hoac chua thong tin tam thoi nhu `chunks`, `images`.

### Completed Response

Khi `status = completed`, deck JSON nam tai `result.deck`.

```json
{
  "status": "completed",
  "progress": 100,
  "result": {
    "task_id": "95915ceb-eda2-4890-a954-efff6069c547",
    "status": "completed",
    "mode": "json_spec",
    "spec_version": "1.2",
    "slide_preset": "modern",
    "color_theme": "modern",
    "title_slide": {
      "title": "He thong bai do xe thong minh",
      "subtitle": "Tao boi AI Slide Generator"
    },
    "content_slide_footer": "AI Slide Generator",
    "deck": {
      "title": "He thong bai do xe thong minh",
      "slides": []
    }
  }
}
```

Voi task revise, `result` co them metadata:

```json
{
  "revision_scope": "slide",
  "target_slide_indices": [5],
  "changed_fields": ["text"],
  "revision_prompt": "..."
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

## 4. Output JSON Contract

FE nen render dua vao `result.deck.slides`.

### Deck Object

```json
{
  "title": "He thong bai do xe thong minh",
  "slides": []
}
```

### Slide Object

```json
{
  "index": 0,
  "title": "Toc do xu ly",
  "bullets": [
    "Toc do xu ly nhanh hon nho cam bien va xu ly tu dong."
  ],
  "notes": "Ghi chu thuyet trinh cho slide.",
  "chart": null,
  "table": null,
  "image": null,
  "layout": "text_only",
  "primary_visual": null,
  "likely_multi_pptx_slides": false
}
```

| Field | Type | Description |
|---|---:|---|
| `index` | integer | Thu tu slide, bat dau tu `0`. |
| `title` | string | Tieu de slide. |
| `bullets` | string[] | Noi dung chinh. |
| `notes` | string | Ghi chu/loi thuyet trinh. |
| `chart` | object/null | Du lieu chart neu slide co chart. |
| `table` | object/null | Du lieu bang neu slide co table. |
| `image` | object/null | Thong tin anh neu slide co anh. |
| `layout` | string | Goi y layout: `text_only`, `text_image`, `text_chart`, `text_table`. |
| `primary_visual` | string/null | `image`, `chart`, `table`, hoac `null`. |
| `likely_multi_pptx_slides` | boolean | Goi y slide co the qua dai neu export PPTX. |

Quan trong:

- `layout = "text_table"` chi khi `table` co data that.
- `layout = "text_chart"` chi khi `chart` co data that.
- `layout = "text_image"` chi khi `image.url` hoac `image.path` ton tai.
- FE khong can tu doan bang/chart tu text.

## 5. Table Object

```json
{
  "title": "So sanh phuong an quan ly bai do xe",
  "headers": ["Tieu chi", "Quan ly thu cong", "He thong thong minh"],
  "rows": [
    ["Toc do xu ly", "Cham, phu thuoc nhan vien", "Nhanh, tu dong"],
    ["Do chinh xac", "Thap, de sai sot", "Cao, du lieu thoi gian thuc"],
    ["Chi phi van hanh", "Cao", "Thap hon ve dai han"],
    ["Trai nghiem sinh vien", "Bat tien, cho doi", "Thuan tien, nhanh chong"]
  ]
}
```

FE render bang theo:

```txt
table.headers
table.rows
```

Neu `table = null`, slide khong co bang.

## 6. Chart Object

Chart co the la single-series hoac multi-series.

### Single-Series Example

```json
{
  "title": "Ty le su dung bai do xe theo quy",
  "chart_type": "line",
  "type": "line",
  "labels": ["Quy 1", "Quy 2", "Quy 3", "Quy 4"],
  "categories": ["Quy 1", "Quy 2", "Quy 3", "Quy 4"],
  "values": [0.45, 0.58, 0.72, 0.81],
  "unit": "percent",
  "is_percent": true
}
```

### Multi-Series Example

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

FE render chart theo thu tu uu tien:

1. Neu co `chart.series`, dung `chart.labels`/`chart.categories` + `series`.
2. Neu khong co `series`, dung `chart.labels`/`chart.categories` + `values`.
3. Loai chart lay tu `chart.chart_type` hoac `chart.type`.

## 7. Image Object

```json
{
  "path": "/app/outputs/images/task_2_external.jpg",
  "url": "/outputs/images/task_2_external.jpg",
  "mime": "image/jpeg"
}
```

FE nen dung:

```txt
image.url
```

Neu FE khac domain voi AI Service, ghep full URL:

```txt
{AI_SERVICE_BASE_URL}{image.url}
```

Vi du:

```txt
http://localhost:8000/outputs/images/task_2_external.jpg
```

## 8. Cancel Task

Huy task dang chay.

```txt
POST /api/cancel/{task_id}
```

Response:

```json
{
  "task_id": "95915ceb-eda2-4890-a954-efff6069c547",
  "status": "cancelled",
  "message": "Task cancellation requested"
}
```

Luu y: cancel la best-effort. Neu task dang goi model/image server ben ngoai, viec huy co the khong dung ngay lap tuc.

## 9. Integration Notes For BE/FE

- BE/FE chi can tich hop async task flow.
- Khong goi truc tiep model/LLM/image server.
- Khong can tu tach table/chart/image tu text.
- Render theo `primary_visual` va object tuong ung:
  - `primary_visual = "table"`: render `table.headers` + `table.rows`.
  - `primary_visual = "chart"`: render `chart.labels/categories` + `chart.values/series`.
  - `primary_visual = "image"`: render `image.url`.
  - `primary_visual = null`: render text-only.
- `chart`, `table`, `image` co the la `null`; FE phai render tolerant.
- BE nen luu lai `task_id`, prompt goc, va `result.deck` sau khi completed.
- De sua deck, FE/BE gui `source_task_id` cua task completed gan nhat.
- Sau revise, nen dung `task_id` moi lam source cho lan revise tiep theo.

## 10. Minimal FE Render Rule

Pseudo-code:

```ts
for (const slide of deck.slides) {
  renderTitle(slide.title)
  renderBullets(slide.bullets)

  if (slide.primary_visual === "table" && slide.table) {
    renderTable(slide.table.headers, slide.table.rows)
  } else if (slide.primary_visual === "chart" && slide.chart) {
    renderChart(slide.chart)
  } else if (slide.primary_visual === "image" && slide.image?.url) {
    renderImage(API_BASE_URL + slide.image.url)
  }

  renderNotes(slide.notes)
}
```

## 11. API Summary

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/generate-slide-spec` | Tao deck JSON moi. |
| `POST` | `/api/revise-slide-spec` | Sua deck JSON da sinh. |
| `GET` | `/api/status/{task_id}` | Poll tien do va lay result. |
| `POST` | `/api/cancel/{task_id}` | Huy task dang chay. |
| `GET` | `/outputs/images/...` | Lay file anh da sinh. |
