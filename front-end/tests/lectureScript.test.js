import test from 'node:test';
import assert from 'node:assert/strict';
import {
  byFileName, countWords, estimatedMinutes, firstShownNumber, renumberRows, safeFileName, sheetNameFromFile, suggestedSetName,
} from '../src/utils/lectureScript.js';

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

test('several files are ordered the way their numbers read, and each names its sheet', () => {
  const names = ['C2 Video 11.pptx', 'C2 Video 4.pptx', 'C2 Video 10.pptx', 'C2 Video 5.pptx'];
  assert.deepEqual([...names].sort(byFileName), ['C2 Video 4.pptx', 'C2 Video 5.pptx', 'C2 Video 10.pptx', 'C2 Video 11.pptx']);
  assert.equal(sheetNameFromFile('C2 Video 4.pptx'), 'C2 Video 4');
  assert.equal(sheetNameFromFile('Bài [1]: mở đầu/kết.PDF'), 'Bài 1 mở đầu kết');
  assert.ok(sheetNameFromFile(`${'a'.repeat(60)}.pptx`).length <= 31);
});

test('a set is named after what its files share', () => {
  assert.equal(suggestedSetName([{ sheet: 'C2 Video 4' }, { sheet: 'C2 Video 5' }, { sheet: 'C2 Video 10' }]), 'C2 Video');
  assert.equal(suggestedSetName([{ sheet: 'Bài A', title: 'Mở đầu' }, { sheet: 'Chương 3' }]), 'Mở đầu');
  assert.equal(suggestedSetName([{ sheet: 'C1 Video 1', title: 'Tổng quan ATTT' }]), 'Tổng quan ATTT');
  assert.equal(suggestedSetName([]), 'Bộ kịch bản');
});
