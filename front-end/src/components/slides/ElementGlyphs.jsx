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
export function ShapeGlyph({ element }) {
  const { info, path, dash, fill, borderColor, borderWidth, opacity, radius } = resolveShape(element);
  const stroke = borderColor === 'transparent' || !borderWidth ? 'none' : borderColor;

  if (info.kind === 'path') {
    return (
      <svg className="canvas-shape-svg" viewBox="0 0 100 100" preserveAspectRatio="none" style={{ opacity }}>
        {path ? (
          <path
            d={path}
            fill={fill}
            fillRule="evenodd"
            stroke={stroke}
            strokeWidth={borderWidth}
            strokeLinejoin="round"
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
