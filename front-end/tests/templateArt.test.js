import test from 'node:test';
import assert from 'node:assert/strict';
import { mapTemplateFont } from '../src/utils/templateFonts.js';
import { buildTemplateArt, computeSafeArea, isDarkColor, resolveArtLayout, withoutTemplateArt } from '../src/utils/templateArt.js';
import { applyCustomTemplateResult, restoreBuiltInTemplate } from '../src/utils/templateSwitching.js';
import { layoutTemplateElements } from '../src/utils/templateLayouts.js';
import { reflowSlideTemplate } from '../src/utils/slideElements.js';

const LOADED = /Inter|Nunito|Plus Jakarta Sans|Space Grotesk|Playfair Display|Merriweather|Exo 2|Saira|Baloo 2|Be Vietnam Pro/;

test('template fonts always map to a font this app loads', () => {
  ['Garet', 'Garet Bold', 'Montserrat', 'Georgia', 'Times New Roman', 'Comic Sans MS', 'Wingdings', '', undefined, 'Some Random Font']
    .forEach((name) => assert.match(mapTemplateFont(name), LOADED, `font ${name}`));
  assert.match(mapTemplateFont('Garet Bold'), /Plus Jakarta Sans/);
  assert.match(mapTemplateFont('Playfair Display Italic'), /Playfair Display/);
  assert.match(mapTemplateFont('Georgia'), /Merriweather/);
});

const navyMatch = () => ({
  layoutId: 'sample-layout-1',
  backgroundColor: '#294491',
  primaryColor: '#5284FF',
  titleStyle: { fontFamily: 'Garet', fontWeight: 700, color: '#EBF5FE', textAlign: 'right', fontSize: 12 },
  bodyStyle: { fontFamily: 'Garet', fontWeight: 400, color: '#EBF5FE' },
  elements: [
    { id: 'bg', type: 'shape', role: 'background', x: 0, y: 0, width: 960, height: 540, fill: 'linear-gradient(90deg, #5284FF 0%, #000422 100%)', locked: true },
    { id: 'orb', type: 'shape', role: 'decoration', x: 576, y: -4, width: 544, height: 544, fill: 'rgba(159,205,255,0.2)', locked: true },
    { id: 'art', type: 'image', role: 'decoration', x: 513, y: 47, width: 335, height: 467, src: '/template/public/assets/t1/image1.png', locked: true },
    { id: 'icon', type: 'image', role: 'decoration', x: 93, y: 123, width: 27, height: 27, src: '/template/public/assets/t1/image3.png', locked: true },
  ],
});

test('background and art are lifted out of the match result', () => {
  const art = buildTemplateArt(navyMatch());
  assert.equal(art.decor.length, 4);
  assert.equal(art.pageColor, '#294491');
  assert.ok(isDarkColor(art.pageColor));
});

test('a plain white template carries no art', () => {
  const art = buildTemplateArt({ backgroundColor: '#FFFFFF', elements: [{ id: 'bg', type: 'shape', role: 'background', fill: '#FFFFFF', width: 960, height: 540 }] });
  assert.equal(art.decor.length, 0);
  assert.equal(art.safe, null);
});

test('large pictures reserve their side; icons, backdrops and cramped slides do not', () => {
  const { decor } = buildTemplateArt(navyMatch());
  const safe = computeSafeArea(decor);
  assert.deepEqual(safe, { pad: 64, safeRight: 489 });
  // Art on both sides that leaves too little room: the smaller side's picture is dropped.
  const small = { id: 'left-art', type: 'image', role: 'decoration', x: 0, y: 40, width: 300, height: 300, src: '/x.png' };
  const both = [...decor, small];
  const resolved = resolveArtLayout(both);
  assert.ok(!resolved.decor.some((el) => el.id === 'left-art'), 'the smaller picture is dropped');
  assert.ok(resolved.decor.some((el) => el.id === 'art'), 'the larger picture stays');
  assert.deepEqual(resolved.safe, { pad: 64, safeRight: 489 });
  // Room for a column between two pictures: both stay and the text sits between them.
  const roomy = resolveArtLayout([
    { id: 'l', type: 'image', role: 'decoration', x: 0, y: 60, width: 150, height: 400, src: '/l.png' },
    { id: 'r', type: 'image', role: 'decoration', x: 810, y: 60, width: 150, height: 400, src: '/r.png' },
  ]);
  assert.equal(roomy.decor.length, 2);
  assert.deepEqual(roomy.safe, { pad: 174, safeRight: 786 });
  assert.equal(computeSafeArea([{ type: 'image', role: 'decoration', x: 0, y: 0, width: 960, height: 540 }]), null);
});

