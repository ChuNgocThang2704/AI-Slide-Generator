# LecGen Frontend

React + Vite frontend cho luong tao, render, chinh sua va xuat slide LecGen.

## Chuc nang hien tai

- Dang ky, xac minh email, dang nhap thuong/Google, refresh token va quen mat khau.
- Dashboard co thumbnail that, progress task va phan trang.
- Tao slide tu prompt, file moi hoac tai lieu da upload.
- Editor ba panel co resize, trinh chieu, template va AI Assistant.
- Chinh text, font, mau, list, can le, line spacing, anh, bang va bieu do.
- Autosave, undo/redo va dong bo slide pages voi BE.
- AI revise bang mot o prompt; AI tu xac dinh slide/deck can sua.
- Xuat PDF va PPTX editable theo kha nang mapping cua PowerPoint.
- Goi Free/Pro/Ultra, quota va thanh toan PayOS/Stripe.

## Cai dat

```bash
npm ci
```

Tao `.env` tu `.env.example`:

```env
# De trong de dung hostname cua trinh duyet va cong gateway ben duoi.
VITE_API_BASE_URL=
VITE_GATEWAY_PORT=8080
```

Local gateway mac dinh la `http://localhost:8080`. Khi FE truy cap qua IP server, de `VITE_API_BASE_URL` trong giup FE tu dung cung hostname thay vi khoa cung localhost.

```bash
npm run dev -- --host 0.0.0.0 --port 5173
```

Production build:

```bash
npm run build
```

## Quy tac tich hop

- FE chi goi Java API Gateway.
- Contract request/response: [../fe_api_spec.md](../fe_api_spec.md).
- Tao project: `POST /api/document/projects`.
- Poll: `GET /api/document/projects/{id}/progress`.
- Lay deck: `GET /api/document/projects/{id}/pages`.
- Sua AI: `POST /api/document/projects/{id}/revise` voi `revisionScope="auto"`.
- Sau revise, tai lai toan bo pages; khong merge delta AI o client.
- FE khong gui plan tuy y, khong tu bat/tat anh va khong suy luan table/chart tu bullet.

## Cau truc

```text
src/components/   UI va slide renderer/editor
src/pages/        Auth, Dashboard, Generate, Editor, Pricing, Admin
src/services/     API clients
src/store/        Zustand stores
src/utils/        Slide mapping, text/image fit va export helpers
```
