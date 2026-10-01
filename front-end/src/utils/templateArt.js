// Background and decorative art of an uploaded template's sample slide.
//
// The template service returns them as locked "background" / "decoration" elements.
// They are kept apart from the slide's ordinary elements (in `richText._decor`) so the
// layout engine never mistakes an illustration for content and moves it. The text
// layout is then told where the art sits (`richText._safe`) so it keeps clear of it.

const CANVAS_W = 960;
const CANVAS_H = 540;
const MIN_TEXT_WIDTH = 340;
const GAP = 24;

export function relativeLuminance(color) {
  const match = /^#?([0-9a-f]{6})$/i.exec(String(color || '').trim());
  if (!match) return 1;
  const value = parseInt(match[1], 16);
  const channel = (shift) => {
    const c = ((value >> shift) & 255) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(16) + 0.7152 * channel(8) + 0.0722 * channel(0);
}

export const isDarkColor = (color) => relativeLuminance(color) < 0.3;

const isWhite = (fill) => /^#f{6}$/i.test(String(fill || '').trim());

const pickArt = (element) => ({
  id: element.id,
  type: element.type,
  role: element.role,
  x: Number(element.x) || 0,
  y: Number(element.y) || 0,
  width: Number(element.width) || 0,
  height: Number(element.height) || 0,
  rotation: Number(element.rotation) || 0,
  ...(element.opacity != null ? { opacity: Number(element.opacity) } : {}),
  ...(element.src ? { src: element.src } : {}),
  ...(element.fill ? { fill: element.fill } : {}),
  ...(element.borderColor ? { borderColor: element.borderColor } : {}),
  ...(element.style && Object.keys(element.style).length ? { style: element.style } : {}),
});

// Pictures big enough to push text aside. Gradient discs, thin shapes, icons and wide
// banners are backdrops the text may sit on.
function reservingPictures(decor) {
  return decor.flatMap((element) => {
    if (element.type !== 'image' || element.role === 'background') return [];
    const x0 = Math.max(0, element.x);
    const x1 = Math.min(CANVAS_W, element.x + element.width);
    const y0 = Math.max(0, element.y);
    const y1 = Math.min(CANVAS_H, element.y + element.height);
    const width = x1 - x0;
    const height = y1 - y0;
    if (width <= 0 || height <= 0) return [];
    if (width * height < 0.04 * CANVAS_W * CANVAS_H) return [];
    if (width > CANVAS_W * 0.7) return [];
    return [{ element, x0, x1, area: width * height, side: (x0 + x1) / 2 >= CANVAS_W / 2 ? 'right' : 'left' }];
  });
}

/**
 * Where text may go on this slide: the horizontal band left free by the illustrations.
 * When art on both sides leaves too little room, the pictures on the smaller side are
 * dropped so the text keeps a readable column instead of running over an illustration.
 * Returns the (possibly reduced) art and `{ pad, safeRight }`, or null safe area when the
 * default layout can stay.
 */
export function resolveArtLayout(decor) {
  let art = decor;
  const bounds = (items) => ({
    left: Math.max(64, ...items.filter((item) => item.side === 'left').map((item) => Math.round(item.x1 + GAP))),
    right: Math.min(896, ...items.filter((item) => item.side === 'right').map((item) => Math.round(item.x0 - GAP))),
  });
  let items = reservingPictures(art);
  let { left, right } = bounds(items);
  while (right - left < MIN_TEXT_WIDTH) {
    const area = (side) => items.filter((item) => item.side === side).reduce((sum, item) => sum + item.area, 0);
    const smaller = area('left') <= area('right') ? 'left' : 'right';
    const dropped = new Set(items.filter((item) => item.side === smaller).map((item) => item.element));
    if (!dropped.size || (area('left') === 0 || area('right') === 0)) {
      // A single huge picture: nothing to trade off, keep the default layout over it.
      return { decor: art, safe: null };
    }
    art = art.filter((element) => !dropped.has(element));
    items = reservingPictures(art);
    ({ left, right } = bounds(items));
  }
  if (left === 64 && right === 896) return { decor: art, safe: null };
  return { decor: art, safe: { pad: left, safeRight: right } };
}

export const computeSafeArea = (decor) => resolveArtLayout(decor).safe;

export function buildTemplateArt(match) {
  const source = Array.isArray(match?.elements) ? match.elements : [];
  const decor = source
    .filter((el) => ['background', 'decoration'].includes(el.role) && ['shape', 'image'].includes(el.type))
    .map(pickArt)
    .filter((el) => (el.type === 'image' ? Boolean(el.src) : Boolean(el.fill)));
  const hasArt = decor.some((el) => el.role === 'decoration')
    || decor.some((el) => el.role === 'background' && !isWhite(el.fill));
  if (!hasArt) return { decor: [], safe: null, pageColor: null };
  const resolved = resolveArtLayout(decor);
  return {
    decor: resolved.decor,
    safe: resolved.safe,
    pageColor: match?.backgroundColor || null,
  };
}

/** Pieces covering nearly the whole slide are the backdrop, not an ornament. */
export const isBackdrop = (item) => item.role === 'background' || (item.width >= 900 && item.height >= 500);

/** The ornaments of an uploaded template as slide elements the user can select, move and delete. */
export function artToElements(decor) {
  return decor.filter((item) => !isBackdrop(item)).map((item) => (item.type === 'shape' && (item.style?.shape || item.style?.path) ? shapeOrnament(item) : ({
    id: `orn-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    type: 'art',
    role: 'ornament',
    ornament: true,
    artType: item.type === 'image' ? 'image' : 'shape',
    src: item.src,
    fill: item.fill,
    style: item.style ? { ...item.style } : undefined,
    x: item.x,
    y: item.y,
    width: item.width,
    height: item.height,
    rotation: item.rotation || 0,
    opacity: item.opacity ?? 1,
  })));
}

// A template shape the editor has a matching shape for becomes a real shape: it can then be
// recoloured, given an outline and restyled with the same inspector as any shape the user adds.
function shapeOrnament(item) {
  return {
    id: `orn-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    type: 'shape',
    role: 'ornament',
    ornament: true,
    shape: item.style.shape,
    ...(typeof item.style.path === 'string' ? { path: item.style.path } : {}),
    ...(item.style.dash ? { dash: item.style.dash } : {}),
    fill: item.fill || 'transparent',
    borderColor: item.borderColor || 'transparent',
    borderWidth: Number(item.style.borderWidth) || 0,
    x: item.x,
    y: item.y,
    width: item.width,
    height: item.height,
    rotation: item.rotation || 0,
    opacity: item.opacity ?? 1,
  };
}

/** Drops a previous template's art from a slide's richText. */
export function withoutTemplateArt(richText) {
  const next = { ...(richText || {}) };
  delete next._noOrnaments;
  delete next._decor;
  delete next._safe;
  delete next._tplBg;
  return next;
}
