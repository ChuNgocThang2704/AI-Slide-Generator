import { useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import ElementCanvas from '../../components/slides/ElementCanvas';
import { ADAPTIVE_TEMPLATES, LAYOUT_VARIANTS } from '../../utils/templateLayouts';

// Developer-only bench (see App.jsx): renders every layout variant of a slide
// kind with realistic content so layouts can be reviewed without touching data.
const IMAGE = `data:image/svg+xml;utf8,${encodeURIComponent(
  '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="600"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f59e0b"/><stop offset="1" stop-color="#7c3aed"/></linearGradient></defs><rect width="800" height="600" fill="url(#g)"/><circle cx="560" cy="200" r="110" fill="rgba(255,255,255,.35)"/><path d="M0 520 L220 300 L400 460 L600 250 L800 470 L800 600 L0 600Z" fill="rgba(0,0,0,.28)"/></svg>',
)}`;
const BULLETS = {
  short: ['Ý chính đầu tiên', 'Ý thứ hai ngắn gọn', 'Ý thứ ba'],
  medium: [
    'Mốc năm 1857: Thời điểm các nhà truyền giáo mang cây cà phê đầu tiên đến trồng thử nghiệm.',
    'Nhà truyền giáo Pháp: Đưa hạt giống vào các nhà thờ miền Bắc trước khi lan rộng vào miền Trung.',
    'Cường quốc Robusta số một thế giới: Bước chuyển mình vĩ đại nhờ chính sách đổi mới.',
    'Vùng nguyên liệu Tây Nguyên: Đất đỏ bazan tạo nên hương vị đậm đà và khác biệt.',
  ],
  long: Array.from({ length: 9 }, (_, i) => `Ý số ${i + 1}: nội dung khá dài để kiểm tra việc xuống dòng, chia cột và kích thước chữ trong bố cục.`),
};
const TABLE = { headers: ['Vùng sản xuất', 'Loại cà phê', 'Đặc trưng'], rows: [['Buôn Ma Thuột', 'Robusta', 'Đậm, caffeine cao'], ['Cầu Đất', 'Arabica', 'Chua thanh, hậu ngọt'], ['Kết hợp', 'Cả hai', 'Phong phú']] };
const CHART = { type: 'bar', labels: ['2020', '2021', '2022', '2023', '2024'], series: [{ name: 'Sản lượng', values: [26.5, 27.1, 29.8, 26, 28.5] }] };

const make = (kind, variant, shape) => {
  const bullets = BULLETS[shape] || BULLETS.medium;
  const title = shape === 'long' ? 'Thách thức và cơ hội trong tương lai của ngành cà phê Việt Nam giai đoạn 2025–2030' : 'Lịch sử phát triển của cà phê Việt Nam';
  const base = { id: `lab-${kind}-${variant}`, title, bullets, richText: { _layoutVariant: variant }, elements: [] };
  if (kind === 'cover') return { ...base, type: 'title', bullets: ['Hành trình từ hạt giống đầu tiên đến biểu tượng nông nghiệp'] };
  if (kind === 'closing') return { ...base, type: 'thankyou', bullets: bullets.slice(0, 4) };
  if (kind === 'image') return { ...base, type: 'imageText', imageUrl: IMAGE };
  if (kind === 'data') return { ...base, type: 'chart', chart: CHART, bullets: ['Sản lượng ổn định qua các năm'] };
  if (kind === 'table') return { ...base, type: 'table', table: TABLE };
  return { ...base, type: 'content' };
};

export default function LayoutLab() {
  const [params] = useSearchParams();
  const theme = ADAPTIVE_TEMPLATES.has(params.get('theme')) ? params.get('theme') : 'soft-blue';
  const kind = params.get('kind') || 'text';
  const shape = params.get('shape') || 'medium';
  const scale = Number(params.get('scale')) || 0.5;
  const variantKind = kind === 'table' ? 'data' : kind;
  const variants = LAYOUT_VARIANTS[variantKind] || [];
  const slides = useMemo(() => variants.map((v) => ({ variant: v, slide: make(kind, v.id, shape) })), [variants, kind, shape]);
  return (
    <div style={{ background: '#1b1b24', minHeight: '100vh', padding: 12, display: 'flex', flexWrap: 'wrap', gap: 12 }} data-lab-ready="true">
      {slides.map(({ variant, slide }) => (
        <div key={variant.id} data-variant={variant.id} style={{ color: '#fff', font: '13px sans-serif' }}>
          <div style={{ width: 960 * scale, height: 540 * scale, overflow: 'hidden', position: 'relative' }}>
            <div style={{ width: 960, height: 540, transform: `scale(${scale})`, transformOrigin: 'top left' }}>
              <ElementCanvas slide={slide} theme={theme} scale={1} onUpdate={() => {}} readonly />
            </div>
          </div>
          <div style={{ padding: '4px 0' }}>{theme} · {kind} · {variant.id}</div>
        </div>
      ))}
    </div>
  );
}
