import { Star } from 'lucide-react';
import { ICON_COMPONENTS } from './iconMap';
import { resolveShape } from '../../utils/shapeLibrary';
import { resolveTemplateAssetUrl } from '../../utils/assetUrl';

export function IconGlyph({ element }) {
  const Icon = ICON_COMPONENTS[element.icon] || Star;
  return (
    <div className="canvas-icon" style={{ opacity: element.opacity ?? 1 }}>
      <Icon color={element.color || '#6c63ff'} strokeWidth={Number(element.strokeWidth) || 2} size="100%" />
    </div>
  );
}

/**
 * A picture or plain shape taken from an uploaded template (crop, flip and rounding included).
 * It fills whatever box it is put in, so the same glyph serves the fixed art layer and the
 * editable elements made from it.
 */
export function ArtGlyph({ item }) {
  const style = item.style || {};
  const box = {
    position: 'absolute',
    inset: 0,
    opacity: item.opacity ?? 1,
    transform: [style.flipX ? 'scaleX(-1)' : '', style.flipY ? 'scaleY(-1)' : ''].filter(Boolean).join(' ') || undefined,
    borderRadius: style.borderRadius,
    overflow: 'hidden',
  };
  if (item.type !== 'image' && (style.shape || style.path)) {
    // A preset the editor knows (triangle, star, arrow…) or an outline from the file, drawn as that shape.
    return (
      <div style={{ ...box, borderRadius: undefined, overflow: 'visible' }}>
        <ShapeGlyph element={{ shape: style.path ? 'path' : style.shape, path: style.path, dash: style.dash, fill: item.fill, borderColor: item.borderColor, borderWidth: style.borderWidth, opacity: 1 }} />
      </div>
    );
  }
  if (item.type !== 'image') return <div style={{ ...box, background: item.fill }} />;
  const cropL = style.cropL || 0;
  const cropT = style.cropT || 0;
  const cropW = Math.max(0.05, 1 - cropL - (style.cropR || 0));
  const cropH = Math.max(0.05, 1 - cropT - (style.cropB || 0));
  return (
    <div style={box}>
      <img
        src={resolveTemplateAssetUrl(item.src)}
        alt=""
        draggable={false}
        style={{
          position: 'absolute',
          width: `${100 / cropW}%`,
          height: `${100 / cropH}%`,
          left: `${-(cropL / cropW) * 100}%`,
          top: `${-(cropT / cropH) * 100}%`,
          maxWidth: 'none',
          objectFit: 'fill',
          userSelect: 'none',
          pointerEvents: 'none',
        }}
      />
    </div>
  );
}

const pointList = (points) => points.map(([x, y]) => `${x},${y}`).join(' ');

/** A shape as HTML/SVG; also draws shapes saved before the catalogue existed (plain rectangles). */
// "linear-gradient(90deg, rgba(255, 255, 255, 0) 0%, #FFFFFF 50%)" as SVG gradient geometry and stops.
function parseLinearGradient(value) {
  const match = /^linear-gradient\((.*)\)$/i.exec(String(value || '').trim());
  if (!match) return null;
  const parts = [];
  let depth = 0;
  let current = '';
  for (const ch of match[1]) {
    if (ch === '(') depth += 1;
    if (ch === ')') depth -= 1;
    if (ch === ',' && depth === 0) { parts.push(current.trim()); current = ''; } else current += ch;
  }
  parts.push(current.trim());
  const angleMatch = /^(-?[\d.]+)deg$/i.exec(parts[0]);
  const angle = angleMatch ? Number(angleMatch[1]) : 180;
  const stops = (angleMatch ? parts.slice(1) : parts).map((part, index, all) => {
    const at = /\s+([\d.]+)%$/.exec(part);
    return {
      color: part.replace(/\s+[\d.]+%$/, ''),
      offset: at ? Number(at[1]) / 100 : all.length > 1 ? index / (all.length - 1) : 0,
    };
  });
  if (stops.length < 2) return null;
  const radians = (angle * Math.PI) / 180;
  const dx = Math.sin(radians) / 2;
  const dy = -Math.cos(radians) / 2;
  return { x1: 0.5 - dx, y1: 0.5 - dy, x2: 0.5 + dx, y2: 0.5 + dy, stops };
}

export function ShapeGlyph({ element }) {
  const { info, path, dash, fill, borderColor, borderWidth, opacity, radius } = resolveShape(element);
  const stroke = borderColor === 'transparent' || !borderWidth ? 'none' : borderColor;

  if (info.kind === 'path') {
    // An SVG fill cannot be a CSS gradient (it would paint black), so it becomes a real gradient.
    const gradient = parseLinearGradient(fill);
    const gradientId = gradient ? `grad-${String(element?.id || 'g').replace(/[^a-z0-9_-]/gi, '')}` : null;
    return (
      <svg className="canvas-shape-svg" viewBox="0 0 100 100" preserveAspectRatio="none" style={{ opacity }}>
        {gradient ? (
          <defs>
            <linearGradient id={gradientId} x1={gradient.x1} y1={gradient.y1} x2={gradient.x2} y2={gradient.y2}>
              {gradient.stops.map((stop, index) => (
                <stop key={index} offset={stop.offset} stopColor={stop.color} />
              ))}
            </linearGradient>
          </defs>
        ) : null}
        {path ? (
          <path
            d={path}
            fill={gradient ? `url(#${gradientId})` : fill}
            fillRule="evenodd"
            stroke={stroke}
            strokeWidth={borderWidth}
            strokeLinejoin="round"
            strokeDasharray={dash === 'dot' ? '2 3' : dash === 'dash' ? '7 5' : undefined}
            vectorEffect="non-scaling-stroke"
          />
        ) : null}
      </svg>
    );
  }

  if (info.kind === 'box') {
    return (
      <div
        className="canvas-shape"
        style={{
          background: fill,
          border: borderWidth ? `${borderWidth}px solid ${borderColor}` : undefined,
          borderColor: borderWidth ? borderColor : undefined,
          borderRadius: radius,
          opacity,
        }}
      />
    );
  }

  if (info.kind === 'glow') {
    return <div className="canvas-shape" style={{ background: `radial-gradient(circle, ${fill} 0%, transparent 70%)`, opacity, border: 0 }} />;
  }

  if (info.kind === 'dots') {
    return (
      <div
        className="canvas-shape"
        style={{ background: `radial-gradient(${fill} 1.6px, transparent 1.7px) 0 0 / 18px 18px`, opacity, border: 0 }}
      />
    );
  }

  if (info.kind === 'line') {
    return (
      <svg className="canvas-shape-svg" viewBox="0 0 100 100" preserveAspectRatio="none" style={{ opacity }}>
        <line
          x1="0" y1="50" x2="100" y2="50"
          stroke={stroke === 'none' ? fill : stroke}
          strokeWidth={borderWidth || 4}
          strokeLinecap={dash ? 'butt' : 'round'}
          strokeDasharray={dash === 'dot' ? '2 3' : dash === 'dash' ? '7 5' : undefined}
          vectorEffect="non-scaling-stroke"
        />
      </svg>
    );
  }

  return (
    <svg className="canvas-shape-svg" viewBox="0 0 100 100" preserveAspectRatio="none" style={{ opacity }}>
      <polygon
        points={pointList(info.points)}
        fill={fill}
        stroke={stroke}
        strokeWidth={borderWidth}
        strokeLinejoin="round"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}
