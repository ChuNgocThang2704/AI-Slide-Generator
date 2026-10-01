// Turns a parsed real .pptx (templateService.importSlides' response) into slide objects the
// editor already knows how to render and save — each returned layout is a faithful, ordered
// copy of one real slide, so this is a straight conversion, not a template match.
//
// Known limits of this v1: native PowerPoint tables/charts aren't extracted (that slide's
// text and pictures still come through, the table/chart itself doesn't); grouped shapes and
// SmartArt aren't unpacked; a picture used purely as a small logo near the slide edge may be
// skipped (the same "is this actually decoration" heuristic the template-upload feature uses).
import { buildTemplateArt } from './templateArt.js';
import { newElementId } from './selection.js';

const ROLE_MAP = { title: 'title', body: 'body' };

function mapTextElement(element) {
  return {
    id: newElementId(),
    type: 'text',
    role: ROLE_MAP[element.role] || 'custom',
    x: Number(element.x) || 0,
    y: Number(element.y) || 0,
    width: Number(element.width) || 0,
    height: Number(element.height) || 0,
    rotation: Number(element.rotation) || 0,
    content: element.content || '',
    style: element.style ? { ...element.style } : {},
  };
}

export function slidesFromImportedManifest(manifest) {
  const layouts = Array.isArray(manifest?.layouts) ? manifest.layouts : [];
  return layouts.map((layout) => {
    // buildTemplateArt already knows how to pick the page colour, tell decoration from
    // background, and reserve a safe area for text around any big picture — the exact same
    // pass a matched template's sample layout goes through, so it's reused as-is here.
    const art = buildTemplateArt({ backgroundColor: layout.backgroundColor, elements: layout.decor || [] });
    // `_imported` marks a slide that is a faithful copy of a real one: the editor must keep its
    // boxes where the file put them, not re-match the slide against the deck's template on load
    // (that re-flows every slide and saves the result over the copy).
    const richText = { _imported: true };
    if (art.decor.length) {
      richText._decor = art.decor;
      if (art.pageColor) richText._tplBg = art.pageColor;
      if (art.safe) richText._safe = art.safe;
    }
    const elements = (layout.elements || [])
      .filter((element) => element.type === 'text' && String(element.content || '').trim())
      .map(mapTextElement);
    return {
      id: null,
      type: layout.type || 'content',
      notes: '',
      richText,
      elements,
    };
  });
}
