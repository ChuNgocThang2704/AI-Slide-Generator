import test from 'node:test';
import assert from 'node:assert/strict';
import { calmRect, busyGrid } from '../src/utils/imageCalm.js';
import { fitToCalm } from '../src/utils/templateAvoid.js';

const grid = (busyRows) => Array.from({ length: 14 }, (_, row) => new Array(24).fill(row < busyRows));

test('a photo on top of a plain area leaves the plain area as the calm rectangle', () => {
  const rect = calmRect(grid(6));           // top 6 of 14 rows are detailed
  assert.equal(rect.x, 0);
  assert.equal(rect.width, 960);
  assert.ok(Math.abs(rect.y - (6 * 540) / 14) < 1);
  assert.ok(Math.abs(rect.height - (8 * 540) / 14) < 1);
});

test('a picture that is detailed everywhere has no calm rectangle', () => {
  assert.equal(calmRect(grid(14)), null);
});

test('busyGrid tells detail from a flat area', () => {
  const w = 192; const h = 108; const luma = new Float32Array(w * h).fill(200);
  for (let y = 0; y < 40; y += 1) for (let x = 0; x < w; x += 1) luma[y * w + x] = (x + y) % 2 ? 30 : 220; // detailed top
  const busy = busyGrid(luma, w, h);
  assert.equal(busy[0][5], true);
  assert.equal(busy[13][5], false);
});

test('text lying on the detailed part moves into the calm area, title above body', () => {
  const calm = { x: 0, y: 231, width: 960, height: 309 };
  const text = (role, x, y, width, height) => ({ type: 'text', role, x, y, width, height, content: '<p>Tiêu đề</p>', style: { fontSize: 32 } });
  const [title, body] = fitToCalm([text('title', 96, 60, 520, 100), text('body', 96, 190, 800, 280)], calm);
  assert.ok(title.y >= 231 && body.y >= title.y + title.height);
  assert.ok(body.y + body.height <= 540);
});

test('text already in the calm area, or a calm area too small, is left alone', () => {
  const box = { type: 'text', role: 'body', x: 100, y: 300, width: 700, height: 150 };
  assert.deepEqual(fitToCalm([box], { x: 0, y: 231, width: 960, height: 309 })[0], box);
  assert.deepEqual(fitToCalm([{ ...box, y: 50 }], { x: 0, y: 400, width: 300, height: 100 })[0].y, 50);
});
