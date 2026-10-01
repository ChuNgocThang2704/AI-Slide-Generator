import test from 'node:test';
import assert from 'node:assert/strict';
import { explainGenerationError } from '../src/utils/generationErrors.js';

test('plan length limit names the numbers and offers an upgrade', () => {
  const info = explainGenerationError('Do dai noi dung vuot qua gioi han cua goi FREE (15476 > 10000 ky tu).');
  assert.equal(info.action, 'upgrade');
  assert.match(info.detail, /15\.476/);
  assert.match(info.detail, /10\.000/);
  assert.match(info.detail, /Miễn phí/);
});

test('daily limit, translated or raw, is a clear limit message', () => {
  for (const raw of ['Daily slide generation limit reached', 'Bạn đã dùng hết lượt tạo slide hôm nay']) {
    const info = explainGenerationError(raw);
    assert.equal(info.action, 'upgrade', raw);
    assert.match(info.title, /hết lượt/);
  }
});

test('provider capacity errors say it is temporary and not the user’s content', () => {
  const info = explainGenerationError('[antigravity/x] 429: You have exhausted your capacity on this model.');
  assert.equal(info.action, 'retry');
  assert.match(info.detail, /không phải lỗi của nội dung/);
});

test('connection problems are told apart from content problems', () => {
  assert.equal(explainGenerationError('Lỗi kết nối AI Engine: Connection refused').action, 'retry');
});

test('unreadable file gets a file-specific hint', () => {
  assert.match(explainGenerationError('Cannot extract text: file is encrypted').title, /Không đọc được/);
});

test('an unknown short reason is shown, a long or technical one is not leaked', () => {
  assert.match(explainGenerationError('Chủ đề không phù hợp').detail, /Chủ đề không phù hợp/);
  const technical = explainGenerationError('java.lang.NullPointerException at com.backend.X.y(X.java:1)');
  assert.doesNotMatch(technical.detail, /NullPointer/);
  assert.equal(explainGenerationError('').title, 'Không thể tạo slide');
});

test('expired session points to logging in again', () => {
  assert.match(explainGenerationError('', { status: 401 }).title, /đăng nhập/);
});
