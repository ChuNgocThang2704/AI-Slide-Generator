import { plainText as htmlToPlain } from './textFit.js';
import { isGeneratedTheme, buildGeneratedTheme } from './generatedTheme.js';

/* ───────────────────────────── Themes & tokens ───────────────────────────── */

// Generated (prompt-driven) templates use the same adaptive layout engine.
class AdaptiveTemplateSet extends Set {
  has(value) { return super.has(value) || isGeneratedTheme(value); }
}
export const ADAPTIVE_TEMPLATES = new AdaptiveTemplateSet([
  'soft-blue', 'clean-white', 'blue-planet', 'royal-purple', 'modern-dark',
  'playful-yellow', 'gradient-border', 'nature-green', 'tech-purple',
  'ocean-teal', 'editorial-paper', 'midnight-gold',
]);

// Per-theme design tokens. Themes differ by palette, typography, title
// treatment and their default cover/closing composition — NOT by moving the
// everyday content slide away from the traditional "title on top, text below".
const DESIGN = {
  'soft-blue': { accent: '#0d5099', onAccent: '#fefefe', titleSize: 36, weight: 700, decor: null, cover: 'cover-left', closing: 'closing-cards' },
  'royal-purple': { accent: '#9948ff', onAccent: '#fefefe', titleSize: 36, weight: 700, decor: null, cover: 'cover-center', closing: 'closing-center' },
  'clean-white': { accent: '#4f46e5', onAccent: '#fefefe', titleSize: 36, weight: 700, decor: null, cover: 'cover-split', closing: 'closing-list' },
  'modern-dark': { accent: '#6c63ff', onAccent: '#fefefe', titleSize: 36, weight: 700, decor: 'underline', cover: 'cover-hero', closing: 'closing-cards' },
  'playful-yellow': { accent: '#f59e0b', onAccent: '#2e1e0a', titleSize: 38, weight: 400, decor: 'underline', cover: 'cover-center', closing: 'closing-center' },
  'gradient-border': { accent: '#6c63ff', onAccent: '#fefefe', titleSize: 36, weight: 700, decor: 'underline', cover: 'cover-left', closing: 'closing-cards' },
  'blue-planet': { accent: '#00f2fe', onAccent: '#031233', titleSize: 36, weight: 700, decor: 'underline', cover: 'cover-left', closing: 'closing-cards', safeRight: 740, circleImages: true },
  'nature-green': { accent: '#2ecc71', onAccent: '#062314', titleSize: 34, weight: 700, decor: 'underline', cover: 'cover-split', closing: 'closing-cards' },
  'tech-purple': { accent: '#e056fd', onAccent: '#1a0526', titleSize: 36, weight: 700, decor: 'underline', cover: 'cover-center', closing: 'closing-cards' },
  'ocean-teal': { accent: '#0f766e', onAccent: '#fefefe', titleSize: 36, weight: 700, decor: 'underline', cover: 'cover-left', closing: 'closing-cards' },
  'editorial-paper': { accent: '#c2410c', onAccent: '#fefefe', titleSize: 34, weight: 700, decor: 'underline', cover: 'cover-split', closing: 'closing-list' },
  'midnight-gold': { accent: '#f5c542', onAccent: '#1a1300', titleSize: 38, weight: 700, decor: 'underline', cover: 'cover-hero', closing: 'closing-center' },
};
const designOf = (theme) => ({
  pad: 64,
  safeRight: 896,
  ...(DESIGN[theme] || (isGeneratedTheme(theme) ? buildGeneratedTheme(theme).design : null) || DESIGN['soft-blue']),
});

/* ───────────────────────────── Variant catalogue ─────────────────────────── */

export const LAYOUT_VARIANTS = {
  text: [
    { id: 'classic', label: 'Cổ điển' },
    { id: 'columns', label: '2 cột' },
    { id: 'cards', label: 'Thẻ' },
    { id: 'rail', label: 'Tiêu đề trái' },
    { id: 'centered', label: 'Căn giữa' },
    { id: 'banner', label: 'Banner' },
  ],
  image: [
    { id: 'image-right', label: 'Ảnh phải' },
    { id: 'image-left', label: 'Ảnh trái' },
    { id: 'image-top', label: 'Ảnh ngang' },
    { id: 'image-focus', label: 'Ảnh lớn' },
  ],
  data: [
    { id: 'data-full', label: 'Toàn chiều rộng' },
    { id: 'data-side', label: 'Chữ trái' },
    { id: 'data-side-right', label: 'Chữ phải' },
  ],
  cover: [
    { id: 'cover-center', label: 'Giữa' },
    { id: 'cover-left', label: 'Trái' },
    { id: 'cover-split', label: 'Chia đôi' },
    { id: 'cover-hero', label: 'Nổi bật' },
  ],
  closing: [
    { id: 'closing-cards', label: 'Thẻ' },
    { id: 'closing-list', label: 'Danh sách' },
    { id: 'closing-center', label: 'Căn giữa' },
    { id: 'closing-split', label: 'Chia đôi' },
  ],
};

