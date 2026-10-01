// Shapes and icons a user can drop onto a slide, as ordinary editable elements.
//
//   { type: 'shape', shape: 'star', fill, borderColor, borderWidth, opacity }
//   { type: 'icon',  icon: 'Lightbulb', color, strokeWidth, opacity }
//
// Geometry lives here (pure data) so the canvas, the PPTX export and the tests all agree on
// what a shape looks like. Polygon points are in a 0..100 box and stretch with the element.

const uid = () => `el-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

const starPoints = (spikes = 5, inner = 0.42) => {
  const points = [];
  for (let i = 0; i < spikes * 2; i += 1) {
    const radius = i % 2 === 0 ? 50 : 50 * inner;
    const angle = (Math.PI / spikes) * i - Math.PI / 2;
    points.push([+(50 + radius * Math.cos(angle)).toFixed(2), +(50 + radius * Math.sin(angle)).toFixed(2)]);
  }
  return points;
};

const wavePoints = (phase, amplitude = 18, cycles = 1.2) => {
  const points = [];
  for (let x = 0; x <= 100; x += 4) {
    points.push([x, +(38 + amplitude * Math.sin((x / 100) * Math.PI * 2 * cycles + phase)).toFixed(2)]);
  }
  return [...points, [100, 100], [0, 100]];
};

// kind: 'box' = drawn by CSS (rect, rounded, ellipse); 'polygon' and 'line' = drawn as SVG;
// 'glow' (soft radial disc) and 'dots' (dot grid) are drawn from a single colour.
// `hidden` shapes exist for template ornaments but are not offered in the picker.
export const SHAPE_CATALOG = [
  { id: 'rect', label: 'Chữ nhật', kind: 'box', radius: '0', size: [220, 130], pptx: 'rect' },
  { id: 'roundRect', label: 'Bo góc', kind: 'box', radius: '14%', size: [220, 130], pptx: 'roundRect' },
  { id: 'ellipse', label: 'Hình tròn', kind: 'box', radius: '50%', size: [140, 140], pptx: 'ellipse' },
  { id: 'triangle', label: 'Tam giác', kind: 'polygon', points: [[50, 0], [100, 100], [0, 100]], size: [150, 130], pptx: 'triangle' },
  { id: 'diamond', label: 'Thoi', kind: 'polygon', points: [[50, 0], [100, 50], [50, 100], [0, 50]], size: [140, 140], pptx: 'diamond' },
  { id: 'star', label: 'Ngôi sao', kind: 'polygon', points: starPoints(), size: [150, 150], pptx: 'star5' },
  { id: 'arrowRight', label: 'Mũi tên', kind: 'polygon', points: [[0, 30], [58, 30], [58, 8], [100, 50], [58, 92], [58, 70], [0, 70]], size: [220, 100], pptx: 'rightArrow' },
  { id: 'chevron', label: 'Chevron', kind: 'polygon', points: [[0, 0], [70, 0], [100, 50], [70, 100], [0, 100], [30, 50]], size: [180, 100], pptx: 'chevron' },
  { id: 'line', label: 'Đường kẻ', kind: 'line', size: [260, 12], pptx: 'line' },
  { id: 'wave', label: 'Sóng', kind: 'polygon', points: wavePoints(0), size: [960, 150], pptx: null },
  { id: 'wave2', label: 'Sóng 2', kind: 'polygon', points: wavePoints(2.2, 14, 1), size: [960, 150], pptx: null, hidden: true },
  { id: 'glow', label: 'Quầng sáng', kind: 'glow', size: [300, 300], pptx: 'ellipse' },
  { id: 'dots', label: 'Lưới chấm', kind: 'dots', size: [230, 130], pptx: null },
  { id: 'corner', label: 'Góc', kind: 'polygon', points: [[0, 0], [100, 0], [100, 9], [9, 9], [9, 100], [0, 100]], size: [34, 34], pptx: null, hidden: true },
];

export const PICKER_SHAPES = SHAPE_CATALOG.filter((shape) => !shape.hidden);

export const shapeInfo = (shape) => SHAPE_CATALOG.find((item) => item.id === shape) || SHAPE_CATALOG[0];

export const ICON_NAMES = [
  'Star', 'Heart', 'Check', 'X', 'Plus', 'ArrowRight', 'ArrowUp', 'ChevronRight', 'Lightbulb', 'Target',
  'Rocket', 'Flag', 'Bookmark', 'Bell', 'Calendar', 'Clock', 'Users', 'User', 'Mail', 'Phone',
  'MapPin', 'Globe', 'Search', 'Settings', 'Shield', 'Lock', 'Key', 'Award', 'Trophy', 'Gift',
  'Camera', 'Music', 'Video', 'BookOpen', 'GraduationCap', 'Coffee', 'Leaf', 'Sun', 'Moon', 'Cloud',
  'Zap', 'Flame', 'Droplet', 'Wifi', 'Cpu', 'Code', 'Database', 'BarChart3', 'PieChart', 'TrendingUp',
  'Briefcase', 'Home', 'Building2', 'Truck', 'Car', 'Plane', 'ThumbsUp', 'Smile', 'MessageCircle', 'Quote',
];

export const isKnownIcon = (name) => ICON_NAMES.includes(name);

/** A new shape element, centred, coloured with the deck's accent unless a colour is given. */
export function createShapeElement(shape, { accent = '#6c63ff', x, y } = {}) {
  const info = shapeInfo(shape);
  const [width, height] = info.size;
  const isLine = info.kind === 'line';
  return {
    id: uid(),
    type: 'shape',
    role: 'shape',
    shape: info.id,
    x: Math.round(x ?? (960 - width) / 2),
    y: Math.round(y ?? (info.id === 'wave' ? 540 - height : (540 - height) / 2)),
    width,
    height,
    rotation: 0,
    fill: isLine ? 'transparent' : accent,
    borderColor: isLine ? accent : 'transparent',
    borderWidth: isLine ? 4 : 0,
    opacity: 1,
  };
}

export function createIconElement(icon, { accent = '#6c63ff', x, y } = {}) {
  return {
    id: uid(),
    type: 'icon',
    role: 'icon',
    icon: isKnownIcon(icon) ? icon : 'Star',
    x: Math.round(x ?? (960 - 72) / 2),
    y: Math.round(y ?? (540 - 72) / 2),
    width: 72,
    height: 72,
    rotation: 0,
    color: accent,
    strokeWidth: 2,
    opacity: 1,
  };
}

/** Normalised view of a shape element, filling in what older elements never stored. */
export function resolveShape(element) {
  const info = shapeInfo(element?.shape);
  const borderWidth = Number(element?.borderWidth ?? (element?.borderColor && element.borderColor !== 'transparent' ? 1 : 0)) || 0;
  return {
    info,
    fill: element?.fill || 'transparent',
    borderColor: element?.borderColor || 'transparent',
    borderWidth: Math.max(0, Math.min(24, borderWidth)),
    opacity: Math.max(0, Math.min(1, Number(element?.opacity ?? 1))),
    // Shapes made before the catalogue existed carry their own radius.
    radius: element?.shape ? info.radius : (element?.radius ?? 0),
  };
}

/** Elements the user placed themselves (as opposed to a template's own ornaments). */
export const isUserGraphic = (element) => ['shape', 'icon'].includes(element?.type) && !element?.ornament;

export const isValidColor = (value) => /^#[0-9a-f]{6}$/i.test(String(value || ''));
