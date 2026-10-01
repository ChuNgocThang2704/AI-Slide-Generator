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
