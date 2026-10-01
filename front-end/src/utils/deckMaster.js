// Deck-wide presenting settings, stored on the project as a JSON string (Project.deckMaster
// on the backend), the same way a slide's own richText/elements are stored.
//
// Anything that *appears on a slide* (logo, footer, page number) is a normal element on that
// slide instead — added once and copied across with "sao chép sang mọi slide" — so it can be
// moved, resized and deleted like everything else, the way PowerPoint works.

export const DEFAULT_DECK_MASTER = {
  // Presenting, like PowerPoint: nothing animates unless the user asks for it.
  transition: 'none', // 'none' | 'fade' | 'push' | 'zoom' — how one slide gives way to the next
  revealBullets: false, // step through a slide's bullet points one click at a time
};

// Cover/closing slides carry their own bold design, so deck-wide extras skip them by default.
export const MASTER_COVER_TYPES = new Set(['title', 'thankyou']);

export function parseDeckMaster(raw) {
  if (!raw) return { ...DEFAULT_DECK_MASTER };
  if (typeof raw === 'object') return { ...DEFAULT_DECK_MASTER, ...raw };
  try {
    return { ...DEFAULT_DECK_MASTER, ...JSON.parse(raw) };
  } catch {
    return { ...DEFAULT_DECK_MASTER };
  }
}

export function serializeDeckMaster(master) {
  return JSON.stringify(master || DEFAULT_DECK_MASTER);
}
