// After a custom template's art and the slide's text are both placed, text can still land on a
// photo or a shape (art in the middle of the slide, a row of pictures, art above or below the text).
// `avoidArt` finds those collisions and pulls the text box into the largest free space beside or
// above/below the art. Art that the text is meant to sit on (a panel, a card, the backdrop) is left
// alone, and a box that cannot be moved without becoming unreadably small is left where it is.

const CANVAS_W = 960;
const CANVAS_H = 540;
const GAP = 16;
const MAX_SHIFT = 170;                               // a box is slid at most this far
const MIN_ART_AREA = 0.015 * CANVAS_W * CANVAS_H;   // smaller marks are decoration, not obstacles
const PAGE_SIZED = 0.25 * CANVAS_W * CANVAS_H;      // bigger pieces are the page the text sits on
const MIN_BOX = { title: { w: 220, h: 56 }, body: { w: 240, h: 110 } };

const area = (box) => Math.max(0, box.width) * Math.max(0, box.height);

function overlap(a, b) {
  const w = Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x);
  const h = Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y);
  return w > 0 && h > 0 ? w * h : 0;
}

const isPicture = (item) => item.type === 'image' && item.role !== 'background';
const coversPage = (box) => box.width >= 0.95 * CANVAS_W && box.height >= 0.95 * CANVAS_H;

/**
 * The pieces of a template's art that text must keep clear of. Body text also keeps off a large
 * picture such as a header photo band (a title may sit on it, a paragraph cannot be read on it).
 */
export function artObstacles(decor, { forBody = false } = {}) {
  return (Array.isArray(decor) ? decor : []).filter((item) => {
    if (item.role === 'background') return false;
    if (!['image', 'shape'].includes(item.type)) return false;
    const box = { x: Number(item.x) || 0, y: Number(item.y) || 0, width: Number(item.width) || 0, height: Number(item.height) || 0 };
    if (Math.min(box.width, box.height) < 12) return false;               // a rule or a line
    const size = area(box);
    if (forBody && isPicture(item) && !coversPage(box) && size >= MIN_ART_AREA) return true;
    if (size < MIN_ART_AREA || size >= PAGE_SIZED) return false;
    if (item.type === 'shape') {
      // A shape with no fill and no outline draws nothing; a translucent one is a tint the text may sit on.
      const fill = String(item.fill || '');
      if (!fill || fill === 'transparent') return Boolean(item.borderColor && item.borderColor !== 'transparent');
      const alpha = /rgba\(.*,\s*([0-9.]+)\)$/.exec(fill);
      if (alpha && Number(alpha[1]) < 0.5) return false;
    }
    return true;
  }).map((item) => ({ x: Number(item.x) || 0, y: Number(item.y) || 0, width: Number(item.width) || 0, height: Number(item.height) || 0 }));
}

// The ways to shrink `box` so it clears `obstacle`, each a new box (or null when it would be too small).
function clearances(box, obstacle, min) {
  const right = box.x + box.width;
  const bottom = box.y + box.height;
  const options = [
    { ...box, width: obstacle.x - GAP - box.x },                                        // text stays left of the art
    { ...box, x: obstacle.x + obstacle.width + GAP, width: right - (obstacle.x + obstacle.width + GAP) }, // right of it
    { ...box, height: obstacle.y - GAP - box.y },                                       // above the art
    { ...box, y: obstacle.y + obstacle.height + GAP, height: bottom - (obstacle.y + obstacle.height + GAP) }, // below it
  ];
  // Or keep the size and slide the box a short way up or down past the art.
  options.push(
    { ...box, y: obstacle.y - GAP - box.height },
    { ...box, y: obstacle.y + obstacle.height + GAP },
  );
  return options.filter((next) => Math.abs(next.y - box.y) <= MAX_SHIFT && next.width >= min.w && next.height >= min.h
    && next.x >= 0 && next.y >= 0 && next.x + next.width <= CANVAS_W && next.y + next.height <= CANVAS_H);
}

function fitBox(box, obstacles, min) {
  let current = { ...box };
  for (let step = 0; step < 6; step += 1) {
    let worst = null;
    let worstOverlap = 0;
    for (const obstacle of obstacles) {
      const shared = overlap(current, obstacle);
      // The text is meant to sit inside this piece (a card, a panel): not a collision.
      if (shared >= 0.9 * area(current)) continue;
      if (shared > worstOverlap) { worst = obstacle; worstOverlap = shared; }
    }
    if (!worst || worstOverlap < 0.02 * area(current)) return current;
    const options = clearances(current, worst, min);
    if (!options.length) return current;
    current = options.reduce((best, next) => (area(next) > area(best) ? next : best));
  }
  return current;
}

/**
 * Moves the title and body boxes clear of the template's art, then makes sure the body does not
 * sit on the title. Returns new elements; the input is not changed.
 */
