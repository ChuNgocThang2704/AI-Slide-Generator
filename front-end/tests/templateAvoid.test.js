import test from 'node:test';
import assert from 'node:assert/strict';
import { avoidArt, artObstacles, withoutCrossingRules, withReadablePanels } from '../src/utils/templateAvoid.js';

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

test('body text keeps off a header photo band, a title may sit on it', () => {
  const band = { type: 'image', role: 'decoration', x: 0, y: 0, width: 960, height: 265, src: 'asset:band.jpg' };
  const [title, body] = avoidArt([text('title', 96, 60, 520, 100), text('body', 96, 190, 800, 280)], [band]);
  assert.equal(title.y, 60);
  assert.ok(body.y >= 265, 'body.y=' + body.y);
  assert.ok(body.y + body.height <= 540);
});

test('rules that cut through the new text are dropped, a rule under the title stays', () => {
  const rule = (y) => ({ type: 'shape', role: 'decoration', x: 40, y, width: 880, height: 2, fill: '#456' });
  const kept = withoutCrossingRules([rule(370), rule(460), rule(170)], [text('title', 96, 60, 520, 100), text('body', 96, 190, 800, 250)]);
  assert.deepEqual(kept.map((r) => r.y), [460, 170]);
});

test('a picture placed over the title is moved below the title text', () => {
  const title = { ...text('title', 630, 70, 300, 100), content: '<p>Chính Sách Kinh Tế và Đỉnh Cao Di Sản Văn Hóa</p>', style: { fontSize: 38 } };
  const image = { type: 'image', x: 104, y: 178, width: 841, height: 330 };
  const out = avoidArt([title, image], [{ type: 'image', role: 'decoration', x: 0, y: 0, width: 960, height: 200 }]);
  const moved = out.find((el) => el.type === 'image');
  assert.ok(moved.y > 178 && moved.height >= 120);
});

test('text over a bare photo gets a soft panel, over the template sheet it does not', () => {
  const photo = { type: 'image', role: 'decoration', x: 0, y: 0, width: 960, height: 540 };
  const sheet = { type: 'shape', role: 'decoration', x: 0, y: 0, width: 960, height: 540, fill: 'rgba(0, 0, 0, 0.79)' };
  const dark = { ...text('body', 96, 190, 800, 250), style: { color: '#123456' } };
  const [bare] = withReadablePanels([dark], [photo]);
  assert.match(bare.style.background, /255, 255, 255/);
  const [covered] = withReadablePanels([dark], [photo, sheet]);
  assert.equal(covered.style.background, undefined);
});
