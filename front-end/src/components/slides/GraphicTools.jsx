import { useState } from 'react';
import { ICON_NAMES, PICKER_SHAPES, isValidColor } from '../../utils/shapeLibrary';
import { ShapeGlyph } from './ElementGlyphs';
import { ICON_COMPONENTS } from './iconMap';
import './GraphicTools.css';

const stop = (event) => event.stopPropagation();

/** Popover for adding a shape or an icon to the slide. */
export function ShapePicker({ onAddShape, onAddIcon, color }) {
  const [tab, setTab] = useState('shapes');
  return (
    <div className="graphic-picker" onPointerDown={stop}>
      <div className="gp-tabs" role="tablist">
        <button type="button" role="tab" aria-selected={tab === 'shapes'} className={tab === 'shapes' ? 'active' : ''} onClick={() => setTab('shapes')}>Hình khối</button>
        <button type="button" role="tab" aria-selected={tab === 'icons'} className={tab === 'icons' ? 'active' : ''} onClick={() => setTab('icons')}>Biểu tượng</button>
      </div>
      {tab === 'shapes' ? (
        <div className="gp-grid shapes">
          {PICKER_SHAPES.map((shape) => (
            <button key={shape.id} type="button" className="gp-item" title={shape.label} aria-label={shape.label} onClick={() => onAddShape(shape.id)}>
              <span className="gp-preview">
                <ShapeGlyph element={{ shape: shape.id, fill: shape.kind === 'line' ? 'transparent' : color, borderColor: shape.kind === 'line' ? color : 'transparent', borderWidth: shape.kind === 'line' ? 3 : 0 }} />
              </span>
              <small>{shape.label}</small>
            </button>
          ))}
        </div>
      ) : (
        <div className="gp-grid icons">
          {ICON_NAMES.map((name) => {
            const Icon = ICON_COMPONENTS[name];
            return (
              <button key={name} type="button" className="gp-item icon" title={name} aria-label={name} onClick={() => onAddIcon(name)}>
                <Icon size={20} color={color} />
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

const hexOr = (value, fallback) => (isValidColor(value) ? value : fallback);

/** Colour, outline and opacity of the selected shape or icon. */
export function GraphicInspector({ element, onChange }) {
  const isIcon = element.type === 'icon';
  const opacity = Math.round((element.opacity ?? 1) * 100);
  const noFill = !isIcon && (element.fill === 'transparent' || !element.fill);

  return (
    <div className="graphic-inspector" onPointerDown={stop}>
      {isIcon ? (
        <>
          <label className="gi-row">
            <span>Màu</span>
            <input type="color" value={hexOr(element.color, '#6c63ff')} onChange={(event) => onChange({ color: event.target.value })} />
          </label>
          <label className="gi-row">
            <span>Độ dày nét</span>
            <input type="range" min="1" max="4" step="0.5" value={element.strokeWidth || 2} onChange={(event) => onChange({ strokeWidth: Number(event.target.value) })} />
          </label>
        </>
      ) : (
        <>
          <div className="gi-row">
            <span>Màu nền</span>
            <span className="gi-inline">
              <input type="color" value={hexOr(element.fill, '#6c63ff')} disabled={noFill} onChange={(event) => onChange({ fill: event.target.value })} />
              <label className="gi-check">
                <input type="checkbox" checked={noFill} onChange={(event) => onChange({ fill: event.target.checked ? 'transparent' : hexOr(element.borderColor, '#6c63ff') })} /> Không tô
              </label>
            </span>
          </div>
          <div className="gi-row">
            <span>Viền</span>
            <span className="gi-inline">
              <input
                type="color"
                value={hexOr(element.borderColor, '#6c63ff')}
                onChange={(event) => onChange({ borderColor: event.target.value, borderWidth: element.borderWidth || 2 })}
              />
              <input type="range" min="0" max="16" value={element.borderWidth || 0} aria-label="Độ dày viền" onChange={(event) => onChange({ borderWidth: Number(event.target.value), borderColor: element.borderColor && element.borderColor !== 'transparent' ? element.borderColor : '#6c63ff' })} />
            </span>
          </div>
        </>
      )}
      <label className="gi-row">
        <span>Độ mờ</span>
        <input type="range" min="10" max="100" value={opacity} aria-label="Độ mờ" onChange={(event) => onChange({ opacity: Number(event.target.value) / 100 })} />
      </label>
    </div>
  );
}
