import test from 'node:test';
import assert from 'node:assert/strict';
import { parseTwoColumns } from '../src/utils/slideMapping.js';

test('column headings are read with the long dash and with the hyphen the AI service leaves', () => {
  const dash = parseTwoColumns(['Nên — a', 'Nên — b', 'Tránh — c']);
  assert.deepEqual(dash, [{ heading: 'Nên', points: ['a', 'b'] }, { heading: 'Tránh', points: ['c'] }]);
  const hyphen = parseTwoColumns(['Kênh bán - Omnichannel: tích hợp', 'Kênh bán - Loyalty: tăng 28%', 'Vận hành - Chuỗi cung ứng: tối ưu']);
  assert.deepEqual(hyphen.map((c) => [c.heading, c.points.length]), [['Kênh bán', 2], ['Vận hành', 1]]);
});

test('plain bullets become two unnamed columns, no invented headings', () => {
  const plain = parseTwoColumns(['Y tế - chẩn đoán', 'Giáo dục - cá nhân hóa', 'Tài chính - gian lận', 'Một dòng thường']);
  assert.deepEqual(plain.map((c) => c.heading), ['', '']);
  assert.equal(plain[0].points.length + plain[1].points.length, 4);
});
