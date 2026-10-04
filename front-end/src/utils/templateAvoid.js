// After a custom template's art and the slide's text are both placed, text can still land on a
// photo or a shape (art in the middle of the slide, a row of pictures, art above or below the text).
// `avoidArt` finds those collisions and pulls the text box into the largest free space beside or
// above/below the art. Art that the text is meant to sit on (a panel, a card, the backdrop) is left
// alone, and a box that cannot be moved without becoming unreadably small is left where it is.

const CANVAS_W = 960;
const CANVAS_H = 540;
const GAP = 16;
const CLUSTER_GAP = 22;                            // pieces this close belong to one drawing
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
    // Shapes (cards, panels, tints) are what the text is laid on, never something to dodge.
    if (item.type === 'shape') return false;
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
 * A diagram left over from a deck's own content is many small pieces sitting together (boxes,
 * arrows, labels). Each is too small to count as an obstacle, yet together they cover the text.
 * Drops every cluster of four or more small pieces whose bounding box lies on a text box; a
 * cluster clear of the text (a template's own pattern of dots or icons) stays.
 */
export function withoutClustersOnText(decor, elements) {
  const list = Array.isArray(decor) ? decor : [];
  const boxes = elements.filter((el) => el.type === 'text' && ['title', 'body'].includes(el.role));
  const boxOf = (item) => ({ x: Number(item.x) || 0, y: Number(item.y) || 0, width: Number(item.width) || 0, height: Number(item.height) || 0 });
  const small = list.filter((item) => item.role !== 'background' && ['image', 'shape'].includes(item.type)
    && area(boxOf(item)) < 0.04 * CANVAS_W * CANVAS_H);
  const parent = small.map((_, index) => index);
  const find = (i) => (parent[i] === i ? i : (parent[i] = find(parent[i])));
  const near = (a, b) => a.x - CLUSTER_GAP < b.x + b.width && b.x - CLUSTER_GAP < a.x + a.width
    && a.y - CLUSTER_GAP < b.y + b.height && b.y - CLUSTER_GAP < a.y + a.height;
  for (let i = 0; i < small.length; i += 1) {
    for (let j = i + 1; j < small.length; j += 1) {
      if (near(boxOf(small[i]), boxOf(small[j]))) parent[find(i)] = find(j);
    }
  }
  const groups = new Map();
  small.forEach((item, index) => {
    const root = find(index);
    if (!groups.has(root)) groups.set(root, []);
    groups.get(root).push(item);
  });
  const doomed = new Set();
  groups.forEach((members) => {
    if (members.length < 4) return;
    const xs = members.map(boxOf);
    const x0 = Math.min(...xs.map((b) => b.x));
    const y0 = Math.min(...xs.map((b) => b.y));
    const bound = { x: x0, y: y0, width: Math.max(...xs.map((b) => b.x + b.width)) - x0, height: Math.max(...xs.map((b) => b.y + b.height)) - y0 };
    if (boxes.some((text) => overlap(bound, text) >= 0.25 * area(bound))) members.forEach((item) => doomed.add(item));
  });
  return doomed.size ? list.filter((item) => !doomed.has(item)) : list;
}

/**
 * A picture the body text still lies on after `avoidArt` had no room to move it (a figure in the
 * middle of the slide) is content of the file the template came from, not its look: drop it.
 * Backdrops stay, and so does a picture only the title sits on (a header photo).
 */
export function withoutPicturesUnderBody(decor, elements) {
  const bodies = elements.filter((el) => el.type === 'text' && el.role === 'body');
  return (Array.isArray(decor) ? decor : []).filter((item) => {
    if (!isPicture(item)) return true;
    const box = { x: Number(item.x) || 0, y: Number(item.y) || 0, width: Number(item.width) || 0, height: Number(item.height) || 0 };
    if (coversPage(box)) return true;
    return !bodies.some((body) => overlap(box, body) >= 0.15 * area(body));
  });
}

export function withoutTextBackings(decor, elements) {
  const boxes = elements.filter((el) => el.type === 'text' && ['title', 'body'].includes(el.role));
  return (Array.isArray(decor) ? decor : []).filter((item) => {
    if (item.type !== 'shape' || item.role === 'background') return true;
    const box = { x: Number(item.x) || 0, y: Number(item.y) || 0, width: Number(item.width) || 0, height: Number(item.height) || 0 };
    if (Math.min(box.width, box.height) < 12 || area(box) >= PAGE_SIZED) return true;   // lines and page-sized art stay
    // A coloured card or panel lying under the text is dropped, so the text sits on the page like the rest.
    return !boxes.some((text) => overlap(box, text) >= 0.4 * area(box));
  });
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

