import test from 'node:test';
import assert from 'node:assert/strict';
import { recommendTemplateForDeck, TOPIC_THEME_IDS } from '../src/utils/dynamicTemplate.js';
import { ADAPTIVE_TEMPLATES } from '../src/utils/templateLayouts.js';

const pick = (name, slides = []) => recommendTemplateForDeck({ name }, slides);

test('every recommended theme is a real built-in theme', () => {
  TOPIC_THEME_IDS.forEach((id) => assert.ok(ADAPTIVE_TEMPLATES.has(id), `${id} is not a built-in theme`));
});

test('topics map to a fitting profile', () => {
  assert.equal(pick('Trí tuệ nhân tạo trong giáo dục').id === 'technology' || pick('Trí tuệ nhân tạo trong giáo dục').id === 'education', true);
  assert.equal(pick('Chiến lược marketing và doanh thu 2025').id, 'business');
  assert.equal(pick('Bảo vệ môi trường và biến đổi khí hậu').id, 'nature');
  assert.equal(pick('Lịch sử và di sản văn hóa Việt Nam').id, 'humanities');
  assert.equal(pick('Đầu tư chứng khoán cho người mới').id, 'finance');
});

test('short keywords do not match inside other words', () => {
  // "ai" must not fire inside "hai", "mai" or "bài".
  assert.equal(pick('Hai bài học về mai sau').id, 'general');
});

test('the deck body contributes but the title weighs more', () => {
  const slides = [{ title: 'Doanh thu quý', bullets: ['khách hàng', 'thị trường'] }];
  assert.equal(pick('Tổng hợp', slides).id, 'business');
});

test('the same project always gets the same theme', () => {
  assert.equal(pick('Báo cáo marketing').themeId, pick('Báo cáo marketing').themeId);
});

test('unknown topics still get a valid theme', () => {
  const result = pick('Xyz qwerty');
  assert.equal(result.id, 'general');
  assert.ok(ADAPTIVE_TEMPLATES.has(result.themeId));
});

test('across many projects every built-in theme can be reached', () => {
  const seen = new Set();
  const subjects = ['công nghệ', 'môi trường', 'sức khỏe', 'kinh doanh', 'tài chính', 'giáo dục', 'lịch sử', 'du lịch', 'zzz'];
  subjects.forEach((subject) => {
    for (let i = 0; i < 40; i += 1) seen.add(pick(`${subject} số ${i}`).themeId);
  });
  assert.equal(seen.size, ADAPTIVE_TEMPLATES.size, `unreachable themes: ${[...ADAPTIVE_TEMPLATES].filter((id) => !seen.has(id)).join(', ')}`);
});
