import test from 'node:test';
import assert from 'node:assert/strict';
import {
  byFileName, countWords, estimatedMinutes, firstShownNumber, applyTranslations, normalizeRow, renumberRows, rowsToTranslate, rowsWithScript, safeFileName, translationStatus, sheetNameFromFile, suggestedSetName,
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

test('a translation is needed for rows that have none or whose script changed after translating', () => {
  const rows = [
    { script: 'Một.', alt: 'One.', altFor: 'Một.' },
    { script: 'Hai (đã sửa).', alt: 'Two.', altFor: 'Hai.' },
    { script: 'Ba.', alt: '' },
    { script: '   ', alt: '' },
  ];
  assert.deepEqual(rowsToTranslate(rows), [{ i: 1, script: 'Hai (đã sửa).' }, { i: 2, script: 'Ba.' }]);
  assert.deepEqual(rowsWithScript(rows).map((row) => row.i), [0, 1, 2]);
  assert.deepEqual(translationStatus(rows), { translated: 2, stale: 1, missing: 1 });
  assert.deepEqual(rowsToTranslate([]), []);
});

test('rows saved when the subtitles could only be English are read as they are now', () => {
  assert.deepEqual(normalizeRow({ script: 'Một.', en: 'One.', enFor: 'Một.' }), { script: 'Một.', alt: 'One.', altFor: 'Một.' });
  const current = { script: 'Một.', alt: 'One.', altFor: 'Một.' };
  assert.equal(normalizeRow(current), current);
});

test('a translation lands only on the row whose script is still what was sent', () => {
  const plan = [{ i: 0, script: 'Một.' }, { i: 1, script: 'Hai.' }, { i: 2, script: 'Ba.' }];
  const items = [{ i: 0, text: 'One.' }, { i: 1, text: 'Two.' }, { i: 2, text: 'Three.' }];
  const rows = [
    { script: 'Một.', alt: '' },
    { script: 'Hai, đã gõ thêm.', alt: '' },                       // edited while the call was running
    { script: 'Chèn mới', alt: '' },                                // a row inserted meanwhile pushed "Ba." down
    { script: 'Ba.', alt: '' },
  ];
  const out = applyTranslations(rows, plan, items);
  assert.equal(out.applied, 2);
  assert.deepEqual(out.rows.map((row) => row.alt), ['One.', '', '', 'Three.']);
  assert.equal(out.rows[3].altFor, 'Ba.');
});

test('a row the user brought up to date by hand is not overwritten, unless everything is redone', () => {
  const rows = [{ script: 'Một.', alt: 'One, polished.', altFor: 'Một.' }];
  const plan = [{ i: 0, script: 'Một.' }];
  assert.equal(applyTranslations(rows, plan, [{ i: 0, text: 'One.' }]).rows[0].alt, 'One, polished.');
  assert.equal(applyTranslations(rows, plan, [{ i: 0, text: 'One.' }], { force: true }).rows[0].alt, 'One.');
});
