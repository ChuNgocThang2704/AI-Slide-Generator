import test from 'node:test';
import assert from 'node:assert/strict';
import { createElementsFromSlide, reflowSlideTemplate } from '../src/utils/slideElements.js';
import { formatSlidePage, toSlidePageUpdate } from '../src/utils/slideMapping.js';
import { ADAPTIVE_TEMPLATES, normalizeBoundaryElements, normalizeTableElements } from '../src/utils/templateLayouts.js';
import { prepareTemplateContent, applyCustomTemplateResult, restoreBuiltInTemplate } from '../src/utils/templateSwitching.js';

const themes = [...ADAPTIVE_TEMPLATES];
const table = { headers: ['Year', 'Total'], rows: Array.from({ length: 12 }, (_, i) => [2020 + i, i * 10]) };
const chart = { type: 'bar', labels: ['A', 'B', 'C'], series: [{ name: 'Series 1', values: [4, 6, 2] }, { name: 'Series 2', values: [1, 3, 5] }] };
const slide = { id: 'test-slide', type: 'content', title: 'Learning objectives', bullets: ['Understand the concept', 'Apply the tools', 'Review the results'] };

for (const theme of themes) {
  test(`${theme}: bounds stay on canvas for cover, text, image, table and chart`, () => {
    for (const extra of [{}, { type: 'title' }, { imageUrl: 'data:image/png;base64,test' }, { table }, { chart }]) {
      const elements = createElementsFromSlide({ ...slide, ...extra }, theme);
      for (const el of elements) {
        assert.ok(el.x >= 0 && el.y >= 0 && el.width > 0 && el.height > 0);
        assert.ok(el.x + el.width <= 960 && el.y + el.height <= 540);
      }
      for (let i = 0; i < elements.length; i++) {
        for (let j = i + 1; j < elements.length; j++) {
          const a = elements[i], b = elements[j];
          assert.ok(a.x + a.width <= b.x || b.x + b.width <= a.x || a.y + a.height <= b.y || b.y + b.height <= a.y,
            `overlap: ${a.role}, ${b.role}`);
        }
      }
    }
  });
  test(`${theme}: dense tables are wide and data is not mutated`, () => {
    const input = { ...slide, table };
    const before = JSON.stringify(input);
    const output = reflowSlideTemplate(input, theme);
    const el = output.elements.find((item) => item.type === 'table');
    assert.ok(el.width >= 800);
    assert.equal(el.data, table);
    assert.equal(el.data.rows.length, 12);
    assert.equal(JSON.stringify(input), before);
  });
  test(`${theme}: chart type, all series and image assets survive switches`, () => {
    const input = { ...slide, chart, imageUrl: 'asset.jpg' };
    const output = reflowSlideTemplate(input, theme);
    assert.equal(output.elements.find((el) => el.type === 'chart').data, chart);
    assert.equal(output.elements.find((el) => el.type === 'image').src, 'asset.jpg');
  });
}

test('themes have different text, image and chart coordinates', () => {
  for (const extra of [{}, { imageUrl: 'asset.jpg' }, { chart }, { type: 'title' }]) {
    const signatures = themes.map((theme) => JSON.stringify(createElementsFromSlide({ ...slide, ...extra }, theme)
      .map(({ x, y, width, height }) => [x, y, width, height])));
    assert.equal(new Set(signatures).size, themes.length);
  }
});

test('title and closing slides omit lecture labels and use readable closing body text', () => {
  for (const theme of themes) {
    const title = reflowSlideTemplate({ ...slide, type: 'title' }, theme);
    const closing = reflowSlideTemplate({ ...slide, type: 'thankyou' }, theme);
    assert.equal(title.elements.some((el) => /^(BÀI GIẢNG|LECTURE)$/.test(String(el.content))), false);
    assert.equal(closing.elements.some((el) => /^(KẾT THÚC BÀI GIẢNG|END OF LECTURE)$/.test(String(el.content))), false);
    const titleElement = closing.elements.find((el) => el.role === 'title');
    const bodyElement = closing.elements.find((el) => el.role === 'body');
    assert.equal(bodyElement.style.fontSize, 24);
    assert.ok(bodyElement.height >= 300);
    assert.ok(titleElement.x + titleElement.width <= bodyElement.x
      || bodyElement.x + bodyElement.width <= titleElement.x
      || titleElement.y + titleElement.height <= bodyElement.y
      || bodyElement.y + bodyElement.height <= titleElement.y);
  }
});

