import { useMemo } from 'react';
import { LayoutGrid, Wand2, RotateCcw } from 'lucide-react';
import { layoutKindOf, LAYOUT_VARIANTS, previewVariantRects, resolveVariant } from '../../utils/templateLayouts';
import './LayoutPicker.css';

const ROLE_FILL = {
  title: 'var(--lp-title)',
  body: 'var(--lp-body)',
  image: 'var(--lp-image)',
  visual: 'var(--lp-visual)',
  code: 'var(--lp-body)',
};

function Thumb({ kind, variantId, theme }) {
  const rects = useMemo(() => previewVariantRects(kind, variantId, theme), [kind, variantId, theme]);
  return (
    <svg viewBox="0 0 960 540" className="lp-thumb" aria-hidden="true">
      <rect width="960" height="540" rx="14" className="lp-thumb-bg" />
      {rects.map((r, index) => {
        const fill = ROLE_FILL[r.role] || (r.type === 'image' ? ROLE_FILL.image : ROLE_FILL.body);
        const rx = r.role === 'title' ? 6 : 12;
        if (r.role === 'body' || r.role === 'code') {
          const lines = Math.max(2, Math.min(7, Math.round(r.height / 44)));
          return (
            <g key={index}>
              {Array.from({ length: lines }, (_, i) => (
                <rect key={i} x={r.x} y={r.y + 8 + i * 36} width={i % 3 === 2 ? r.width * 0.68 : r.width} height="14" rx="7" fill={fill} />
              ))}
            </g>
          );
        }
        return <rect key={index} x={r.x} y={r.y} width={r.width} height={Math.max(14, r.height)} rx={rx} fill={fill} />;
      })}
    </svg>
  );
}

export default function LayoutPicker({ slide, theme, onPick, onAutoMix, onResetAll, disabled = false }) {
  const elements = Array.isArray(slide?.elements) ? slide.elements : [];
  const kind = layoutKindOf(slide, elements);
  const variants = LAYOUT_VARIANTS[kind] || [];
  if (!variants.length) return null;
  const bullets = Array.isArray(slide?.bullets) ? slide.bullets : [];
  const active = resolveVariant(kind, slide?.richText?._layoutVariant, theme, {
    bullets: bullets.length, chars: bullets.join('').length,
  });
  return (
    <div className="lp-root">
      <div className="lp-head">
        <span><LayoutGrid size={14} /> Kiểu trình bày</span>
      </div>
      <div className="lp-grid">
        {variants.map((variant) => (
          <button
            key={variant.id}
            type="button"
            disabled={disabled}
            className={`lp-item ${active === variant.id ? 'active' : ''}`}
            onClick={() => onPick(variant.id)}
            title={`Áp dụng bố cục "${variant.label}" cho slide này`}
          >
            <Thumb kind={kind} variantId={variant.id} theme={theme} />
            <span>{variant.label}</span>
          </button>
        ))}
      </div>
      <p className="lp-note">Chọn bố cục sẽ sắp xếp lại các khung của slide này; nội dung giữ nguyên. Sau đó bạn vẫn kéo, đổi cỡ và định dạng tự do.</p>
      <div className="lp-actions">
        <button type="button" disabled={disabled} onClick={onAutoMix}><Wand2 size={13} /> Đa dạng hóa cả bài</button>
        <button type="button" disabled={disabled} onClick={onResetAll}><RotateCcw size={13} /> Về kiểu cổ điển</button>
      </div>
    </div>
  );
}