const VARIANT_KEYS = new Set(['--slide-cols', '--slide-card-cols', '--decor-accent']);
const LIST_VARIANT_CLASSES = ['slide-cards', 'slide-plain'];

/* ───────────────────────────── Small helpers ─────────────────────────────── */

const box = (x, y, width, height) => ({ x: Math.round(x), y: Math.round(y), width: Math.round(width), height: Math.round(height) });
const textLength = (value) => String(value || '').replace(/<[^>]*>/g, '').length;
const itemCount = (html) => (String(html || '').match(/<li\b/gi) || []).length;

// The layout model mirrors what the canvas actually paints (list indent, item
// spacing, unbreakable column items, card padding) so a saved box always holds
// its text — thumbnails and presentations never get to auto-grow a clipped box.
const GLYPH = 0.55;
const LIST_INDENT_EM = 1.75;
const ITEM_GAP_EM = 0.7;

function splitItems(html) {
  const source = String(html || '');
  if (/<li\b/i.test(source)) {
    return source.split(/<\/li>/i).map((part) => htmlToPlain(part)).filter(Boolean);
  }
  return htmlToPlain(source).split(/\n+/).filter(Boolean);
}

function linesFor(text, width, size, glyph = GLYPH) {
  const cpl = Math.max(6, Math.floor(width / (size * glyph)));
  return Math.max(1, Math.ceil(text.length / cpl));
}

function itemHeights(items, width, size, lineHeight, indent) {
  const usable = Math.max(40, width - 16 - indent * size);
  return items.map((text) => linesFor(text, usable, size) * size * lineHeight);
}

// Smallest column height that fits the items when an item cannot split.
function packColumns(heights, gap, cols) {
  if (cols <= 1) return heights.reduce((sum, h) => sum + h, 0) + gap * Math.max(0, heights.length - 1);
  const tallest = Math.max(0, ...heights);
  let low = tallest;
  let high = heights.reduce((sum, h) => sum + h, 0) + gap * heights.length;
  const fits = (limit) => {
    let used = 1;
    let filled = 0;
    heights.forEach((h) => {
      const next = filled ? filled + gap + h : h;
      if (next > limit) { used += 1; filled = h; } else filled = next;
    });
    return used <= cols;
  };
  for (let i = 0; i < 24; i += 1) {
    const mid = (low + high) / 2;
    if (fits(mid)) high = mid; else low = mid;
  }
  return Math.ceil(high);
}

// mode: 'list' (bulleted flow), 'plain' (no markers, e.g. centred), 'cards'.
function measureBody(html, width, size, { lineHeight = 1.5, cols = 1, mode = 'list', cardCols = 2 } = {}) {
  const items = splitItems(html);
  if (!items.length) return Math.ceil(size * lineHeight + 16);
  const gap = size * (mode === 'plain' ? 0.82 : ITEM_GAP_EM);
  if (mode === 'cards') {
    const cardW = (width - 14 * (cardCols - 1)) / cardCols;
    const heights = itemHeights(items, cardW - 34, size, 1.45, 0).map((h) => h + 28);
    let total = 0;
    for (let row = 0; row < heights.length; row += cardCols) total += Math.max(...heights.slice(row, row + cardCols));
    return Math.ceil(total + 14 * (Math.ceil(heights.length / cardCols) - 1) + 8);
  }
  const indent = mode === 'plain' ? 0 : LIST_INDENT_EM;
  const colW = cols > 1 ? (width - 40 * (cols - 1)) / cols : width;
  const heights = itemHeights(items, colW, size, lineHeight, indent);
  const trailing = mode === 'plain' && items.length > 1 ? size * 0.6 : 0;
  return Math.ceil(packColumns(heights, gap, cols) + 10 + trailing);
}

// Largest size whose measured height fits; falls back to `min` (clamped to the
// area so geometry stays on the canvas even for extreme amounts of text).
// Sizes below `min` are tried only when the text would otherwise be clipped.
function planBody(html, width, maxHeight, { min = 13, max = 24, ...options } = {}) {
  const floor = Math.min(min, 11);
  for (let size = max; size >= floor; size -= 0.5) {
    const height = measureBody(html, width, size, options);
    if (height <= maxHeight) return { fs: size, h: Math.max(44, height) };
  }
  return { fs: floor, h: Math.min(maxHeight, Math.max(44, measureBody(html, width, floor, options))) };
}