test('reflow removes saved lecture labels but preserves other custom text', () => {
  const output = reflowSlideTemplate({ ...slide, type: 'thankyou', elements: [
    { id: 'label', type: 'text', role: 'custom', content: '<p>Kết thúc bài giảng</p>', x: 10, y: 10, width: 200, height: 30 },
    { id: 'title', type: 'text', role: 'title', content: slide.title, x: 100, y: 100, width: 500, height: 80 },
    { id: 'body', type: 'text', role: 'body', content: '<ul><li>Summary</li></ul>', x: 100, y: 250, width: 500, height: 100 },
    { id: 'custom', type: 'text', role: 'custom', content: 'Q&A', x: 20, y: 470, width: 100, height: 30 },
  ] }, 'tech-purple');
  assert.equal(output.elements.some((el) => el.id === 'label'), false);
  assert.equal(output.elements.some((el) => el.id === 'custom'), true);
  assert.equal(output.elements.find((el) => el.id === 'body').style.fontSize, 24);
});

test('saved closing slides are normalized on reload and serialization', () => {
  const saved = [
    { id: 'label', type: 'text', role: 'custom', content: 'KẾT THÚC BÀI GIẢNG', templateLayout: 'cover' },
    { id: 'body', type: 'text', role: 'body', content: '<p>Summary</p>', templateLayout: 'cover', style: { fontSize: 20 } },
  ];
  const normalized = normalizeBoundaryElements(saved, 'thankyou', 'tech-purple');
  assert.deepEqual(normalized.map((el) => el.id), ['body']);
  assert.equal(normalized[0].style.fontSize, 24);
  assert.equal(normalized[0].height, 362);
  assert.equal(normalizeBoundaryElements(normalized, 'thankyou', 'tech-purple'), normalized);
});

test('existing edits are not reflowed on ordinary render', () => {
  const elements = [{ id: 'manual', type: 'text', role: 'body', x: 23, y: 57, width: 345, height: 200, content: 'Edited content' }];
  assert.equal(createElementsFromSlide({ ...slide, elements }, 'soft-blue'), elements);
  assert.equal(reflowSlideTemplate({ ...slide, elements }, 'clean-white').elements[0].content, 'Edited content');
});

test('split body content survives API serialization and reload', () => {
  const elements = [
    { id: 'title', type: 'text', role: 'title', content: slide.title, x: 60, y: 40 },
    ...slide.bullets.map((text, index) => ({ id: `body-${index}`, type: 'text', role: 'body',
      layoutGroup: 'body', content: `<ul><li>${text}</li></ul>`, x: index * 200, y: 150 })),
  ];
  const update = toSlidePageUpdate({ ...slide, elements });
  assert.deepEqual(update.bullets, slide.bullets);
  assert.deepEqual(formatSlidePage({ ...update, pageIndex: 1 }).elements, elements);
  const merged = reflowSlideTemplate({ ...slide, elements }, 'clean-white');
  assert.deepEqual(toSlidePageUpdate(merged).bullets, slide.bullets);
});

test('extra user text, image crop and notes survive layout changes', () => {
  const original = reflowSlideTemplate({ ...slide, imageUrl: 'asset.jpg', notes: 'Speaker notes' }, 'soft-blue');
  original.elements.push({ id: 'annotation', type: 'text', role: 'custom', content: 'My annotation', x: 10, y: 10, width: 120, height: 30 });
  original.elements.find((el) => el.type === 'image').objectPositionX = 30;
  const output = reflowSlideTemplate(original, 'blue-planet');
  assert.equal(output.notes, original.notes);
  assert.equal(output.elements.find((el) => el.id === 'annotation').content, 'My annotation');
  assert.equal(output.elements.find((el) => el.type === 'image').objectPositionX, 30);
});

test('table layouts contain the title and table, not duplicate bullets', () => {
  for (const theme of [...themes, 'tech-purple']) {
    const output = reflowSlideTemplate({ ...slide, table }, theme);
    assert.deepEqual(output.elements.map((el) => el.type), ['text', 'table']);
    assert.equal(output.elements[0].content, slide.title);
    assert.equal(output.elements[1].data, table);
    assert.deepEqual(toSlidePageUpdate(output).bullets, slide.bullets);
  }
});

