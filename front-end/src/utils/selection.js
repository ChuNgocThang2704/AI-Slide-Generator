// Multi-selection maths for the slide canvas: bounds, alignment, distribution, groups, layers,
// cloning and drag snapping. Pure functions over element lists, so the canvas only wires events.
// Boxes are the elements' own (unrotated) x/y/width/height, in the 960 x 540 slide space.

export const SLIDE_W = 960;
export const SLIDE_H = 540;

const box = (element) => ({
  x: Number(element.x) || 0,
  y: Number(element.y) || 0,
  width: Number(element.width) || 0,
  height: Number(element.height) || 0,
});

const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
const round = (value) => Math.round(value * 10) / 10;
const uid = (prefix) => `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
export const newElementId = () => uid('el');

/** Elements that can take part in a selection (locked ones are left alone). */
export const selectable = (element) => Boolean(element) && !element.locked;

export function boundsOf(elements, ids) {
  const wanted = new Set(ids);
  const picked = elements.filter((element) => wanted.has(element.id)).map(box);
  if (!picked.length) return null;
  const x0 = Math.min(...picked.map((b) => b.x));
  const y0 = Math.min(...picked.map((b) => b.y));
  const x1 = Math.max(...picked.map((b) => b.x + b.width));
  const y1 = Math.max(...picked.map((b) => b.y + b.height));
  return { x: x0, y: y0, width: x1 - x0, height: y1 - y0 };
}

/** The ids plus every member of any group they touch: grouped elements are picked as one. */
export function expandToGroups(elements, ids) {
  const wanted = new Set(ids);
  const groups = new Set(elements.filter((el) => wanted.has(el.id) && el.groupId).map((el) => el.groupId));
  elements.forEach((el) => { if (el.groupId && groups.has(el.groupId)) wanted.add(el.id); });
  return elements.filter((el) => wanted.has(el.id)).map((el) => el.id);
}

/** Toggles one element in a selection (Shift+click), keeping groups whole. */
export function toggleInSelection(elements, current, id) {
  const [expanded] = [expandToGroups(elements, [id])];
  const have = new Set(current);
  const allIn = expanded.every((member) => have.has(member));
  if (allIn) return current.filter((member) => !expanded.includes(member));
  return expandToGroups(elements, [...current, ...expanded]);
}

/** Elements whose box touches the marquee rectangle (any two corners, in slide space). */
export function marqueeSelect(elements, rect) {
  const x0 = Math.min(rect.x0, rect.x1);
  const x1 = Math.max(rect.x0, rect.x1);
  const y0 = Math.min(rect.y0, rect.y1);
  const y1 = Math.max(rect.y0, rect.y1);
  const hits = elements.filter((element) => {
    if (!selectable(element)) return false;
    const b = box(element);
    return b.x < x1 && b.x + b.width > x0 && b.y < y1 && b.y + b.height > y0;
  }).map((element) => element.id);
  return expandToGroups(elements, hits);
}

export const ALIGN_MODES = ['left', 'center', 'right', 'top', 'middle', 'bottom'];

/**
 * New x/y for each element so the selection lines up. With one element it aligns to the slide,
 * with several it aligns to the selection's own edges (as PowerPoint does).
 * Returns { id: { x?, y? } } for the elements that actually move.
 */
export function alignPatches(elements, ids, mode) {
  const wanted = new Set(ids);
  const items = elements.filter((el) => wanted.has(el.id) && selectable(el));
  if (!items.length || !ALIGN_MODES.includes(mode)) return {};
  const ref = items.length > 1
    ? boundsOf(items, items.map((el) => el.id))
    : { x: 0, y: 0, width: SLIDE_W, height: SLIDE_H };
  const patches = {};
  items.forEach((el) => {
    const b = box(el);
    let x = b.x;
    let y = b.y;
    if (mode === 'left') x = ref.x;
    if (mode === 'center') x = ref.x + (ref.width - b.width) / 2;
    if (mode === 'right') x = ref.x + ref.width - b.width;
    if (mode === 'top') y = ref.y;
    if (mode === 'middle') y = ref.y + (ref.height - b.height) / 2;
    if (mode === 'bottom') y = ref.y + ref.height - b.height;
    x = round(clamp(x, 0, SLIDE_W - b.width));
    y = round(clamp(y, 0, SLIDE_H - b.height));
    if (x !== b.x || y !== b.y) patches[el.id] = { x, y };
  });
  return patches;
}

/** Equal gaps between three or more elements along one axis, keeping the outer two in place. */
export function distributePatches(elements, ids, axis) {
  const wanted = new Set(ids);
  const items = elements.filter((el) => wanted.has(el.id) && selectable(el));
  if (items.length < 3) return {};
  const horizontal = axis === 'h';
  const start = (el) => (horizontal ? box(el).x : box(el).y);
  const size = (el) => (horizontal ? box(el).width : box(el).height);
  const sorted = [...items].sort((a, b) => start(a) - start(b));
  // The span is the outermost edges of the selection (a wide element can end after the last one starts).
  const first = Math.min(...items.map(start));
  const last = Math.max(...items.map((el) => start(el) + size(el)));
  const gap = (last - first - sorted.reduce((sum, el) => sum + size(el), 0)) / (sorted.length - 1);
  // Not enough room for even gaps: moving things would only push them out of the span.
  if (gap < 0) return {};
  const patches = {};
  let cursor = first;
  sorted.forEach((el) => {
    const next = round(cursor);
    if (next !== start(el)) patches[el.id] = horizontal ? { x: next } : { y: next };
    cursor += size(el) + gap;
  });
  return patches;
}

/** Applies { id: patch } to a list. */
export function applyPatches(elements, patches) {
  return elements.map((el) => (patches[el.id] ? { ...el, ...patches[el.id] } : el));
}

/** Puts the picked elements in one group (any previous grouping of them is replaced). */
export function groupElements(elements, ids) {
  const wanted = new Set(expandToGroups(elements, ids));
  if (wanted.size < 2) return elements;
  const groupId = uid('grp');
  return elements.map((el) => (wanted.has(el.id) ? { ...el, groupId } : el));
}

export function ungroupElements(elements, ids) {
  const wanted = new Set(expandToGroups(elements, ids));
  return elements.map((el) => {
    if (!wanted.has(el.id) || !el.groupId) return el;
    const { groupId: dropped, ...rest } = el;
    void dropped;
    return rest;
  });
}

export const hasGroup = (elements, ids) => {
  const wanted = new Set(ids);
  return elements.some((el) => wanted.has(el.id) && el.groupId);
};

/** Copies of the picked elements with new ids and new (but still shared) group ids, nudged aside. */
export function cloneSelection(elements, ids, offset = 20) {
  const wanted = new Set(ids);
  const groupMap = new Map();
  return elements.filter((el) => wanted.has(el.id)).map((el) => {
    const copy = {
      ...el,
      id: uid('el'),
      x: clamp((Number(el.x) || 0) + offset, 0, SLIDE_W - (Number(el.width) || 0)),
      y: clamp((Number(el.y) || 0) + offset, 0, SLIDE_H - (Number(el.height) || 0)),
      style: el.style ? { ...el.style } : undefined,
    };
    if (el.groupId) {
      if (!groupMap.has(el.groupId)) groupMap.set(el.groupId, uid('grp'));
      copy.groupId = groupMap.get(el.groupId);
    }
    return copy;
  });
}

/** Sends the picked elements to the front or back, keeping their order relative to each other. */
export function reorderLayers(elements, ids, direction) {
  const wanted = new Set(ids);
  const moving = elements.filter((el) => wanted.has(el.id));
  const rest = elements.filter((el) => !wanted.has(el.id));
  return direction === 'front' ? [...rest, ...moving] : [...moving, ...rest];
}

/** Moves the whole selection by dx/dy, never letting any part leave the slide. */
export function moveWithinSlide(startPositions, bounds, dx, dy) {
  const safeDx = clamp(dx, -bounds.x, SLIDE_W - (bounds.x + bounds.width));
  const safeDy = clamp(dy, -bounds.y, SLIDE_H - (bounds.y + bounds.height));
  const patches = {};
  Object.entries(startPositions).forEach(([id, start]) => {
    patches[id] = { x: round(start.x + safeDx), y: round(start.y + safeDy) };
  });
  return { patches, dx: safeDx, dy: safeDy };
}

/**
 * Snaps a moving box to the slide's edges and centre and to the other elements' edges and
 * centres, returning the correction and the guide lines to draw.
 */
export function snapBox(moving, others, distance = 6) {
  const xs = [0, SLIDE_W / 2, SLIDE_W, ...others.flatMap((el) => { const b = box(el); return [b.x, b.x + b.width / 2, b.x + b.width]; })];
  const ys = [0, SLIDE_H / 2, SLIDE_H, ...others.flatMap((el) => { const b = box(el); return [b.y, b.y + b.height / 2, b.y + b.height]; })];
  const points = (start, size) => [start, start + size / 2, start + size];
  let fixX = 0;
  let fixY = 0;
  let guideX = null;
  let guideY = null;
  let best = distance + 1;
  xs.forEach((target) => points(moving.x, moving.width).forEach((point) => {
    const delta = target - point;
    if (Math.abs(delta) <= distance && Math.abs(delta) < best) { best = Math.abs(delta); fixX = delta; guideX = target; }
  }));
  best = distance + 1;
  ys.forEach((target) => points(moving.y, moving.height).forEach((point) => {
    const delta = target - point;
    if (Math.abs(delta) <= distance && Math.abs(delta) < best) { best = Math.abs(delta); fixY = delta; guideY = target; }
  }));
  return { fixX, fixY, guideX, guideY };
}
