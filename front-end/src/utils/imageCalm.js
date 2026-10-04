// Where on a template's picture text can be read: a slide sample is often one full-slide picture
// (a photo on top of a plain sky or white area). The calm part of such a picture, the cells with
// little detail, is where the title and body belong. `calmRect` works on a grid of cell "busyness"
// so it can be tested without a browser; `calmRegionOf` fills the grid from a real picture.

const CANVAS_W = 960;
const CANVAS_H = 540;
const COLS = 24;
const ROWS = 14;
const cache = new Map();

/**
 * The largest block of calm cells, as a rectangle in slide pixels, or null when too little of the
 * picture is calm. `busy` is a ROWS x COLS matrix of booleans (true = detailed).
 */
export function calmRect(busy, cols = COLS, rows = ROWS) {
  const heights = new Array(cols).fill(0);
  let best = null;
  for (let row = 0; row < rows; row += 1) {
    for (let col = 0; col < cols; col += 1) heights[col] = busy[row][col] ? 0 : heights[col] + 1;
    // Largest rectangle under the histogram of calm run-lengths.
    const stack = [];
    for (let col = 0; col <= cols; col += 1) {
      const h = col === cols ? 0 : heights[col];
      let start = col;
      while (stack.length && stack[stack.length - 1].height >= h) {
        const top = stack.pop();
        const size = top.height * (col - top.start);
        if (!best || size > best.size) best = { size, col0: top.start, col1: col, row0: row - top.height + 1, row1: row + 1 };
        start = top.start;
      }
      stack.push({ start, height: h });
    }
  }
  if (!best || best.size < 0.18 * cols * rows) return null;
  const cw = CANVAS_W / cols;
  const ch = CANVAS_H / rows;
  return { x: best.col0 * cw, y: best.row0 * ch, width: (best.col1 - best.col0) * cw, height: (best.row1 - best.row0) * ch };
}

/** Marks each grid cell as detailed (true) or calm from per-pixel luminance (0-255). */
export function busyGrid(luma, width, height, cols = COLS, rows = ROWS) {
  const grid = Array.from({ length: rows }, () => new Array(cols).fill(false));
  const cellW = width / cols;
  const cellH = height / rows;
  for (let row = 0; row < rows; row += 1) {
    for (let col = 0; col < cols; col += 1) {
      let sum = 0; let sumSq = 0; let edge = 0; let count = 0;
      for (let y = Math.floor(row * cellH); y < Math.floor((row + 1) * cellH); y += 1) {
        for (let x = Math.floor(col * cellW); x < Math.floor((col + 1) * cellW); x += 1) {
          const v = luma[y * width + x];
          sum += v; sumSq += v * v; count += 1;
          if (x + 1 < width) edge += Math.abs(v - luma[y * width + x + 1]);
          if (y + 1 < height) edge += Math.abs(v - luma[(y + 1) * width + x]);
        }
      }
      if (!count) continue;
      const mean = sum / count;
      const std = Math.sqrt(Math.max(0, sumSq / count - mean * mean));
      grid[row][col] = std > 22 || edge / (count * 2) > 6;
    }
  }
  return grid;
}

/** Calm rectangle of a picture at `src`, or null (cached). Browser only. */
export async function calmRegionOf(src) {
  if (!src || typeof document === 'undefined') return null;
  if (cache.has(src)) return cache.get(src);
  const result = await new Promise((resolve) => {
    const image = new Image();
    image.crossOrigin = 'anonymous';
    image.onload = () => {
      try {
        const w = 192;
        const h = 108;
        const canvas = document.createElement('canvas');
        canvas.width = w; canvas.height = h;
        const ctx = canvas.getContext('2d', { willReadFrequently: true });
        ctx.drawImage(image, 0, 0, w, h);
        const { data } = ctx.getImageData(0, 0, w, h);
        const luma = new Float32Array(w * h);
        for (let i = 0; i < w * h; i += 1) luma[i] = 0.2126 * data[i * 4] + 0.7152 * data[i * 4 + 1] + 0.0722 * data[i * 4 + 2];
        resolve(calmRect(busyGrid(luma, w, h)));
      } catch {
        resolve(null);
      }
    };
    image.onerror = () => resolve(null);
    image.src = src;
  });
  cache.set(src, result);
  return result;
}
