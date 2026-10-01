import test from 'node:test';
import assert from 'node:assert/strict';
import {
  alignPatches, applyPatches, boundsOf, cloneSelection, distributePatches, expandToGroups, groupElements,
  hasGroup, marqueeSelect, moveWithinSlide, reorderLayers, snapBox, toggleInSelection, ungroupElements,
} from '../src/utils/selection.js';

const el = (id, x, y, width, height, extra = {}) => ({ id, type: 'shape', x, y, width, height, ...extra });
const sample = () => [el('a', 100, 100, 100, 50), el('b', 300, 200, 60, 80), el('c', 500, 60, 120, 40)];

test('bounds cover every picked element', () => {
  assert.deepEqual(boundsOf(sample(), ['a', 'b', 'c']), { x: 100, y: 60, width: 520, height: 220 });
  assert.equal(boundsOf(sample(), ['zzz']), null);
});

test('several elements align to the selection; a single one aligns to the slide', () => {
  const list = sample();
  const left = alignPatches(list, ['a', 'b', 'c'], 'left');
  assert.deepEqual(left, { b: { x: 100, y: 200 }, c: { x: 100, y: 60 } });
  const right = applyPatches(list, alignPatches(list, ['a', 'b', 'c'], 'right'));
  right.forEach((item) => assert.equal(item.x + item.width, 620));
  const middle = applyPatches(list, alignPatches(list, ['a', 'b', 'c'], 'middle'));
  middle.forEach((item) => assert.equal(item.y + item.height / 2, 170));
  // one element -> the slide itself
  assert.deepEqual(alignPatches(list, ['a'], 'center'), { a: { x: 430, y: 100 } });
  assert.deepEqual(alignPatches(list, ['a'], 'bottom'), { a: { x: 100, y: 490 } });
  assert.deepEqual(alignPatches(list, ['a'], 'nonsense'), {});
});

test('distribute leaves the outer two in place and evens the gaps', () => {
  const list = [el('a', 0, 0, 100, 40), el('b', 150, 0, 100, 40), el('c', 700, 0, 100, 40)];
  const next = applyPatches(list, distributePatches(list, ['a', 'b', 'c'], 'h'));
  assert.equal(next.find((i) => i.id === 'a').x, 0);
  assert.equal(next.find((i) => i.id === 'c').x, 700);
  const [a, b, c] = ['a', 'b', 'c'].map((id) => next.find((i) => i.id === id));
  assert.equal(b.x - (a.x + a.width), c.x - (b.x + b.width), 'gaps are equal');
  assert.deepEqual(distributePatches(list, ['a', 'b'], 'h'), {}, 'needs three or more');
  const vertical = [el('a', 0, 0, 40, 100), el('b', 0, 130, 40, 100), el('c', 0, 400, 40, 100)];
  const v = applyPatches(vertical, distributePatches(vertical, ['a', 'b', 'c'], 'v'));
  assert.equal(v[1].y - (v[0].y + v[0].height), v[2].y - (v[1].y + v[1].height));
});

test('distribute does nothing when the elements are too wide to leave even gaps', () => {
  const list = [el('t', 64, 20, 832, 60), el('b', 64, 100, 832, 300), el('s', 570, 285, 220, 130), el('c', 210, 200, 140, 140)];
  assert.deepEqual(distributePatches(list, ['t', 'b', 's', 'c'], 'h'), {});
  // and whatever it does, nothing ends up outside the span it started with
  const three = [el('a', 50, 0, 100, 40), el('b', 200, 0, 300, 40), el('c', 600, 0, 100, 40)];
  const next = applyPatches(three, distributePatches(three, ['a', 'b', 'c'], 'h'));
  next.forEach((item) => assert.ok(item.x >= 50 && item.x + item.width <= 700, item.id));
});

test('locked elements are never moved by alignment', () => {
  const list = [el('a', 100, 100, 100, 50), el('b', 300, 200, 60, 80, { locked: true }), el('c', 500, 60, 120, 40)];
  const patches = alignPatches(list, ['a', 'b', 'c'], 'left');
  assert.equal(patches.b, undefined);
});

