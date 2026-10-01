import test from 'node:test';
import assert from 'node:assert/strict';
import { slidesFromImportedManifest } from '../src/utils/pptxImport.js';

const manifest = {
  layouts: [{
    type: 'content',
    backgroundColor: '#FFFFFF',
    decor: [],
    elements: [
      { type: 'text', role: 'title', x: 223, y: 5, width: 496, height: 79, content: '<p>Tiêu đề thật</p>', style: { fontSize: 32 } },
      { type: 'text', role: 'body', x: 40, y: 110, width: 322, height: 25, content: '<p>Nội dung thật</p>', style: {} },
      { type: 'text', role: 'body', x: 669, y: 504, width: 129, height: 17, content: '<p>http://www.ptit.edu.vn</p>', style: {} },
      { type: 'text', role: 'body', x: 10, y: 10, width: 10, height: 10, content: '   ', style: {} },
    ],
  }],
};

test('an opened slide keeps every real text box where the file put it', () => {
  const [slide] = slidesFromImportedManifest(manifest);
  assert.deepEqual(
    slide.elements.map((el) => [el.role, el.x, el.y, el.width, el.height]),
    [['title', 223, 5, 496, 79], ['body', 40, 110, 322, 25], ['body', 669, 504, 129, 17]],
  );
  assert.match(slide.elements[0].content, /Tiêu đề thật/);
});

test('an opened slide is marked as a faithful copy so the editor will not re-match it', () => {
  const [slide] = slidesFromImportedManifest(manifest);
  assert.equal(slide.richText._imported, true);
  // A slide with no decoration at all is still marked: the marker is not tied to having art.
  assert.deepEqual(Object.keys(slide.richText), ['_imported']);
});

test('an empty manifest gives no slides', () => {
  assert.deepEqual(slidesFromImportedManifest({ layouts: [] }), []);
  assert.deepEqual(slidesFromImportedManifest(null), []);
});

test('a slide number becomes a page-number box and keeps the size the file gave it', () => {
  const withNumber = {
    layouts: [{
      type: 'content',
      backgroundColor: '#FFFFFF',
      decor: [],
      elements: [
        { type: 'text', role: 'title', x: 100, y: 20, width: 400, height: 40, content: '<p>Tiêu đề</p>', style: { fontSize: 32 } },
        { type: 'text', role: 'pageNumber', x: 864, y: 504, width: 48, height: 22, content: '<p>3</p>', style: { fontSize: 12 } },
      ],
    }],
  };
  const [slide] = slidesFromImportedManifest(withNumber);
  const number = slide.elements.find((el) => el.role === 'pageNumber');
  assert.ok(number, 'the slide number is kept as a page-number box');
  assert.equal(number.content, '<p>3</p>');
  assert.deepEqual([number.x, number.y], [864, 504]);
  assert.equal(number.style.fontSize, 12);
  assert.equal(number.style.fontSizeLocked, true);
});

test('a table in the file becomes an editor table with its own cells and column widths', () => {
  const withTable = {
    layouts: [{
      type: 'table',
      backgroundColor: '#FFFFFF',
      decor: [],
      elements: [
        { type: 'text', role: 'title', x: 100, y: 20, width: 400, height: 40, content: '<p>Bảng</p>', style: {} },
        {
          type: 'table', role: 'table', x: 60, y: 120, width: 800, height: 300, content: '',
          data: { headers: ['Mục', 'Giá trị'], rows: [['A', '1'], ['B', '2']], columnWidths: [3000000, 6000000] },
        },
      ],
    }],
  };
  const [slide] = slidesFromImportedManifest(withTable);
  const table = slide.elements.find((el) => el.type === 'table');
  assert.ok(table, 'the table is kept as an element');
  assert.deepEqual([table.x, table.y, table.width, table.height], [60, 120, 800, 300]);
  assert.deepEqual(table.data.rows, [['A', '1'], ['B', '2']]);
  assert.deepEqual(table.data.columnWidths, [3000000, 6000000]);
  // It is also the slide's table, so the outline and the AI see its cells.
  assert.equal(slide.table.headers[0], 'Mục');
  assert.equal(slide.primaryVisual, 'table');
});
