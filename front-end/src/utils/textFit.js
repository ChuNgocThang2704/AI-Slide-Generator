export function plainText(value) {
  return String(value || '')
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<\/(?:p|li)>/gi, '\n')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;|&#160;/gi, ' ')
    .replace(/&amp;/gi, '&')
    .replace(/[ \t]+/g, ' ')
    .replace(/\n{2,}/g, '\n')
    .trim();
}

export function fitTextToBox(
  value,
  {
    width,
    height,
    min = 10,
    max = 24,
    lineHeight = 1.5,
    itemCount = 1,
    padding = 12,
  },
) {
  const text = plainText(value);
  if (!text) return max;

  const paragraphs = text.split(/\n+/).filter(Boolean);
  const usableWidth = Math.max(40, Number(width) - padding * 2);
  const usableHeight = Math.max(30, Number(height) - padding * 2);

  for (let size = max; size >= min; size -= 0.5) {
    const charsPerLine = Math.max(10, Math.floor(usableWidth / (size * 0.54)));
    const wrappedLines = paragraphs.reduce(
      (sum, paragraph) => sum + Math.max(1, Math.ceil(paragraph.length / charsPerLine)),
      0,
    );
    const listSpacing = Math.max(0, itemCount - 1) * size * 0.3;
    if (wrappedLines * size * lineHeight + listSpacing <= usableHeight) {
      return Math.round(size * 2) / 2;
    }
  }
  return min;
}