export function avoidArt(elements, decor) {
  const titleObstacles = artObstacles(decor);
  const bodyObstacles = artObstacles(decor, { forBody: true });
  const next = elements.map((element) => ({ ...element }));
  const text = next.filter((el) => el.type === 'text' && ['title', 'body'].includes(el.role));
  for (const el of text) {
    const min = MIN_BOX[el.role];
    const obstacles = el.role === 'body' ? bodyObstacles : titleObstacles;
    if (!obstacles.length) continue;
    const fitted = fitBox({ x: el.x, y: el.y, width: el.width, height: el.height }, obstacles, min);
    el.x = Math.round(fitted.x); el.y = Math.round(fitted.y);
    el.width = Math.round(fitted.width); el.height = Math.round(fitted.height);
  }
  // A title squeezed beside the art can end up on the body (or the other way round).
  const title = text.find((el) => el.role === 'title');
  for (const body of text.filter((el) => el.role === 'body')) {
    if (!title || !overlap(title, body)) continue;
    const top = title.y + title.height + 10;
    const height = body.y + body.height - top;
    if (top > body.y && height >= MIN_BOX.body.h) { body.y = Math.round(top); body.height = Math.round(height); }
  }
  // The app's own picture, table or chart must not cover the title (whose text can run past its box).
  if (title) {
    const bottom = Math.max(title.y + title.height, title.y + estimatedTextHeight(title));
    for (const visual of next.filter((el) => ['image', 'table', 'chart'].includes(el.type))) {
      const side = { x: title.x, y: title.y, width: title.width, height: bottom - title.y };
      if (!overlap(side, visual) || visual.y >= bottom) continue;
      const top = Math.round(bottom + 10);
      const height = visual.y + visual.height - top;
      if (height >= 120) { visual.y = top; visual.height = Math.round(height); }
    }
  }
  return next;
}

/**
 * Puts the title and body inside the calm part of the template's picture (see imageCalm.js) when
 * they lie partly on its detailed part. The title takes the top of the calm area and the body the
 * rest; a calm area too small to hold them leaves the boxes alone (readable panels cover that case).
 */
export function fitToCalm(elements, calm) {
  if (!calm || area(calm) < 0.2 * CANVAS_W * CANVAS_H) return elements;
  const pad = 14;
  const room = { x: calm.x + pad, y: calm.y + pad, width: calm.width - 2 * pad, height: calm.height - 2 * pad };
  const text = elements.filter((el) => el.type === 'text' && ['title', 'body'].includes(el.role));
  const outside = (el) => area(el) - overlap(el, room) > 0.15 * area(el);
  if (!text.some(outside) || room.width < MIN_BOX.body.w || room.height < MIN_BOX.title.h + MIN_BOX.body.h) return elements;
  const title = text.find((el) => el.role === 'title');
  const bodies = text.filter((el) => el.role === 'body');
  const next = elements.map((el) => ({ ...el }));
  const byRef = (source) => next[elements.indexOf(source)];
  let top = room.y;
  if (title) {
    const t = byRef(title);
    const limit = bodies.length ? room.height * 0.4 : room.height;
    // The title keeps its size while it fits; a narrow calm area shrinks it rather than letting it run over the body.
    let size = Number(title.style?.fontSize) || 32;
    const probe = { ...t, width: room.width, style: { ...t.style, fontSize: size } };
    while (size > 20 && estimatedTextHeight({ ...probe, style: { ...probe.style, fontSize: size } }) + 8 > limit) size -= 2;
    t.style = { ...t.style, fontSize: size };
    const height = Math.min(Math.max(MIN_BOX.title.h, estimatedTextHeight({ ...probe, style: { ...probe.style, fontSize: size } }) + 8), limit);
    t.x = Math.round(room.x); t.width = Math.round(room.width);
    t.y = Math.round(top); t.height = Math.round(height);
    top += height + 10;
  }
  bodies.forEach((body, index) => {
    const b = byRef(body);
    const share = (room.y + room.height - top) / (bodies.length - index);
    b.x = Math.round(room.x); b.width = Math.round(room.width);
    b.y = Math.round(top); b.height = Math.round(Math.max(MIN_BOX.body.h, share - (index < bodies.length - 1 ? 10 : 0)));
    top += b.height + 10;
  });
  return next;
}

const luminance = (color) => {
  const m = /^#?([0-9a-f]{6})$/i.exec(String(color || '').trim());
  if (!m) return null;
  const v = parseInt(m[1], 16);
  return (0.2126 * ((v >> 16) & 255) + 0.7152 * ((v >> 8) & 255) + 0.0722 * (v & 255)) / 255;
};