// `extra` is padding a title treatment adds (the underline reserves space below).
function fitTitle(text, width, { max, min = 22, maxLines = 2, weight = 700, extra = 0 }) {
  const len = Math.max(1, textLength(text));
  const glyph = weight >= 700 ? 0.54 : 0.5;
  let size = max;
  for (; size > min; size -= 1) {
    const cpl = Math.max(6, Math.floor((width - 16) / (size * glyph)));
    if (Math.ceil(len / cpl) <= maxLines) break;
  }
  const cpl = Math.max(6, Math.floor((width - 16) / (size * glyph)));
  const lines = Math.max(1, Math.min(maxLines + 1, Math.ceil(len / cpl)));
  return { size, lines, height: Math.ceil(lines * size * 1.18 + 8 + extra) };
}

function restyleLists(html, add = []) {
  return String(html || '').replace(/<(ul|ol)\b([^>]*)>/gi, (match, tag, attrs) => {
    const existing = (attrs.match(/class="([^"]*)"/i)?.[1] || '').split(/\s+/).filter(Boolean);
    const kept = existing.filter((cls) => !LIST_VARIANT_CLASSES.includes(cls));
    const rest = attrs.replace(/\s*class="[^"]*"/i, '');
    const cls = [...kept, ...add].join(' ');
    return `<${tag}${cls ? ` class="${cls}"` : ''}${rest}>`;
  });
}

// Older split layouts stored one list per box; merging the boxes leaves several
// adjacent lists. Editing, columns and cards all expect a single list.
function unifyLists(html) {
  const source = String(html || '');
  const lists = source.match(/<ul\b[^>]*>[\s\S]*?<\/ul>/gi) || [];
  if (lists.length < 2) return source;
  const remainder = source.replace(/<ul\b[^>]*>[\s\S]*?<\/ul>/gi, '').replace(/\s+/g, '');
  if (remainder || lists.some((list) => (list.match(/<ul\b/gi) || []).length > 1)) return source;
  const open = lists[0].match(/<ul\b[^>]*>/i)[0];
  return `${open}${lists.map((list) => list.replace(/^<ul\b[^>]*>/i, '').replace(/<\/ul>$/i, '')).join('')}</ul>`;
}

// Choosing a layout re-aligns the text; a paragraph-level alignment left over
// from an earlier manual edit would otherwise fight the new composition.
const stripParagraphAlign = (html) => String(html || '')
  .replace(/\s*text-align:\s*[a-z]+;?/gi, '')
  .replace(/\sstyle="\s*"/gi, '');

const hasNestedList = (html) => /<li\b[^>]*>(?:(?!<\/li>)[\s\S])*<(?:ul|ol)\b/i.test(String(html || ''));

/* ───────────────────────── Boundary / table normalisation ────────────────── */

const BOUNDARY_LABELS = new Set([
  'BÀI GIẢNG', 'LECTURE', 'KẾT THÚC BÀI GIẢNG', 'END OF LECTURE',
  'BÀI THUYẾT TRÌNH', 'PRESENTATION', 'KẾT LUẬN', 'CLOSING',
]);
const plainUpper = (value) => String(value || '').replace(/<[^>]*>/g, '').trim().toUpperCase();

// Generated eyebrow labels were retired; anything still carrying one is stale
// output from an older generator and would only pile up on template switches.
export const isBoundaryLabel = (element) => element?.type === 'text' && element?.role === 'custom'
  && BOUNDARY_LABELS.has(plainUpper(element.content));

// Only removes stale generated labels. It never touches geometry or styling:
// cover and closing slides are ordinary, freely editable canvases.
export function normalizeBoundaryElements(elements = [], type) {
  if (!['title', 'thankyou'].includes(type)) return elements;
  if (!elements.some(isBoundaryLabel)) return elements;
  return elements.filter((element) => !isBoundaryLabel(element));
}

export function normalizeTableElements(elements = []) {
  const hasTable = elements.some((el) => el.type === 'table');
  const isGeneratedBody = (el) => el.type === 'text' && el.role === 'body'
    && ['data-wide', 'data-editorial'].includes(el.templateLayout);
  if (!hasTable || !elements.some(isGeneratedBody)) return elements;
  // Migrate only the body boxes added by the old built-in data layouts.
  // Keep manual annotations, custom templates, and the table payload intact.
  return elements.filter((el) => !isGeneratedBody(el)).map((el) =>
    el.type === 'table' && el.templateLayout === 'data-wide'
      ? { ...el, y: 132, height: 368 } : el);
}

export function orderedBodyElements(elements = []) {
  const bodies = elements.filter((el) => el.type === 'text' && el.role === 'body');
  if (!bodies.length || !bodies.every((el) => el.layoutGroup === bodies[0].layoutGroup && el.layoutGroup)) return bodies;
  return [...bodies].sort((a, b) => (a.layoutOrder || 0) - (b.layoutOrder || 0));
}

function mergeLayoutBodies(elements) {
  const generated = orderedBodyElements(elements).filter((el) => el.layoutGroup);
  if (generated.length < 2 || !generated.every((el) => el.layoutGroup === generated[0].layoutGroup)) return elements;
  const merged = { ...generated[0], content: unifyLists(generated.map((el) => el.content).join('')) };
  return elements.flatMap((el) => el.id === merged.id ? [merged] : generated.includes(el) ? [] : [el]);
}

