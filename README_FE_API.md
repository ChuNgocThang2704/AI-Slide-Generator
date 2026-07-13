# FE Integration README

Use this file as the quick handoff note for FE.

Detailed API contract:

- [fe_api_spec.md](./fe_api_spec.md)
- [back-end/document-service/document_api_spec.md](./back-end/document-service/document_api_spec.md)

`fe_api_spec.md` is the source of truth for FE request/response fields. This
README is only the quick-start checklist.

## Base URL

Local gateway:

```txt
http://localhost:8080
```

FE calls the Java BE through API Gateway only. FE should not call the Python AI Service directly.

## Main Flow

Create slides:

```txt
POST /api/document/projects
GET  /api/document/projects/{projectId}/progress
GET  /api/document/projects/{projectId}/pages
```

Revise slides:

```txt
POST /api/document/projects/{projectId}/revise
GET  /api/document/projects/{projectId}/progress
GET  /api/document/projects/{projectId}/pages
```

When FE has one selected slide, send `revisionScope="slide"` and the 1-based
`slideNumber`. For multi-slide natural-language edits, send the slide numbers in
`revisionPrompt` with `revisionScope="auto"`. For a full-deck rewrite, send
`revisionScope="deck"` without a slide target.

## FE Responsibilities

- Send the user's prompt/file data to BE.
- Poll project progress until completed.
- Render slides from `/pages`.
- After revise completes, reload `/pages` and replace local slide state.
- Export PPTX on FE side if the FE export module owns rendering/export.

## FE Should Not Do

- Do not call AI Service directly.
- Do not send `generate_images`; AI Service enables image generation by default.
- Do not force table/chart/image mode from UI unless product requires it later.
- Do not infer table/chart from bullet text. Use structured fields only.

## Slide Render Fields

Each page can contain:

```txt
title
bullets
notes
table
chart
imageUrl
layout
primaryVisual
likelyMultiPptxSlides
```

Render priority:

```txt
table != null       -> render table
else chart != null  -> render chart
else imageUrl set   -> render image
else                -> render text only
```

## AI Revise Examples

FE can send a single text box value as `revisionPrompt`.

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

## Current Tested Behavior

- Generate deck from prompt.
- Auto-detect table/chart/image slides.
- Auto-enable image generation.
- Revise image/table/chart/text.
- Preserve non-target slides during single-slide revise.
- Add slide.
- Delete slide.
- Apply small literal title edit.
- Preserve text and visual fields outside the requested scope.
- Revise multiple slides named in the prompt.
- Revise a full deck while preserving requested chart data.
- Return complete non-empty table/chart specs after revise.
