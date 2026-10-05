import test from 'node:test';
import assert from 'node:assert/strict';
import { countWords, estimatedMinutes, firstShownNumber, renumberRows, safeFileName } from '../src/utils/lectureScript.js';

const rows = () => [
  { kind: 'intro', scene: 'Lời mở đầu', slide: 1, script: 'Chào các em.', note: 'Hình ảnh GV' },
  { kind: 'slide', scene: 'Slide 2', slide: 2, script: 'a b c', note: '' },
  { kind: 'slide', scene: 'Slide 3', slide: 3, script: 'a b', note: 'Hình 3' },
  { kind: 'outro', scene: 'Lời kết', slide: null, script: 'Hẹn gặp lại.', note: 'Hình ảnh GV' },
];

test('slide rows follow a new first number, their figure notes too; the opening and closing do not', () => {
  const out = renumberRows(rows(), 27);
  assert.deepEqual(out.map((row) => row.scene), ['Lời mở đầu', 'Slide 27', 'Slide 28', 'Lời kết']);
  assert.equal(out[2].note, 'Hình 28');
  assert.equal(firstShownNumber(out), 27);
  assert.deepEqual(renumberRows(out, 2).map((row) => row.scene), ['Lời mở đầu', 'Slide 2', 'Slide 3', 'Lời kết']);
});

test('a label the user typed is left alone', () => {
  const edited = rows();
  edited[1].scene = 'Phần 1';
  const out = renumberRows(edited, 10);
  assert.equal(out[1].scene, 'Phần 1');
  assert.equal(out[2].scene, 'Slide 10');
});

test('duration follows the word count at the speaking pace of the reference scripts', () => {
  assert.equal(countWords('  Chào   các em. \n\n Hôm nay '), 5);
  assert.equal(estimatedMinutes([{ script: Array(1120).fill('từ').join(' ') }]), 8);
  assert.equal(estimatedMinutes([{ script: '' }]), 0);
});

test('the file name drops characters Windows refuses', () => {
  assert.equal(safeFileName('Video 4: Mối đe dọa / Lỗ hổng?'), 'Kịch bản dựng_Video 4 Mối đe dọa Lỗ hổng.xlsx');
});
