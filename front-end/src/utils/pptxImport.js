// Turns a parsed real .pptx (templateService.importSlides' response) into slide objects the
// editor already knows how to render and save — each returned layout is a faithful, ordered
// copy of one real slide, so this is a straight conversion, not a template match.
//
// Known limits of this v1: native PowerPoint tables/charts aren't extracted (that slide's
// text and pictures still come through, the table/chart itself doesn't); grouped shapes and
// SmartArt aren't unpacked; a picture used purely as a small logo near the slide edge may be
// skipped (the same "is this actually decoration" heuristic the template-upload feature uses).
import { buildTemplateArt } from './templateArt.js';
import { newElementId } from './selection.js';

const ROLE_MAP = { title: 'title', body: 'body', pageNumber: 'pageNumber' };

function mapTextElement(element) {
  const style = element.style ? { ...element.style } : {};
  // A slide number keeps the size the file gave it instead of being auto-fitted like body text.
  if (element.role === 'pageNumber') style.fontSizeLocked = true;
  return {
    id: newElementId(),
    type: 'text',
    role: ROLE_MAP[element.role] || 'custom',
    x: Number(element.x) || 0,
    y: Number(element.y) || 0,
    width: Number(element.width) || 0,
    height: Number(element.height) || 0,
    rotation: Number(element.rotation) || 0,
    content: element.content || '',
    style,
  };
}

// A table from the file, in the shape the editor's own tables use.
function mapTableElement(element) {
  return {
    id: newElementId(),
    type: 'table',
    role: 'visual',
    x: Number(element.x) || 0,
    y: Number(element.y) || 0,
    width: Number(element.width) || 0,
    height: Number(element.height) || 0,
    rotation: 0,
    data: element.data,
  };
}

const DECOR_BUDGET = 55000;

// Whole pixels (a tenth for the small ones) are all a drawing needs; the digits saved are what lets
// a diagram of a hundred lines fit in the budget.
const tidy = (value) => (Math.abs(value) < 20 ? Math.round(value * 10) / 10 : Math.round(value));
// A straight-segment path with the points that add nothing (Ramer-Douglas-Peucker) taken out.
function simplifyPath(d, tolerance) {
  if (typeof d !== 'string' || d.length < 120 || /[^MLZ0-9.\s-]/.test(d)) return d;
  const commands = d.match(/[MLZ][^MLZ]*/g) || [];
  const out = [];
  let run = [];
  const flush = (closed) => {
    if (run.length > 2) {
      const keep = new Array(run.length).fill(false);
      keep[0] = true; keep[run.length - 1] = true;
      // A loop starts where it ends, so it is cut at its farthest point and both halves simplified.
      const [sx, sy] = run[0];
      const loop = run[run.length - 1][0] === sx && run[run.length - 1][1] === sy;
      let far = run.length - 1;
      if (loop) {
        let best = -1;
        run.forEach(([x, y], i) => { const d = Math.hypot(x - sx, y - sy); if (d > best) { best = d; far = i; } });
        keep[far] = true;
      }
      const stack = loop ? [[0, far], [far, run.length - 1]] : [[0, run.length - 1]];
      while (stack.length) {
        const [a, b] = stack.pop();
        let worst = 0; let index = -1;
        for (let i = a + 1; i < b; i += 1) {
          const [px, py] = run[i]; const [ax, ay] = run[a]; const [bx, by] = run[b];
          const length = Math.hypot(bx - ax, by - ay) || 1;
          const distance = Math.abs((by - ay) * px - (bx - ax) * py + bx * ay - by * ax) / length;
          if (distance > worst) { worst = distance; index = i; }
        }
        if (worst > tolerance && index > 0) { keep[index] = true; stack.push([a, index], [index, b]); }
      }
      run = run.filter((_, i) => keep[i]);
    }
    run.forEach(([x, y], i) => out.push(`${i === 0 ? 'M' : 'L'} ${x} ${y}`));
    if (closed) out.push('Z');
    run = [];
  };
  commands.forEach((command) => {
    const kind = command[0];
    if (kind === 'Z') { flush(true); return; }
    const nums = command.slice(1).trim().split(/\s+/).map(Number);
    if (kind === 'M') flush(false);
    run.push([nums[0], nums[1]]);
  });
  flush(false);
  return out.join(' ');
}

