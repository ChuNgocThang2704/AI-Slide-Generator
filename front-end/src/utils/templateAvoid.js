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

/** The pieces of a template's art that text must keep clear of. */
export function artObstacles(decor) {
  return (Array.isArray(decor) ? decor : []).filter((item) => {
    if (item.role === 'background') return false;
    if (!['image', 'shape'].includes(item.type)) return false;
    const box = { x: Number(item.x) || 0, y: Number(item.y) || 0, width: Number(item.width) || 0, height: Number(item.height) || 0 };
    if (Math.min(box.width, box.height) < 12) return false;               // a rule or a line
    const size = area(box);
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
  const obstacles = artObstacles(decor);
  if (!obstacles.length) return elements;
  const next = elements.map((element) => ({ ...element }));
  const text = next.filter((el) => el.type === 'text' && ['title', 'body'].includes(el.role));
  for (const el of text) {
    const min = MIN_BOX[el.role];
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
  return next;
}