// Older decks stored a two-column text slide as separate left/right boxes.
// One body with CSS columns is easier to edit and keeps bullets in one place.
function mergeColumnPairs(elements) {
  const left = elements.find((el) => el.type === 'text' && el.role === 'body-left');
  const right = elements.find((el) => el.type === 'text' && el.role === 'body-right');
  if (!left || !right || elements.some((el) => el.type === 'text' && el.role === 'body')) return elements;
  const merged = { ...left, role: 'body', content: unifyLists(`${left.content || ''}${right.content || ''}`) };
  return elements.flatMap((el) => el === left ? [merged] : el === right ? [] : [el]);
}

export function isDenseVisual(element) {
  const data = element?.data || {};
  if (element?.type === 'table') {
    return (data.headers?.length || 0) > 4 || (data.rows?.length || 0) > 6
      || JSON.stringify(data.rows || []).length > 650;
  }
  return (data.labels?.length || 0) > 6 || (data.series?.length || 0) > 2;
}

/* ───────────────────────────── Kind & variant choice ─────────────────────── */

export function layoutKindOf(slide, elements = []) {
  if (elements.some((el) => el.type === 'text' && el.role === 'quote')) return 'quote';
  const visuals = elements.some((el) => el.type === 'table' || el.type === 'chart') || slide?.table || slide?.chart;
  const images = elements.some((el) => el.type === 'image') || slide?.imageUrl;
  if (slide?.type === 'title' && !visuals && !images) return 'cover';
  if (slide?.type === 'thankyou' && !visuals && !images) return 'closing';
  if (visuals) return 'data';
  if (images) return 'image';
  return 'text';
}

export function defaultVariant(kind, theme, ctx = {}) {
  const design = designOf(theme);
  if (kind === 'cover') return design.cover;
  if (kind === 'closing') return design.closing;
  if (kind === 'image') return 'image-right';
  if (kind === 'data') return 'data-full';
  if (kind === 'text') {
    if (ctx.bullets >= 8 || ctx.chars > 620) return 'columns';
    return 'classic';
  }
  return null;
}

export function resolveVariant(kind, requested, theme, ctx) {
  const list = LAYOUT_VARIANTS[kind];
  if (!list) return null;
  return list.some((item) => item.id === requested) ? requested : defaultVariant(kind, theme, ctx);
}

export function variantsForSlide(slide) {
  const kind = layoutKindOf(slide, Array.isArray(slide?.elements) ? slide.elements : []);
  return { kind, variants: LAYOUT_VARIANTS[kind] || [] };
}

// Spreads richer layouts across a deck without ever leaving the traditional
// one behind: only every other suitable slide gets a variation.
export function suggestVariant(slide, index, theme) {
  const elements = Array.isArray(slide?.elements) ? slide.elements : [];
  const kind = layoutKindOf(slide, elements);
  if (kind === 'cover' || kind === 'closing') return defaultVariant(kind, theme);
  if (kind === 'image') return ['image-right', 'image-left', 'image-focus', 'image-top'][index % 4];
  if (kind === 'data') return index % 2 ? 'data-side' : 'data-full';
  if (kind !== 'text') return null;
  const body = elements.find((el) => el.type === 'text' && el.role === 'body');
  const html = body?.content || (Array.isArray(slide?.bullets) ? slide.bullets.map((b) => `<li>${b}</li>`).join('') : '');
  const items = itemCount(html);
  const avg = items ? textLength(html) / items : textLength(html);
  const chars = textLength(html);
  if (items >= 3 && items <= 6 && avg <= 110 && chars <= 520) return index % 3 === 0 ? 'cards' : 'classic';
  if (items >= 7 || chars > 620) return 'columns';
  if (chars <= 220 && items <= 3) return index % 2 ? 'centered' : 'rail';
  return index % 4 === 1 ? 'banner' : 'classic';
}

/* ───────────────────────────── Layout engine ─────────────────────────────── */