// A translucent piece the template drew over its own picture (a dark sheet) already makes text readable.
function hasOverlay(decor, picture, box) {
  const after = decor.slice(decor.indexOf(picture) + 1);
  return after.some((item) => {
    if (item.type !== 'shape' || !item.fill) return false;
    const alpha = /rgba\(.*,\s*([0-9.]+)\)$/.exec(String(item.fill));
    const solid = alpha ? Number(alpha[1]) : (/^#[0-9a-f]{6}$/i.test(item.fill) ? 1 : 0);
    const cover = { x: Number(item.x) || 0, y: Number(item.y) || 0, width: Number(item.width) || 0, height: Number(item.height) || 0 };
    return solid >= 0.4 && overlap(box, cover) >= 0.8 * area(box);
  });
}

/**
 * Text lying on a picture the template left bare (a photo behind the whole slide) cannot be read,
 * and moving it is not possible when the photo is the page. Give such a text box a soft panel behind
 * it, light for dark text and dark for light text.
 */
export function withReadablePanels(elements, decor) {
  const pictures = (Array.isArray(decor) ? decor : []).filter((item) => item.type === 'image');
  if (!pictures.length) return elements;
  const out = [];
  elements.forEach((el) => {
    if (['table', 'chart'].includes(el.type)) {
      // A table or chart cannot be read over a busy picture either: set a soft sheet behind it.
      const frame = { x: el.x, y: el.y, width: el.width, height: el.height };
      const busy = pictures.some((picture) => {
        const pic = { x: Number(picture.x) || 0, y: Number(picture.y) || 0, width: Number(picture.width) || 0, height: Number(picture.height) || 0 };
        return overlap(frame, pic) >= 0.25 * area(frame) && !hasOverlay(decor, picture, frame);
      });
      if (busy) {
        out.push({
          id: `${el.id || 'visual'}-sheet`, type: 'shape', shape: 'rect', role: 'decoration', locked: true,
          x: frame.x - 8, y: frame.y - 8, width: frame.width + 16, height: frame.height + 16,
          fill: 'rgba(255, 255, 255, 0.86)', borderColor: 'transparent', borderWidth: 0, borderRadius: 10, rotation: 0,
        });
      }
      out.push(el);
      return;
    }
    out.push(withTextPanel(el));
  });
  return out;

  function withTextPanel(el) {
    if (el.type !== 'text' || !['title', 'body'].includes(el.role)) return el;
    const box = { x: el.x, y: el.y, width: el.width, height: el.height };
    const busy = pictures.some((picture) => {
      const frame = { x: Number(picture.x) || 0, y: Number(picture.y) || 0, width: Number(picture.width) || 0, height: Number(picture.height) || 0 };
      return overlap(box, frame) >= 0.25 * area(box) && !hasOverlay(decor, picture, box);
    });
    if (!busy || el.style?.background) return el;
    const dark = (luminance(el.style?.color) ?? 0) < 0.5;
    return {
      ...el,
      style: {
        ...el.style,
        background: dark ? 'rgba(255, 255, 255, 0.82)' : 'rgba(0, 0, 0, 0.55)',
        padding: '8px 14px',
        borderRadius: '10px',
      },
    };
  }
}

/** Rough height of an element's text from its length, width and font size (HTML tags ignored). */
export function estimatedTextHeight(el) {
  const text = String(el.content || '').replace(/<[^>]*>/g, '').trim();
  const size = Number(el.style?.fontSize) || (el.role === 'title' ? 32 : 18);
  // Headings are set in wide display faces: count their letters wider than body text.
  const perLine = Math.max(1, Math.floor((el.width || 1) / (size * (el.role === 'title' ? 0.7 : 0.6))));
  const lines = Math.max(1, Math.ceil(text.length / perLine));
  return lines * size * (Number(el.style?.lineHeight) || 1.2);
}

/**
 * A rule the template drew between its own sample text rows would cut through the new text: drop
 * thin lines that cross the inside of a title or body box.
 */
export function withoutCrossingRules(decor, elements) {
  const boxes = elements.filter((el) => el.type === 'text' && ['title', 'body'].includes(el.role));
  return (Array.isArray(decor) ? decor : []).filter((item) => {
    const w = Number(item.width) || 0;
    const h = Number(item.height) || 0;
    const horizontal = h < 6 && w >= 120;
    const vertical = w < 6 && h >= 120;
    if (item.type !== 'shape' || (!horizontal && !vertical)) return true;
    return !boxes.some((box) => (horizontal
      ? item.y > box.y + 24 && item.y < box.y + box.height - 24
        && Math.min(item.x + w, box.x + box.width) - Math.max(item.x, box.x) >= 0.5 * box.width
      : item.x > box.x + 24 && item.x < box.x + box.width - 24
        && Math.min(item.y + h, box.y + box.height) - Math.max(item.y, box.y) >= 0.5 * box.height));
  });
}