test('saved old table layouts migrate without changing table data or custom annotations', () => {
  const old = { ...slide, table, layout: 'text_table', pageIndex: 1, elements: [
    { id: 'title', type: 'text', role: 'title', content: slide.title, x: 64, y: 40, width: 832, height: 86 },
    { id: 'body', type: 'text', role: 'body', content: `<ul>${slide.bullets.map((item) => `<li>${item}</li>`).join('')}</ul>`, templateLayout: 'data-wide' },
    { id: 'table', type: 'table', data: table, x: 56, y: 212, width: 848, height: 288, templateLayout: 'data-wide' },
    { id: 'annotation', type: 'text', role: 'custom', content: 'Source: report' },
  ] };
  const formatted = formatSlidePage(old);
  const saved = toSlidePageUpdate(old);
  for (const elements of [formatted.elements, saved.elements]) {
    assert.equal(elements.some((el) => el.id === 'body'), false);
    assert.equal(elements.find((el) => el.id === 'table').data, table);
    assert.equal(elements.find((el) => el.id === 'table').y, 132);
    assert.equal(elements.find((el) => el.id === 'annotation').content, 'Source: report');
    assert.equal(normalizeTableElements(elements), elements);
  }
  assert.equal(old.elements.length, 4);
});

test('chart descriptions and unmarked custom table text are not migrated away', () => {
  const chartSlide = reflowSlideTemplate({ ...slide, chart }, 'soft-blue');
  assert.ok(chartSlide.elements.some((el) => el.role === 'body'));
  assert.equal(normalizeTableElements(chartSlide.elements), chartSlide.elements);
  const custom = [{ type: 'table', data: table }, { type: 'text', role: 'body', content: 'Custom text' }];
  assert.equal(normalizeTableElements(custom), custom);
});

test('table title is used if slide title is missing', () => {
  const elements = createElementsFromSlide({ type: 'table', table: { ...table, title: 'Table heading' } }, 'soft-blue');
  assert.equal(elements.find((el) => el.role === 'title').content, 'Table heading');
});

test('full-width headings do not leave an empty description column on small tables', () => {
  for (const theme of ['playful-yellow', 'gradient-border', 'nature-green']) {
    const output = reflowSlideTemplate({ ...slide, table: { headers: ['Year', 'Total'], rows: [[2025, 100]] } }, theme);
    assert.ok(output.elements.find((el) => el.type === 'table').width >= 800);
    assert.equal(output.elements.filter((el) => el.type === 'text').length, 1);
  }
});

const customMatch = (content) => ({
  layoutId: 'sample-layout', layoutType: 'title', elements: [
    { id: 'template-background-test', type: 'shape', role: 'background', fill: '#FFFFFF', locked: true, x: 0, y: 0, width: 960, height: 540 },
    { id: 'template-title-test', type: 'text', role: 'title', content: content.title, x: 4, y: 14, width: 400, height: 50, style: { fontFamily: 'Imported Font', fontSize: 64 } },
    ...content.bullets.map((bullet, index) => ({ id: `template-body-${index}`, type: 'text', role: 'body',
      content: `<p>${bullet}</p>`, x: 40 + index * 200, y: 120, width: 180, height: 70, style: { fontFamily: 'Imported Font', fontSize: 42, color: '#FFFFFF' } })),
    { id: 'template-empty-image', type: 'image', role: 'image', x: 30, y: 300, width: 200, height: 200 },
  ],
});

test('custom matching reads current canvas edits, not stale semantic fields', () => {
  const input = reflowSlideTemplate(slide, 'clean-white');
  input.elements.find((el) => el.role === 'title').content = '<p>Updated &amp; current</p>';
  input.elements.find((el) => el.role === 'body').content = '<p>First edited paragraph</p><p>Second edited paragraph</p>';
  const current = prepareTemplateContent(input, 'clean-white');
  assert.equal(current.title, 'Updated & current');
  assert.deepEqual(current.bullets, ['First edited paragraph', 'Second edited paragraph']);
  assert.equal(slide.title, 'Learning objectives');
});

test('custom fallback layout must not change semantic slide type', () => {
  const current = prepareTemplateContent(slide, 'soft-blue');
  const custom = applyCustomTemplateResult(current, customMatch(current));
  assert.equal(custom.type, 'content');
  assert.equal(toSlidePageUpdate(custom).layout, 'text_only');
  assert.deepEqual(toSlidePageUpdate(custom).bullets, slide.bullets);
});

test('returning from custom rebuilds each built-in without imported background, fonts or empty image frames', () => {
  for (const theme of themes) {
    const current = prepareTemplateContent(slide, theme);
    const custom = applyCustomTemplateResult(current, customMatch(current));
    const restored = restoreBuiltInTemplate(custom, theme);
    const expected = reflowSlideTemplate({ ...slide, elements: [] }, theme);
    const geometry = (value) => value.elements.map(({ type, role, x, y, width, height, style }) => ({ type, role, x, y, width, height, style }));
    assert.deepEqual(geometry(restored), geometry(expected));
    assert.deepEqual(toSlidePageUpdate(restored).bullets, slide.bullets);
    assert.equal(restored.elements.some((el) => String(el.id).startsWith('template-')), false);
  }
});