test('grouped elements are picked and toggled as one', () => {
  let list = sample();
  list = groupElements(list, ['a', 'b']);
  const gid = list.find((i) => i.id === 'a').groupId;
  assert.ok(gid && list.find((i) => i.id === 'b').groupId === gid);
  assert.equal(list.find((i) => i.id === 'c').groupId, undefined);
  assert.deepEqual(expandToGroups(list, ['a']).sort(), ['a', 'b']);
  assert.deepEqual(toggleInSelection(list, ['c'], 'a').sort(), ['a', 'b', 'c']);
  assert.deepEqual(toggleInSelection(list, ['a', 'b', 'c'], 'b').sort(), ['c'], 'toggling a member removes the whole group');
  assert.equal(hasGroup(list, ['a']), true);
  const loose = ungroupElements(list, ['a']);
  assert.equal(hasGroup(loose, ['a', 'b']), false);
  assert.equal(groupElements(sample(), ['a']).find((i) => i.id === 'a').groupId, undefined, 'one element is not a group');
});

test('marquee picks what it touches, skipping locked elements, and keeps groups whole', () => {
  const list = groupElements([...sample(), el('d', 700, 400, 50, 50, { locked: true })], ['b', 'c']);
  assert.deepEqual(marqueeSelect(list, { x0: 90, y0: 90, x1: 220, y1: 170 }), ['a']);
  assert.deepEqual(marqueeSelect(list, { x0: 320, y0: 210, x1: 340, y1: 230 }).sort(), ['b', 'c'], 'touching one member selects the group');
  assert.deepEqual(marqueeSelect(list, { x1: 0, y1: 0, x0: 960, y0: 540 }).sort(), ['a', 'b', 'c'], 'corners in any order; locked d skipped');
});

test('cloning keeps groups together but gives them new ids', () => {
  const list = groupElements(sample(), ['a', 'b']);
  const copies = cloneSelection(list, ['a', 'b', 'c']);
  assert.equal(copies.length, 3);
  assert.equal(new Set([...list, ...copies].map((i) => i.id)).size, 6);
  const [ca, cb, cc] = copies;
  assert.ok(ca.groupId && ca.groupId === cb.groupId);
  assert.notEqual(ca.groupId, list.find((i) => i.id === 'a').groupId);
  assert.equal(cc.groupId, undefined);
  assert.equal(ca.x, 120);
  const edge = cloneSelection([el('e', 900, 500, 60, 40)], ['e'])[0];
  assert.ok(edge.x + edge.width <= 960 && edge.y + edge.height <= 540, 'stays on the slide');
});

test('layer order keeps the picked elements in their relative order', () => {
  const list = [el('1', 0, 0, 1, 1), el('2', 0, 0, 1, 1), el('3', 0, 0, 1, 1), el('4', 0, 0, 1, 1)];
  assert.deepEqual(reorderLayers(list, ['2', '3'], 'front').map((i) => i.id), ['1', '4', '2', '3']);
  assert.deepEqual(reorderLayers(list, ['3', '4'], 'back').map((i) => i.id), ['3', '4', '1', '2']);
});

test('a group move never leaves the slide', () => {
  const starts = { a: { x: 100, y: 100 }, b: { x: 300, y: 200 } };
  const bounds = { x: 100, y: 100, width: 260, height: 180 };
  const moved = moveWithinSlide(starts, bounds, -500, 900);
  assert.equal(moved.dx, -100);
  assert.equal(moved.dy, 260);
  assert.deepEqual(moved.patches.a, { x: 0, y: 360 });
  assert.deepEqual(moved.patches.b, { x: 200, y: 460 });
});

test('snapping pulls a box to the slide centre and to other elements, and reports the guide', () => {
  const near = snapBox({ x: 478, y: 10, width: 4, height: 4 }, []);
  assert.equal(near.guideX, 480);
  assert.equal(near.fixX, 0, 'its centre is already on the guide');
  const off = snapBox({ x: 455, y: 100, width: 50, height: 20 }, []);
  assert.equal(off.guideX, 480);
  assert.equal(off.fixX, 0);
  const toOther = snapBox({ x: 203, y: 100, width: 50, height: 20 }, [el('o', 100, 300, 100, 30)]);
  assert.equal(toOther.guideX, 200);
  assert.equal(toOther.fixX, -3);
  assert.equal(snapBox({ x: 300, y: 300, width: 10, height: 10 }, []).guideX, null, 'far from everything: no snap');
});
