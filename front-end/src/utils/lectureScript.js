// Small pure helpers of the lecture-script page (kept apart so they can be tested).

export const WORDS_PER_MINUTE = 140;

export const countWords = (text) => String(text || '').trim().split(/\s+/).filter(Boolean).length;

export const totalWords = (rows) => (rows || []).reduce((sum, row) => sum + countWords(row.script), 0);

export const estimatedMinutes = (rows) => {
  const words = totalWords(rows);
  return words ? Math.max(1, Math.round(words / WORDS_PER_MINUTE)) : 0;
};

const isAutoSlideRow = (row) => (
  Number.isInteger(row.slide) && row.kind !== 'intro' && /^Slide \d+$/.test(String(row.scene || '').trim())
);

/**
 * Slides of one video are often numbered within a longer chapter deck ("Slide 27" is the second
 * slide of this file). Rows that still carry their automatic label follow the new first number;
 * a label the user typed is left alone.
 */
export function renumberRows(rows, firstNumber) {
  const numbered = (rows || []).filter(isAutoSlideRow);
  if (!numbered.length || !Number.isInteger(firstNumber) || firstNumber < 1) return rows;
  const lowest = Math.min(...numbered.map((row) => row.slide));
  return rows.map((row) => {
    if (!numbered.includes(row)) return row;
    const shown = firstNumber + (row.slide - lowest);
    const note = /^Hình \d+$/.test(String(row.note || '').trim()) ? `Hình ${shown}` : row.note;
    return { ...row, scene: `Slide ${shown}`, note };
  });
}

/** The number the first slide row currently shows, or null when the labels are no longer automatic. */
export function firstShownNumber(rows) {
  const first = (rows || []).find(isAutoSlideRow);
  return first ? Number(String(first.scene).trim().slice(6)) : null;
}

export const safeFileName = (title) => (
  `Kịch bản dựng_${String(title || 'bài giảng').replace(/[\\/:*?"<>|]+/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 80)}.xlsx`
);
