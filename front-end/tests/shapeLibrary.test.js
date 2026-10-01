import test from 'node:test';
import assert from 'node:assert/strict';
import {
  ICON_NAMES, SHAPE_CATALOG, createIconElement, createShapeElement, isUserGraphic, isValidColor, resolveShape, shapeInfo,
} from '../src/utils/shapeLibrary.js';
import { applyCustomTemplateResult, restoreBuiltInTemplate } from '../src/utils/templateSwitching.js';
import { reflowSlideTemplate } from '../src/utils/slideElements.js';
import { toSlidePageUpdate } from '../src/utils/slideMapping.js';

test('every catalogue shape has valid geometry', () => {
  SHAPE_CATALOG.forEach((shape) => {
    assert.ok(shape.id && shape.label, shape.id);
    // A preset PowerPoint shape, or null when the export has to draw it (custom outline or picture).
    assert.ok(shape.pptx === null || typeof shape.pptx === 'string', `${shape.id} export mapping`);
    assert.ok(shape.size[0] > 0 && shape.size[1] > 0, shape.id);
    if (shape.kind === 'polygon') {
      assert.ok(shape.points.length >= 3, `${shape.id} has too few points`);
      shape.points.forEach(([x, y]) => assert.ok(x >= 0 && x <= 100 && y >= 0 && y <= 100, `${shape.id} point out of box`));
    }
  });
  assert.equal(new Set(SHAPE_CATALOG.map((shape) => shape.id)).size, SHAPE_CATALOG.length, 'ids are unique');
});

test('new shapes and icons are centred, inside the slide and use the given colour', () => {
  SHAPE_CATALOG.forEach((shape) => {
    const el = createShapeElement(shape.id, { accent: '#ff5500' });
    assert.equal(el.type, 'shape');
    assert.ok(el.x >= 0 && el.y >= 0 && el.x + el.width <= 960 && el.y + el.height <= 540, shape.id);
    assert.ok([el.fill, el.borderColor].includes('#ff5500'), `${shape.id} uses the accent`);
  });
  const icon = createIconElement('Rocket', { accent: '#123456' });
  assert.equal(icon.type, 'icon');
  assert.equal(icon.color, '#123456');
  assert.equal(createIconElement('NotAnIcon').icon, 'Star', 'unknown icon names fall back');
  assert.equal(new Set(ICON_NAMES).size, ICON_NAMES.length, 'icon names are unique');
});

test('shapes made before the catalogue existed still resolve as rectangles', () => {
  const legacy = { type: 'shape', fill: '#eeeeee', borderColor: '#999999', radius: 8 };
  const resolved = resolveShape(legacy);
  assert.equal(resolved.info.id, 'rect');
  assert.equal(resolved.radius, 8);
  assert.equal(resolved.borderWidth, 1);
  assert.equal(shapeInfo('does-not-exist').id, 'rect');
});

test('colour validation accepts only #rrggbb', () => {
  assert.ok(isValidColor('#a1B2c3'));
  ['red', '#fff', 'rgb(1,2,3)', '', null, 'url(x)'].forEach((value) => assert.equal(isValidColor(value), false, String(value)));
});

const baseSlide = () => ({ id: 's1', type: 'content', title: 'Tiêu đề', bullets: ['Ý một', 'Ý hai'], elements: [], richText: {} });
const plainMatch = { layoutId: 'x', backgroundColor: '#ffffff', titleStyle: { color: '#111111' }, bodyStyle: { color: '#222222' }, elements: [] };

test('a shape the user placed survives layout changes and template switches, a template ornament does not', () => {
  let slide = reflowSlideTemplate(baseSlide(), 'soft-blue');
  const star = createShapeElement('star', { accent: '#ff0000' });
  const icon = createIconElement('Heart');
  const ornament = { ...createShapeElement('ellipse'), ornament: true, id: 'orn-1' };
  slide = { ...slide, elements: [ornament, ...slide.elements, star, icon] };

  const reflowed = reflowSlideTemplate({ ...slide, richText: { _layoutVariant: 'cards' } }, 'soft-blue');
  [star.id, icon.id, ornament.id].forEach((id) => assert.ok(reflowed.elements.some((el) => el.id === id), `${id} kept by a re-layout`));
  const untouched = reflowed.elements.find((el) => el.id === star.id);
  assert.equal(untouched.x, star.x);
  assert.equal(untouched.y, star.y);

  const custom = applyCustomTemplateResult(slide, plainMatch, 'soft-blue');
  assert.ok(custom.elements.some((el) => el.id === star.id), 'star survives an uploaded template');
  assert.ok(custom.elements.some((el) => el.id === icon.id), 'icon survives an uploaded template');
  assert.ok(!custom.elements.some((el) => el.id === ornament.id), 'ornament belongs to the old template');

  const builtIn = restoreBuiltInTemplate(custom, 'nature-green');
  assert.ok(builtIn.elements.some((el) => el.id === star.id), 'star survives going back to a built-in template');
});

test('user graphics are saved with the slide', () => {
  const star = createShapeElement('star');
  const saved = toSlidePageUpdate({ ...reflowSlideTemplate(baseSlide(), 'soft-blue'), elements: [...reflowSlideTemplate(baseSlide(), 'soft-blue').elements, star] });
  assert.ok(saved.elements.some((el) => el.id === star.id && el.shape === 'star'));
  assert.equal(isUserGraphic(star), true);
  assert.equal(isUserGraphic({ ...star, ornament: true }), false);
});