// A closed run of points that all lie on the ellipse filling the box is an ellipse (what a
// drawing program exports a circle or an oval as), and the editor has a real one.
function isEllipsePath(d) {
  if (typeof d !== 'string' || /[^MLZ0-9.\s-]/.test(d)) return false;
  const points = (d.match(/-?\d+(?:\.\d+)?\s+-?\d+(?:\.\d+)?/g) || []).map((pair) => pair.split(/\s+/).map(Number));
  if (points.length < 12) return false;
  const [firstX, firstY] = points[0];
  const [lastX, lastY] = points[points.length - 1];
  if (Math.hypot(firstX - lastX, firstY - lastY) > 3) return false;
  return points.every(([x, y]) => Math.abs(Math.hypot((x - 50) / 50, (y - 50) / 50) - 1) < 0.06);
}

const compactArt = (item) => {
  const out = { ...item };
  ['x', 'y', 'width', 'height', 'rotation'].forEach((key) => { if (typeof out[key] === 'number') out[key] = Math.round(out[key] * 10) / 10; });
  if (typeof out.borderWidth === 'number') out.borderWidth = tidy(out.borderWidth);
  if (out.opacity === 1) delete out.opacity;
  if (out.style?.shape === 'path' && isEllipsePath(out.style.path)) {
    out.style = { ...out.style, shape: 'ellipse' };
    delete out.style.path;
  }
  const tolerance = 0.8 * 100 / Math.max(1, out.width || 1, out.height || 1);
  if (typeof out.path === 'string') out.path = simplifyPath(out.path, tolerance);
  if (typeof out.style?.path === 'string') out.style = { ...out.style, path: simplifyPath(out.style.path, tolerance) };
  if (typeof out.id === 'string') out.id = out.id.replace(/^orn-\d+-/, 'o');
  return out;
};

export function slidesFromImportedManifest(manifest) {
  const layouts = Array.isArray(manifest?.layouts) ? manifest.layouts : [];
  return layouts.map((layout) => {
    // buildTemplateArt already knows how to pick the page colour, tell decoration from
    // background, and reserve a safe area for text around any big picture — the exact same
    // pass a matched template's sample layout goes through, so it's reused as-is here.
    const art = buildTemplateArt({ backgroundColor: layout.backgroundColor, elements: layout.decor || [] });
    // `_imported` marks a slide that is a faithful copy of a real one: the editor must keep its
    // boxes where the file put them, not re-match the slide against the deck's template on load
    // (that re-flows every slide and saves the result over the copy).
    const richText = { _imported: true };
    if (art.decor.length) {
      // A slide's rich text is stored in a 64 KB column; a drawing of hundreds of shapes is cut
      // at that budget (the rest is the least important: they come last) rather than refused.
      let budget = DECOR_BUDGET;
      richText._decor = art.decor.map(compactArt).filter((item) => (budget -= JSON.stringify(item).length) >= 0);
      if (art.pageColor) richText._tplBg = art.pageColor;
      if (art.safe) richText._safe = art.safe;
    }
    const elements = (layout.elements || [])
      .filter((element) => element.type === 'text' && String(element.content || '').trim())
      .map(mapTextElement);
    const tables = (layout.elements || [])
      .filter((element) => element.type === 'table' && element.data?.headers?.length)
      .map(mapTableElement);
    return {
      id: null,
      type: layout.type || 'content',
      notes: '',
      richText,
      elements: [...elements, ...tables],
      // The slide's first table is also its table, which is what the AI and the outline read.
      ...(tables.length ? { table: tables[0].data, primaryVisual: 'table' } : {}),
    };
  });
}
