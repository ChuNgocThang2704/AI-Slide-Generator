import test from 'node:test';
import assert from 'node:assert/strict';
import { backendLayoutToFrontend } from '../src/utils/slideMapping.js';

test('a closing slide with a real summary is shown as a content slide, so no point is dropped', () => {
  const page = { pageIndex: 5, layout: 'thankyou', pedagogicalRole: 'summary', title: 'Tổng kết', bullets: ['a', 'b', 'c', 'd'] };
  assert.equal(backendLayoutToFrontend(page), 'content');
});

test('a short closing keeps the closing composition', () => {
  assert.equal(backendLayoutToFrontend({ pageIndex: 5, layout: 'thankyou', bullets: ['Cảm ơn quý vị', 'email@example.com'] }), 'thankyou');
  assert.equal(backendLayoutToFrontend({ pageIndex: 5, layout: 'thankyou', bullets: '["Cảm ơn"]' }), 'thankyou');
});
