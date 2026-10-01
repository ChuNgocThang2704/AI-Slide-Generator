import test from 'node:test';
import assert from 'node:assert/strict';
import { hasOwnOrnaments, themeOrnaments } from '../src/utils/themeOrnaments.js';
import { parseThemeCode, serializeThemeSpec, withThemeSpec, makeThemeCode } from '../src/utils/generatedTheme.js';
import { shapeInfo } from '../src/utils/shapeLibrary.js';
import { artToElements, isBackdrop, withoutTemplateArt } from '../src/utils/templateArt.js';
import { applyCustomTemplateResult } from '../src/utils/templateSwitching.js';
import { reflowSlideTemplate } from '../src/utils/slideElements.js';

const codeWith = (decor) => withThemeSpec(makeThemeCode('Cà phê'), { decor });

test('every decoration kind of a generated theme becomes real shapes, and "none" becomes nothing', () => {
  const counts = {};
  for (let decor = 0; decor <= 6; decor += 1) {
    const ornaments = themeOrnaments(codeWith(decor));
    counts[decor] = ornaments.length;
    ornaments.forEach((el) => {
      assert.equal(el.type, 'shape');
      assert.equal(el.ornament, true);
      assert.ok(shapeInfo(el.shape).id === el.shape, `${el.shape} exists in the catalogue`);
      assert.ok(el.width > 0 && el.height > 0);
      assert.ok(el.opacity > 0 && el.opacity <= 1, `opacity ${el.opacity}`);
    });
  }
  assert.equal(counts[6], 0, 'none draws nothing');
  for (let decor = 0; decor <= 5; decor += 1) assert.ok(counts[decor] >= 2, `kind ${decor} has pieces`);
  assert.deepEqual(themeOrnaments('soft-blue'), [], 'built-in themes have no shape ornaments');
});

test('the "none" decoration survives the code round trip and is never picked by chance', () => {
  const none = codeWith(6);
  assert.equal(parseThemeCode(none).decor, 6);
  assert.equal(serializeThemeSpec(parseThemeCode(none)), none);
  for (let i = 0; i < 300; i += 1) assert.notEqual(parseThemeCode(makeThemeCode(`chủ đề ${i}`, i)).decor, 6);
});

test('ornament pieces get fresh ids on every call so slides never share an element id', () => {
  const a = themeOrnaments(codeWith(0));
  const b = themeOrnaments(codeWith(0));
  assert.equal(new Set([...a, ...b].map((el) => el.id)).size, a.length + b.length);
});

test('a slide keeps its ornaments through a re-layout, and hasOwnOrnaments sees them', () => {
  const base = reflowSlideTemplate({ id: 's', type: 'content', title: 'Tiêu đề', bullets: ['Ý một', 'Ý hai'], elements: [], richText: {} }, 'soft-blue');
  const ornaments = themeOrnaments(codeWith(2));
  const slide = { ...base, richText: { _noOrnaments: true }, elements: [...ornaments, ...base.elements] };
  assert.equal(hasOwnOrnaments(slide), true);
  const again = reflowSlideTemplate({ ...slide, richText: { ...slide.richText, _layoutVariant: 'columns' } }, 'soft-blue');
  ornaments.forEach((o) => assert.ok(again.elements.some((el) => el.id === o.id), `${o.id} kept`));
  assert.equal(again.elements.slice(0, ornaments.length).every((el) => el.ornament), true, 'ornaments stay behind the content');
  assert.equal(hasOwnOrnaments(base), false);
});

test('uploaded-template art becomes editable elements; the backdrop stays a layer', () => {
  const decor = [
    { id: 'bg', type: 'shape', role: 'background', x: 0, y: 0, width: 960, height: 540, fill: '#123456' },
    { id: 'pic', type: 'image', role: 'decoration', x: 500, y: 40, width: 300, height: 400, src: '/template/public/assets/t/a.png', style: { flipX: true, cropL: 0.1 } },
    { id: 'orb', type: 'shape', role: 'decoration', x: 600, y: -4, width: 500, height: 500, fill: '#5284ff', style: { borderRadius: '50%' } },
    { id: 'full', type: 'image', role: 'decoration', x: 0, y: 0, width: 960, height: 540, src: '/template/public/assets/t/bg.png' },
  ];
  assert.deepEqual(decor.filter(isBackdrop).map((d) => d.id), ['bg', 'full']);
  const elements = artToElements(decor);
  assert.equal(elements.length, 2);
  elements.forEach((el) => { assert.equal(el.type, 'art'); assert.equal(el.ornament, true); assert.ok(el.id.startsWith('orn-')); });
  const pic = elements.find((el) => el.artType === 'image');
  assert.equal(pic.src, '/template/public/assets/t/a.png');
  assert.equal(pic.style.flipX, true);
  assert.equal(pic.style.cropL, 0.1, 'crop and flip are kept when the art is adopted');
});

test('applying another uploaded template drops the previous ornaments and the hidden flag', () => {
  const ornaments = artToElements([{ id: 'x', type: 'image', role: 'decoration', x: 500, y: 40, width: 300, height: 400, src: '/a.png' }]);
  const slide = { id: 's', type: 'content', title: 'Tiêu đề', bullets: ['Ý một'], elements: ornaments, richText: { _noOrnaments: true, _decor: [] } };
  const result = applyCustomTemplateResult(slide, { layoutId: 'l', backgroundColor: '#ffffff', titleStyle: { color: '#111' }, bodyStyle: { color: '#222' }, elements: [] }, 'soft-blue');
  assert.equal(result.elements.some((el) => el.ornament), false);
  assert.equal(result.richText._noOrnaments, undefined);
  assert.deepEqual(withoutTemplateArt({ _noOrnaments: true, keep: 1 }), { keep: 1 });
});