test('custom edits, notes and repeated round trips preserve content', () => {
  let current = prepareTemplateContent({ ...slide, notes: 'Keep these notes' }, 'soft-blue');
  for (let i = 0; i < 3; i++) {
    current = applyCustomTemplateResult(current, customMatch(current));
    current.elements.find((el) => el.role === 'title').content = 'Edited inside custom';
    current.elements.find((el) => el.role === 'body').content = '<ul><li>Newest bullet</li><li>Apply the tools</li><li>Review the results</li></ul>';
    current = restoreBuiltInTemplate(current, 'soft-blue');
    assert.equal(current.title, 'Edited inside custom');
    assert.deepEqual(current.bullets, ['Newest bullet', ...slide.bullets.slice(1)]);
    assert.equal(current.notes, 'Keep these notes');
  }
});

test('custom templates import styles without importing PPTX geometry or losing chart content', () => {
  const chartSlide = {
    ...slide,
    chart: {
      type: 'bar',
      categories: ['2019', '2020', '2021'],
      series: [{ name: 'Temperature', values: [1, 1.1, 1.2] }],
    },
  };
  const current = prepareTemplateContent(chartSlide, 'soft-blue');
  const match = customMatch(current);
  match.primaryColor = '#D946EF';
  match.titleStyle = { fontFamily: 'Imported Heading', fontSize: 40, color: '#123456', textAlign: 'center' };
  match.bodyStyle = { fontFamily: 'Imported Body', fontSize: 22, color: '#654321' };
  match.elements = match.elements.map((element) => ({ ...element, x: 0, y: 0, width: 960, height: 540 }));

  const custom = applyCustomTemplateResult(current, match, 'soft-blue');
  const expected = reflowSlideTemplate({ ...current, elements: [] }, 'soft-blue');
  const geometry = (elements) => elements
    .filter((element) => ['title', 'body', 'visual'].includes(element.role))
    .map(({ type, role, x, y, width, height }) => ({ type, role, x, y, width, height }));

  assert.deepEqual(geometry(custom.elements), geometry(expected.elements));
  assert.deepEqual(toSlidePageUpdate(custom).bullets, slide.bullets);
  assert.deepEqual(custom.chart, chartSlide.chart);
  assert.equal(custom.elements.find((element) => element.role === 'title').style.fontFamily, 'Imported Heading');
  assert.equal(custom.elements.find((element) => element.role === 'body').style.fontFamily, 'Imported Body');
  assert.equal(custom.elements.some((element) => element.templateStyleOnly), true);
  assert.equal(custom.elements.some((element) => String(element.id).startsWith('template-')), false);
});

test('custom table does not reintroduce bullets above the table', () => {
  const content = prepareTemplateContent({ ...slide, table }, 'soft-blue');
  const match = customMatch(content);
  match.elements.push({ id: 'template-table', type: 'table', role: 'table', data: table, x: 64, y: 130, width: 832, height: 340 });
  const custom = applyCustomTemplateResult(content, match);
  assert.equal(custom.elements.some((el) => el.role === 'body'), false);
  assert.equal(restoreBuiltInTemplate(custom, 'clean-white').table, table);
});

test('manually added annotations and extra images survive template round trips', () => {
  const input = reflowSlideTemplate({ ...slide, imageUrl: 'primary.jpg' }, 'soft-blue');
  input.elements.push({ id: 'my-note', type: 'text', role: 'custom', content: 'My annotation', x: 20, y: 450, width: 200, height: 40 });
  input.elements.push({ id: 'my-image', type: 'image', src: 'extra.jpg', x: 20, y: 300, width: 100, height: 100 });
  const current = prepareTemplateContent(input, 'soft-blue');
  const match = customMatch(current);
  match.elements.push({ id: 'template-primary', type: 'image', role: 'image', src: current.imageUrl, x: 300, y: 300, width: 100, height: 100 });
  const restored = restoreBuiltInTemplate(applyCustomTemplateResult(current, match), 'soft-blue');
  assert.equal(restored.elements.filter((el) => el.id === 'my-note').length, 1);
  assert.equal(restored.elements.filter((el) => el.src === 'extra.jpg').length, 1);
  assert.equal(restored.elements.filter((el) => el.src === 'primary.jpg').length, 1);
});

test('deleted title, body and image are not restored from stale fields when matching', () => {
  const input = { ...slide, imageUrl: 'deleted.jpg', elements: [{ id: 'note', type: 'text', role: 'custom', content: 'Only this remains' }] };
  const current = prepareTemplateContent(input, 'soft-blue');
  assert.equal(current.title, '');
  assert.equal(current.imageUrl, '');
  assert.deepEqual(current.bullets, []);
});
