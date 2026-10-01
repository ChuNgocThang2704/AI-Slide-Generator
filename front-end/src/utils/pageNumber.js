// Slide numbers are ordinary text boxes carrying a marker, not a separate overlay: they can
// be moved, resized, restyled and deleted like any other box. Only their text is looked
// after here, so it keeps matching the slide's position after reordering, adding or deleting.

import { newElementId } from './selection';

export const PAGE_NUMBER_ROLE = 'pageNumber';

export const isPageNumber = (element) => element?.type === 'text' && element?.role === PAGE_NUMBER_ROLE;

export function createPageNumberElement(index) {
  return {
    id: newElementId(),
    type: 'text',
    role: PAGE_NUMBER_ROLE,
    x: 872,
    y: 496,
    width: 56,
    // The height the text really measures at this size: a taller box would be re-measured as soon
    // as it appears, and that correction lands in the undo history as a change of its own.
    height: 20,
    rotation: 0,
    content: `<p>${index + 1}</p>`,
    // Locked so the box keeps this size instead of being auto-fitted like body text; colour is
    // left unset on purpose so it follows the theme (and changes if the user picks one).
    style: { fontSize: 14, fontSizeLocked: true, textAlign: 'right', lineHeight: 1.2 },
  };
}

// Swaps only the digits, so any formatting the user applied to the number (colour, bold…)
// inside the box survives a renumbering.
function withNumber(content, number) {
  const text = String(content || '').replace(/<[^>]*>/g, '').trim();
  if (text === String(number)) return content;
  if (/>\s*\d+\s*</.test(content || '')) return content.replace(/>\s*\d+\s*</, `>${number}<`);
  return `<p>${number}</p>`;
}

/** Rewrites every slide-number box to its slide's current position in the deck. */
export function renumberPages(slides) {
  let changed = false;
  const next = slides.map((slide, index) => {
    if (!Array.isArray(slide.elements) || !slide.elements.some(isPageNumber)) return slide;
    let slideChanged = false;
    const elements = slide.elements.map((element) => {
      if (!isPageNumber(element)) return element;
      const content = withNumber(element.content, index + 1);
      if (content === element.content) return element;
      slideChanged = true;
      return { ...element, content };
    });
    if (!slideChanged) return slide;
    changed = true;
    return { ...slide, elements };
  });
  return changed ? next : slides;
}

export const hasPageNumbers = (slides) => slides.some(
  (slide) => Array.isArray(slide.elements) && slide.elements.some(isPageNumber),
);