// All bounds share the editor's 960 x 540 coordinate system.
export function layoutTemplateElements(slide, source, theme, colors) {
  // An uploaded template's art can reserve part of the slide (see templateArt.js).
  const D = { ...designOf(theme), ...(slide?.richText?._safe || {}) };
  const fitT = (text, width, options) => fitTitle(text, width, { ...options, extra: D.decor ? 12 : 0 });
  const withoutBodies = source.some((el) => el.type === 'table')
    ? source.filter((el) => !(el.type === 'text' && el.role === 'body')) : source;
  const elements = normalizeBoundaryElements(
    mergeColumnPairs(mergeLayoutBodies(withoutBodies)), slide.type, theme,
  ).map((el) => ({ ...el, style: el.style ? { ...el.style } : undefined }));

  const kind = layoutKindOf(slide, elements);
  if (kind === 'quote') return elements.map((el) => ({ ...el, templateLayout: 'quote' }));

  const title = elements.find((el) => el.type === 'text' && el.role === 'title');
  const bodies = elements.filter((el) => el.type === 'text' && el.role === 'body');
  const code = elements.find((el) => el.type === 'text' && el.role === 'code');
  const visuals = elements.filter((el) => el.type === 'table' || el.type === 'chart');
  const images = elements.filter((el) => el.type === 'image');
  const primary = bodies[0];
  const bodyHtml = bodies.map((el) => el.content).join('');
  const bullets = itemCount(bodyHtml);
  const chars = textLength(bodyHtml);

  // Compositions centred on the whole canvas would run into art on one side, so a
  // slide with a reserved area uses their left-aligned counterparts.
  const chosenVariant = resolveVariant(kind, slide?.richText?._layoutVariant, theme, { bullets, chars });
  const variant = slide?.richText?._safe
    ? ({ centered: 'classic', 'cover-center': 'cover-left', 'closing-center': 'closing-list' }[chosenVariant] || chosenVariant)
    : chosenVariant;
  const P = D.pad;
  const R = D.safeRight;
  const W = R - P;

  const place = (el, b, style = {}, extra = {}) => {
    if (!el) return;
    Object.assign(el, b, extra);
    const next = { ...el.style, ...style };
    delete next.fontSizeLocked;
    if (extra.decor) next['--decor-accent'] = D.accent;
    else delete next['--decor-accent'];
    el.style = next;
    if (!('decor' in extra)) delete el.decor;
    else if (extra.decor == null) delete el.decor;
  };

  const baseStyles = () => {
    elements.forEach((el) => {
      if (el.type !== 'text' || !['title', 'body'].includes(el.role)) return;
      const next = { ...el.style };
      VARIANT_KEYS.forEach((key) => delete next[key]);
      delete next.background;
      delete next.padding;
      el.style = {
        ...next,
        fontFamily: el.role === 'title' ? colors.title : colors.body,
        color: el.role === 'title' ? colors.text : colors.sub,
        textAlign: 'left',
        verticalAlign: 'top',
        lineHeight: el.role === 'title' ? 1.18 : 1.5,
      };
      el.content = stripParagraphAlign(el.content);
      if (el.role === 'body') el.content = restyleLists(el.content);
    });
  };
  baseStyles();

  const titleText = title?.content;
  const titleStyle = (size, align = 'left', extra = {}) => ({
    fontSize: size, fontWeight: D.weight, textAlign: align, lineHeight: 1.18, ...extra,
  });
  const decorFor = (align = 'left') => (D.decor ? (align === 'center' ? 'underline-center' : D.decor) : null);
  const bodyStyle = (size, align = 'left', extra = {}) => ({
    fontSize: size, lineHeight: 1.5, textAlign: align, ...extra,
  });

  // Sits any extra bodies (rare) under the primary one so nothing overlaps.
  const stackExtras = (area, fs, align = 'left') => {
    const extras = bodies.slice(1);
    if (!extras.length) return;
    const gap = 14;
    const share = (area.height - gap * extras.length) / (extras.length + 1);
    place(primary, box(area.x, area.y, area.width, share), bodyStyle(fs, align));
    extras.forEach((el, index) => place(el, box(area.x, area.y + (index + 1) * (share + gap), area.width, share), bodyStyle(fs, align)));
  };

  const putCode = (top, left, width) => {
    if (!code) return top;
    const height = Math.max(90, 500 - top);
    place(code, box(left, top, width, height), { fontSize: 15 });
    return top + height;
  };

  const putVisuals = (area) => {
    const slots = [...visuals, ...images];
    if (!slots.length) return;
    const gap = 20;
    const across = area.width >= area.height * 0.9;
    slots.forEach((el, index) => {
      const shared = across
        ? box(area.x + index * ((area.width - gap * (slots.length - 1)) / slots.length + gap), area.y,
          (area.width - gap * (slots.length - 1)) / slots.length, area.height)
        : box(area.x, area.y + index * ((area.height - gap * (slots.length - 1)) / slots.length + gap),
          area.width, (area.height - gap * (slots.length - 1)) / slots.length);
      place(el, D.circleImages && el.type === 'image' ? squareIn(shared) : shared);
    });
  };
  // Keeps a centred block symmetric while clearing decorations (Blue Planet's planet).
  const symWidth = (w, bottom) => (R < 896 && bottom > 340 ? Math.min(w, 2 * (R - 480)) : w);
  const squareIn = (b) => {
    const side = Math.min(b.width, b.height);
    return box(b.x + (b.width - side) / 2, b.y + (b.height - side) / 2, side, side);
  };

  /* ── text ─────────────────────────────────────────────────────────────── */
  if (kind === 'text' || kind === 'closing') {
    const isClosing = kind === 'closing';
    const flat = ['classic', 'closing-list', 'columns', 'cards', 'closing-cards', 'banner'];
    const railLike = variant === 'rail' || variant === 'closing-split';
    const centered = variant === 'centered' || variant === 'closing-center';
    const maxSize = isClosing ? 24 : 23;

    // Body + optional code block below it, inside `area`.
    const putBody = (area, options, align = 'left') => {
      const room = code ? Math.min(area.height, 170) : area.height;
      const plan = planBody(bodyHtml, area.width, room, options);
      const style = {};
      if (options.cols > 1) style['--slide-cols'] = options.cols;
      if (options.mode === 'cards') style['--slide-card-cols'] = options.cardCols;
      place(primary, box(area.x, area.y, area.width, plan.h), bodyStyle(plan.fs, align, style));
      if (bodies.length > 1) stackExtras(area, plan.fs, align);
      if (code) putCode(area.y + plan.h + 12, area.x, area.width);
      return plan;
    };

    if (flat.includes(variant)) {
      const isBanner = variant === 'banner';
      const bannerW = Math.min(832, W);
      const tFit = fitT(titleText, isBanner ? bannerW : W, { max: isClosing ? D.titleSize + 2 : D.titleSize, weight: D.weight });
      const top = isBanner ? 32 : 40;
      const tBox = isBanner ? box(P, top, bannerW, tFit.height + 22) : box(P, top, W, tFit.height);
      place(title, tBox, titleStyle(tFit.size, 'left', isBanner ? { color: D.onAccent } : {}),
        { decor: isBanner ? 'band' : decorFor('left') });
      const y = tBox.y + tBox.height + (isBanner ? 30 : 22);
      const area = box(P, y, W, 500 - y);
      if (variant === 'cards' || variant === 'closing-cards') {
        const n = Math.max(1, splitItems(bodyHtml).length);
        const avg = chars / n;
        const cardCols = n === 1 ? 1 : n <= 3 && avg <= 90 ? n : n === 4 ? 2 : avg > 110 ? 2 : 3;
        if (primary && !hasNestedList(bodyHtml)) primary.content = restyleLists(primary.content, ['slide-cards']);
        putBody(area, { min: 14, max: isClosing ? 22 : 21, lineHeight: 1.45, mode: 'cards', cardCols });
      } else {
        putBody(area, { min: 13, max: maxSize, cols: variant === 'columns' ? 2 : 1 });
      }
    } else if (railLike) {
      const rail = 270;
      const tFit = fitT(titleText, rail, { max: 34, min: 22, maxLines: 5, weight: D.weight });
      place(title, box(P, 96, rail, tFit.height), titleStyle(tFit.size, 'left'), { decor: decorFor('left') });
      const bx = P + rail + 44;
      const area = box(bx, 84, R - bx, 416);
      if (variant === 'closing-split' && primary && !hasNestedList(bodyHtml)) primary.content = restyleLists(primary.content, ['slide-cards']);
      putBody(area, variant === 'closing-split'
        ? { min: 14, max: 22, lineHeight: 1.45, mode: 'cards', cardCols: 1 }
        : { min: 13, max: 24 });
    } else if (centered) {
      const tw = symWidth(720, 200);
      const tFit = fitT(titleText, tw, { max: D.titleSize + 4, weight: D.weight });
      const tBox = box(480 - tw / 2, isClosing ? 70 : 60, tw, tFit.height);
      place(title, tBox, titleStyle(tFit.size, 'center'), { decor: decorFor('center') });
      const y = tBox.y + tBox.height + 30;
      const aw = symWidth(660, 500);
      if (primary) primary.content = restyleLists(primary.content, ['slide-plain']);
      putBody(box(480 - aw / 2, y, aw, 500 - y), { min: 14, max: 25, mode: 'plain' }, 'center');
    }
  }

  /* ── images ───────────────────────────────────────────────────────────── */
  if (kind === 'image') {
    const focus = variant === 'image-focus';
    const tFit = fitT(titleText, focus ? W - 474 : W, { max: focus ? 32 : D.titleSize, min: 22, maxLines: focus ? 4 : 2, weight: D.weight });
    const tBox = focus ? null : box(P, 40, W, tFit.height);
    if (tBox) place(title, tBox, titleStyle(tFit.size, 'left'), { decor: decorFor('left') });
    const top = tBox ? tBox.y + tBox.height + 24 : 60;
    const usableH = 500 - top;
    const stackImages = (imageBox) => {
      const slot = images.length ? (imageBox.height - 16 * (images.length - 1)) / images.length : 0;
      images.forEach((el, index) => {
        const b = box(imageBox.x, imageBox.y + index * (slot + 16), imageBox.width, slot);
        place(el, D.circleImages ? squareIn(b) : b);
      });
    };
    const putText = (area, options = {}) => {
      const room = code ? Math.min(area.height, 170) : area.height;
      const plan = planBody(bodyHtml, area.width, room, { min: 13, max: 22, ...options });
      place(primary, box(area.x, area.y, area.width, plan.h), bodyStyle(plan.fs, 'left', options.cols > 1 ? { '--slide-cols': options.cols } : {}));
      if (bodies.length > 1) stackExtras(area, plan.fs);
      if (code) putCode(area.y + plan.h + 12, area.x, area.width);
    };
    if (variant === 'image-left') {
      stackImages(box(P, top, 380, usableH));
      putText(box(P + 420, top, R - (P + 420), usableH));
    } else if (variant === 'image-top') {
      const imgH = Math.min(190, usableH - 130);
      const w = (W - 16 * (images.length - 1)) / Math.max(1, images.length);
      images.forEach((el, index) => {
        const b = box(P + index * (w + 16), top, w, imgH);
        place(el, D.circleImages ? squareIn(b) : b);
      });
      const y = top + imgH + 18;
      putText(box(P, y, W, 500 - y), { cols: itemCount(bodyHtml) >= 3 ? 2 : 1, max: 20 });
    } else if (variant === 'image-focus') {
      // Themes that keep the lower-right clear put the text column on the left.
      const flip = D.safeRight < 896;
      const imageX = flip ? 896 - 400 : P;
      const textX = flip ? P : P + 474;
      const textW = flip ? imageX - 40 - P : R - textX;
      stackImages(box(imageX, 60, flip ? 400 : 430, flip ? 400 : 430));
      place(title, box(textX, 84, textW, tFit.height), titleStyle(tFit.size, 'left'), { decor: decorFor('left') });
      const y = 84 + tFit.height + 18;
      putText(box(textX, y, textW, 500 - y));
    } else {
      const textW = images.length ? 440 : W;
      stackImages(box(P + textW + 36, top, R - (P + textW + 36), usableH));
      putText(box(P, top, textW, usableH));
    }
  }

  /* ── tables & charts ──────────────────────────────────────────────────── */
  if (kind === 'data') {
    // Tables and charts have their own opaque surface, so they may use the full
    // width even where a theme keeps text clear of a decoration.
    const RW = 896;
    const WW = RW - P;
    const side = variant === 'data-side' || variant === 'data-side-right';
    const describes = bodies.length && bodyHtml && !visuals.some((el) => el.type === 'table');
    if (!side) {
      const tFit = fitT(titleText, WW, { max: D.titleSize, weight: D.weight });
      const tBox = box(P, 40, WW, tFit.height);
      place(title, tBox, titleStyle(tFit.size, 'left'), { decor: decorFor('left') });
      let y = tBox.y + tBox.height + 20;
      if (describes) {
        const plan = planBody(bodyHtml, WW, 96, { min: 14, max: 19 });
        place(primary, box(P, y, WW, plan.h), bodyStyle(plan.fs));
        y += plan.h + 14;
      }
      putVisuals(box(P - 8, y, WW + 16, 500 - y));
      if (code) putCode(y, P, WW);
    } else {
      const left = variant === 'data-side';
      const railW = 236;
      const rx = left ? P : RW - railW;
      const vx = left ? P + railW + 36 : P;
      const vw = WW - railW - 36;
      const tFit = fitT(titleText, railW, { max: 30, min: 20, maxLines: 5, weight: D.weight });
      place(title, box(rx, 60, railW, tFit.height), titleStyle(tFit.size, 'left'), { decor: decorFor('left') });
      let y = 60 + tFit.height + 18;
      if (describes) {
        // A right-hand rail sits where some themes draw a decoration low on the slide.
        const floor = !left && D.safeRight < 896 ? 340 : 500;
        const plan = planBody(bodyHtml, railW, Math.max(60, floor - y), { min: 13, max: 18 });
        place(primary, box(rx, y, railW, Math.min(plan.h, floor - y)), bodyStyle(plan.fs));
        y += plan.h + 14;
      }
      putVisuals(box(vx, 60, vw, 440));
      if (code) putCode(y, rx, railW);
    }
  }

  /* ── cover ────────────────────────────────────────────────────────────── */
  if (kind === 'cover') {
    const subtitleHtml = bodyHtml;
    const place2 = (tBox, bBox, align, tFit, bFs) => {
      place(title, tBox, titleStyle(tFit.size, align), { decor: decorFor(align) });
      place(primary, bBox, bodyStyle(bFs, align));
      if (bodies.length > 1) stackExtras(bBox, bFs, align);
    };
    const center = variant === 'cover-center';
    const hero = variant === 'cover-hero';
    const split = variant === 'cover-split';
    const width = split ? 470 : Math.min(hero ? 720 : center ? 720 : 660, R - P - (hero ? 0 : 16));
    const tFit = fitT(titleText, width, { max: hero ? 60 : 54, min: 30, maxLines: split ? 4 : 3, weight: D.weight });
    const bWidth = split ? R - (P + 470 + 50) : Math.min(center ? 600 : hero ? 600 : 560, R - P - 16);
    const subPlan = subtitleHtml ? planBody(subtitleHtml, bWidth, 150, { min: 15, max: 22, mode: 'plain' }) : { fs: 20, h: 0 };
    const bFs = subPlan.fs;
    const bH = subPlan.h;
    const gap = 26;
    const total = tFit.height + (bH ? gap + bH : 0);
    const topY = hero ? 540 - 72 - total : Math.max(48, (540 - total) / 2 + 6);
    if (split) {
      const y = Math.max(60, (540 - tFit.height) / 2 - 10);
      place2(box(P, y, 470, tFit.height), box(P + 470 + 50, y + 8, bWidth, Math.max(bH, 60)), 'left', tFit, bFs);
      if (primary) {
        primary.decor = 'rule-left';
        primary.style = { ...primary.style, '--decor-accent': D.accent };
      }
    } else if (center) {
      const bw = symWidth(600, topY + tFit.height + gap + bH);
      place2(box(120, topY, 720, tFit.height), box(480 - bw / 2, topY + tFit.height + gap, bw, bH || 40), 'center', tFit, bFs);
    } else {
      const x = hero ? P : 80;
      place2(box(x, topY, width, tFit.height), box(x, topY + tFit.height + gap, bWidth, bH || 40), 'left', tFit, bFs);
    }
  }

  // Closing slides are short; centre the block vertically so the bottom is not
  // left empty (the plain list variant stays top-aligned like a normal slide).
  if (kind === 'closing' && variant !== 'closing-list') {
    const block = [title, primary, code].filter(Boolean);
    const top = Math.min(...block.map((el) => el.y));
    const bottom = Math.max(...block.map((el) => el.y + el.height));
    const shift = Math.max(0, Math.min(Math.round((540 - (bottom - top)) / 2 - 12 - top), 500 - bottom + 12));
    block.forEach((el) => { el.y += shift; });
  }

  const marker = variant || kind;
  return elements.map((el) => ({ ...el, templateLayout: marker }));
}

