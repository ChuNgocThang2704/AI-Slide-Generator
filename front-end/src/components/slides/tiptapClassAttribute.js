import { Extension } from '@tiptap/core';

/**
 * Slide content (from slideElements.js and the AI deck) carries semantic
 * classes on block nodes — slide-content-flow, slide-section-label,
 * slide-code-block, slide-quote-text — that the app's CSS depends on for
 * bullet markers, code blocks and the quote layout. Tiptap's schema drops
 * any HTML attribute a node doesn't explicitly declare, so without this,
 * every one of those classes would silently vanish the moment a box round-
 * trips through the editor once.
 */
export const PreserveClassAttribute = Extension.create({
  name: 'preserveClassAttribute',
  addGlobalAttributes() {
    return [
      {
        types: ['paragraph', 'heading', 'bulletList', 'orderedList', 'listItem', 'codeBlock'],
        attributes: {
          class: {
            default: null,
            parseHTML: (element) => element.getAttribute('class'),
            renderHTML: (attributes) => (attributes.class ? { class: attributes.class } : {}),
          },
        },
      },
    ];
  },
});
