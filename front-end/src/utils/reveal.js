// Reveal-by-bullet for presenting: each click/arrow-key first steps through a content
// slide's bullet points one at a time (like a PowerPoint "Appear" build), and only moves
// to the next slide once every bullet on the current one has been shown. Legacy slides
// with no `elements` array (rendered through the fallback template layout) are left alone
// — there is nothing here to reveal incrementally, so they always count as a single stage.

function listItemCount(html) {
  if (!html || typeof document === 'undefined') return 0;
  const holder = document.createElement('div');
  holder.innerHTML = html;
  return holder.querySelectorAll('li').length;
}

/** How many bullets a slide has to build through (0 when it has none, or isn't element-based). */
export function countRevealStages(slide) {
  const elements = Array.isArray(slide?.elements) && slide.elements.length ? slide.elements : [];
  return elements
    .filter((element) => element.type === 'text' && (element.role === 'body' || element.role === 'custom'))
    .reduce((sum, element) => sum + listItemCount(element.content), 0);
}

/**
 * Hides the `<li>`s past `stage` inside an already-rendered slide (kept in the layout, just
 * transparent, so nothing reflows as more appear). Bullets are numbered in DOM
 * order, which is the same left-to-right, top-to-bottom order `countRevealStages` counts
 * them in. This works on the live DOM rather than the element's HTML string because the
 * bullets are rendered through Tiptap (see TiptapEditor.jsx): its schema only keeps
 * attributes it knows about, so a `style="visibility:hidden"` baked into the source HTML
 * gets silently dropped the moment ProseMirror parses it.
 */
export function paintReveal(root, stage) {
  if (!root) return;
  const items = root.querySelectorAll('.canvas-text li');
  items.forEach((item, index) => {
    // Faded rather than toggled, so a bullet arriving reads as an entrance effect.
    item.style.transition = 'opacity .35s ease, transform .35s ease';
    item.style.opacity = index < stage ? '1' : '0';
    item.style.transform = index < stage ? 'none' : 'translateY(8px)';
  });
}
