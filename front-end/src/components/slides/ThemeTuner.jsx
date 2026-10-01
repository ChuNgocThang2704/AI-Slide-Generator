import { useState } from 'react';
import { RotateCcw } from 'lucide-react';
import { THEME_OPTIONS, buildGeneratedTheme, parseThemeCode, withThemeSpec } from '../../utils/generatedTheme';
import './ThemeTuner.css';

const HUE_TRACK = `linear-gradient(90deg, ${[0, 60, 120, 180, 240, 300, 360].map((h) => `hsl(${h} 78% 52%)`).join(', ')})`;
const QUICK_HUES = [8, 27, 45, 142, 175, 215, 255, 300, 335];

function Segmented({ label, value, options, onPick, disabled }) {
  return (
    <div className="tt-field">
      <span className="tt-label">{label}</span>
      <div className="tt-seg" role="group" aria-label={label}>
        {options.map((option, index) => (
          <button
            key={option}
            type="button"
            className={value === index ? 'active' : ''}
            aria-pressed={value === index}
            disabled={disabled}
            onClick={() => onPick(index)}
          >
            {option}
          </button>
        ))}
      </div>
    </div>
  );
}

/**
 * Hand-tuning of a generated template. Every control edits one field of the theme code, so the
 * result stays a valid, readable theme. Changes apply as soon as they are chosen; the hue slider
 * applies on release so dragging does not rebuild the whole deck for every pixel.
 */
export default function ThemeTuner({ code, disabled, onChange, onReset, onPreviewHue }) {
  const spec = parseThemeCode(code);
  // While the slider is dragged the draft shows; after a change it falls back to the code's own hue.
  const [draft, setDraft] = useState(null);
  if (!spec) return null;
  const hueDraft = draft ?? spec.hue;

  const change = (patch) => {
    setDraft(null);
    onChange(withThemeSpec(code, patch));
  };
  // Releasing on the original colour changes nothing, so the preview tint has to be dropped here.
  const settleHue = () => {
    if (hueDraft !== spec.hue) change({ hue: hueDraft });
    else { setDraft(null); onPreviewHue?.(null); }
  };
  const previewHue = withThemeSpec(code, { hue: hueDraft });
  const swatch = buildGeneratedTheme(previewHue).theme;

  return (
    <div className="theme-tuner">
      <div className="tt-head">
        <strong>Tuỳ chỉnh template</strong>
        {onReset && (
          <button type="button" className="tt-reset" onClick={onReset} disabled={disabled} title="Quay về bản đầu tiên của bài này">
            <RotateCcw size={12} /> Đặt lại
          </button>
        )}
      </div>

      <div className="tt-field">
        <span className="tt-label">Màu chủ đạo</span>
        <div className="tt-hue-row">
          <span className="tt-swatch" style={{ background: swatch.primary }} />
          <input
            type="range"
            min="0"
            max="359"
            value={hueDraft}
            aria-label="Màu chủ đạo"
            className="tt-hue"
            style={{ background: HUE_TRACK }}
            disabled={disabled}
            onChange={(event) => {
              const value = Number(event.target.value);
              setDraft(value);
              onPreviewHue?.(value - spec.hue);
            }}
            onPointerUp={settleHue}
            onPointerCancel={settleHue}
            onKeyUp={settleHue}
          />
        </div>
        <div className="tt-quick">
          {QUICK_HUES.map((hue) => (
            <button
              key={hue}
              type="button"
              className="tt-dot"
              aria-label={`Màu ${hue}°`}
              title={`${hue}°`}
              disabled={disabled}
              style={{ background: `hsl(${hue} 78% 52%)` }}
              onClick={() => change({ hue })}
            />
          ))}
        </div>
      </div>

      <Segmented label="Nền" value={spec.dark ? 1 : 0} options={['Sáng', 'Tối']} disabled={disabled} onPick={(index) => change({ dark: index === 1 })} />
      <Segmented label="Độ đậm màu" value={spec.sat} options={THEME_OPTIONS.saturation} disabled={disabled} onPick={(index) => change({ sat: index })} />
      <Segmented label="Màu nhấn" value={spec.shift} options={THEME_OPTIONS.accent} disabled={disabled} onPick={(index) => change({ shift: index })} />
      <Segmented label="Kiểu nền" value={spec.bg} options={THEME_OPTIONS.background} disabled={disabled} onPick={(index) => change({ bg: index })} />
      <Segmented label="Trang trí" value={spec.decor} options={THEME_OPTIONS.decor} disabled={disabled} onPick={(index) => change({ decor: index })} />

      <div className="tt-field">
        <span className="tt-label">Kiểu chữ tiêu đề</span>
        <div className="tt-fonts">
          {THEME_OPTIONS.font.map((font, index) => (
            <button
              key={font.label}
              type="button"
              className={spec.font === index ? 'active' : ''}
              aria-pressed={spec.font === index}
              disabled={disabled}
              style={{ fontFamily: font.family, fontWeight: font.weight }}
              onClick={() => change({ font: index })}
            >
              Aa <small>{font.label}</small>
            </button>
          ))}
        </div>
      </div>

      <Segmented label="Slide bìa" value={spec.cover} options={THEME_OPTIONS.cover} disabled={disabled} onPick={(index) => change({ cover: index })} />
      <Segmented label="Slide kết" value={spec.closing} options={THEME_OPTIONS.closing} disabled={disabled} onPick={(index) => change({ closing: index })} />
    </div>
  );
}
