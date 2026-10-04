import test from 'node:test';
import assert from 'node:assert/strict';
import { avoidArt, artObstacles } from '../src/utils/templateAvoid.js';

const text = (role, x, y, width, height) => ({ type: 'text', role, x, y, width, height });
const photo = (x, y, width, height) => ({ type: 'image', role: 'decoration', x, y, width, height, src: 'asset:p.jpg' });
const overlaps = (a, b) => Math.min(a.x + a.width, b.x + b.width) > Math.max(a.x, b.x)
  && Math.min(a.y + a.height, b.y + b.height) > Math.max(a.y, b.y);

test('text lying on a photo on its right is pulled left of it', () => {
  const art = photo(600, 100, 300, 340);
  const [body] = avoidArt([text('body', 64, 150, 800, 300)], [art]);
  assert.ok(!overlaps(body, art));
  assert.equal(body.x, 64);
  assert.ok(body.width >= 240);
});

test('a row of photos across the middle leaves the text above or below it', () => {
  const row = [photo(40, 227, 157, 227), photo(210, 227, 157, 227), photo(380, 227, 157, 227), photo(550, 227, 157, 227)];
  const [title] = avoidArt([text('title', 64, 160, 800, 140)], row);
  row.forEach((art) => assert.ok(!overlaps(title, art)));
});

test('art the text is meant to sit on is not an obstacle', () => {
  const panel = { type: 'shape', role: 'decoration', x: 0, y: 0, width: 462, height: 540, fill: 'rgba(255, 255, 255, 0.23)' };
  const backdrop = { type: 'image', role: 'background', x: 0, y: 0, width: 960, height: 540 };
  const card = { type: 'shape', role: 'decoration', x: 50, y: 140, width: 400, height: 260, fill: '#112233' };
  assert.deepEqual(artObstacles([panel, backdrop]), []);
  const box = text('body', 64, 160, 360, 220);
  assert.deepEqual(avoidArt([box], [card])[0], box);   // text fully inside a card stays put
});

test('lines, tiny marks and unfilled shapes are ignored', () => {
  const small = [
    { type: 'shape', role: 'decoration', x: 0, y: 80, width: 900, height: 2, fill: '#999' },
    photo(10, 10, 40, 40),
    { type: 'shape', role: 'decoration', x: 300, y: 100, width: 200, height: 200, fill: 'transparent' },
  ];
  assert.deepEqual(artObstacles(small), []);
});

test('a box that would become unreadably small is left alone, and the input is not changed', () => {
  const art = photo(100, 0, 760, 540 - 0);   // leaves no usable gap beside it
  const input = [text('body', 120, 100, 700, 300)];
  const before = JSON.stringify(input);
  const out = avoidArt(input, [art]);
  assert.equal(JSON.stringify(input), before);
  assert.equal(out[0].width, 700);
});

test('after the title is squeezed, the body is kept off it', () => {
  const art = photo(560, 120, 340, 300);
  const out = avoidArt([text('title', 64, 60, 800, 120), text('body', 64, 100, 800, 380)], [art]);
  const [title, body] = out;
  assert.ok(!overlaps(title, body));
  assert.ok(!overlaps(body, art));
});