/* ───────────────────────────── Preview (for the picker) ──────────────────── */

// Geometry of a variant on a synthetic slide, so the picker thumbnails show
// exactly what the engine will produce.
export function previewVariantRects(kind, variantId, theme) {
  const colors = { title: 'serif', body: 'sans-serif', text: '#111', sub: '#444' };
  const item = (t) => `<li>${t}</li>`;
  const base = [
    { id: 'p-title', type: 'text', role: 'title', content: 'Tiêu đề của slide trình bày', x: 0, y: 0, width: 10, height: 10, style: {} },
  ];
  const list = `<ul>${['Ý chính đầu tiên của nội dung', 'Ý thứ hai được nêu ngắn gọn rõ ràng', 'Ý thứ ba bổ sung thêm thông tin', 'Ý cuối cùng chốt lại vấn đề'].map(item).join('')}</ul>`;
  const body = { id: 'p-body', type: 'text', role: 'body', content: list, x: 0, y: 0, width: 10, height: 10, style: {} };
  const image = { id: 'p-image', type: 'image', role: 'image', src: 'x', x: 0, y: 0, width: 10, height: 10 };
  const table = { id: 'p-table', type: 'table', role: 'visual', data: { headers: ['A', 'B', 'C'], rows: [[1, 2, 3]] }, x: 0, y: 0, width: 10, height: 10 };
  const chart = { id: 'p-chart', type: 'chart', role: 'visual', data: { labels: ['A', 'B'], series: [{ values: [1, 2] }] }, x: 0, y: 0, width: 10, height: 10 };
  const slideBase = { richText: { _layoutVariant: variantId } };
  let slide;
  let source;
  if (kind === 'cover') { slide = { ...slideBase, type: 'title' }; source = [...base, { ...body, content: 'Phụ đề ngắn gọn cho phần mở đầu' }]; }
  else if (kind === 'closing') { slide = { ...slideBase, type: 'thankyou' }; source = [...base, body]; }
  else if (kind === 'image') { slide = { ...slideBase, type: 'imageText', imageUrl: 'x' }; source = [...base, body, image]; }
  else if (kind === 'data') { slide = { ...slideBase, type: 'chart', chart: {} }; source = [...base, { ...body, content: '<ul><li>Mô tả ngắn cho biểu đồ</li></ul>' }, chart]; }
  else { slide = { ...slideBase, type: 'content' }; source = [...base, body]; }
  if (kind === 'data' && variantId && variantId.startsWith('data-')) source = source.filter((el) => el.type !== 'image');
  const out = layoutTemplateElements(slide, source.map((el) => ({ ...el })), theme, colors);
  void table;
  return out.map((el) => ({ role: el.role, type: el.type, x: el.x, y: el.y, width: el.width, height: el.height }));
}
