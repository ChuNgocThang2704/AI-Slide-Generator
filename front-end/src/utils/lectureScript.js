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

/** "C2 Video 4.pptx" -> "C2 Video 4": the default sheet name of a file (Excel allows 31 characters). */
export const sheetNameFromFile = (fileName) => (
  String(fileName || '').replace(/\.(pptx|pdf)$/i, '').replace(/[[\]:*?/\\]+/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 31) || 'Kịch bản'
);

/** File order as a person reads it: "Video 4" before "Video 11". */
export const byFileName = (a, b) => String(a).localeCompare(String(b), 'vi', { numeric: true, sensitivity: 'base' });

/**
 * A name for a set of scripts from what its files share: "C2 Video 4", "C2 Video 5" -> "C2 Video";
 * one file, or files with nothing in common, fall back to the first title.
 */
export function suggestedSetName(items) {
  const names = (items || []).map((item) => String(item.sheet || '').trim()).filter(Boolean);
  if (names.length > 1) {
    let prefix = names[0];
    for (const name of names.slice(1)) {
      while (prefix && !name.toLowerCase().startsWith(prefix.toLowerCase())) prefix = prefix.slice(0, -1);
    }
    prefix = prefix.replace(/[\s\d._-]+$/, '').trim();
    if (prefix.length >= 2) return prefix;
  }
  return String(items?.[0]?.title || names[0] || 'Bộ kịch bản').trim().slice(0, 200);
}

/** Rows whose Vietnamese has no English yet, or changed since it was translated: [{i, script}]. */
export function rowsToTranslate(rows) {
  const out = [];
  (rows || []).forEach((row, i) => {
    const script = String(row.script || '').trim();
    if (script && (!String(row.en || '').trim() || row.enFor !== script)) out.push({ i, script });
  });
  return out;
}

/** How many rows carry English, and how many of those are out of date against their Vietnamese. */
export function englishStatus(rows) {
  let translated = 0;
  let stale = 0;
  let missing = 0;
  for (const row of rows || []) {
    const script = String(row.script || '').trim();
    if (!script) continue;
    if (!String(row.en || '').trim()) missing += 1;
    else {
      translated += 1;
      if (row.enFor !== script) stale += 1;
    }
  }
  return { translated, stale, missing };
}