test('applying an uploaded template keeps the art, stores it beside the elements and reserves space', () => {
  const slide = { id: 's1', type: 'content', title: 'Tiêu đề', bullets: ['Ý một', 'Ý hai'], elements: [], richText: {} };
  const result = applyCustomTemplateResult(slide, navyMatch(), 'soft-blue');
  assert.equal(result.richText._decor.length, 4);
  assert.deepEqual(result.richText._safe, { pad: 64, safeRight: 489 });
  assert.equal(result.richText._tplBg, '#294491');
  // Art never becomes a content element the layout could move or edit.
  assert.ok(!result.elements.some((el) => el.role === 'decoration' || el.role === 'background'));
  // Imported alignment/size are ignored, colour and (mapped) font are kept.
  const title = result.elements.find((el) => el.role === 'title');
  assert.equal(title.style.color, '#EBF5FE');
  assert.match(title.style.fontFamily, /Plus Jakarta Sans/);
  assert.notEqual(title.style.textAlign, 'right');
  // The text stays left of the illustration.
  const body = result.elements.find((el) => el.role === 'body');
  assert.ok(body.x + body.width <= 489 + 1, `body ends at ${body.x + body.width}`);
});

test('switching back to a built-in template removes the previous art', () => {
  const slide = { id: 's1', type: 'content', title: 'Tiêu đề', bullets: ['Ý một'], elements: [], richText: {} };
  const custom = applyCustomTemplateResult(slide, navyMatch(), 'soft-blue');
  const restored = restoreBuiltInTemplate(custom, 'soft-blue');
  assert.equal(restored.richText._decor, undefined);
  assert.equal(restored.richText._safe, undefined);
  assert.equal(restored.richText._tplBg, undefined);
});

test('applying a template without art clears art left by a previous one', () => {
  const slide = { id: 's1', type: 'content', title: 'Tiêu đề', bullets: ['Ý một'], elements: [], richText: {} };
  const first = applyCustomTemplateResult(slide, navyMatch(), 'soft-blue');
  const plain = { ...navyMatch(), backgroundColor: '#FFFFFF', elements: [{ id: 'bg', type: 'shape', role: 'background', fill: '#FFFFFF', width: 960, height: 540 }] };
  const second = applyCustomTemplateResult(first, plain, 'soft-blue');
  assert.equal(second.richText._decor, undefined);
  assert.equal(second.richText._safe, undefined);
});

test('the layout engine honours a reserved area for every text layout', () => {
  const base = { id: 's2', type: 'content', title: 'Tiêu đề khá dài của một slide nội dung', bullets: ['Ý thứ nhất khá dài để chiếm nhiều dòng trong khung', 'Ý thứ hai', 'Ý thứ ba'], richText: { _safe: { pad: 64, safeRight: 489 } } };
  ['classic', 'columns', 'cards', 'rail', 'centered', 'banner'].forEach((variant) => {
    const slide = { ...base, richText: { ...base.richText, _layoutVariant: variant } };
    const els = reflowSlideTemplate(slide, 'soft-blue').elements.filter((el) => el.type === 'text');
    els.forEach((el) => assert.ok(el.x + el.width <= 489 + 1, `${variant}/${el.role} ends at ${el.x + el.width}`));
  });
  assert.equal(typeof layoutTemplateElements, 'function');
  assert.deepEqual(withoutTemplateArt({ _decor: [1], _safe: {}, _tplBg: 'x', keep: 1 }), { keep: 1 });
});
