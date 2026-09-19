export const ADAPTIVE_TEMPLATES = new Set([
  'soft-blue', 'clean-white', 'blue-planet', 'royal-purple', 'modern-dark',
  'playful-yellow', 'gradient-border', 'nature-green', 'tech-purple',
]);

const BOUNDARY_LABELS = new Set(['BÀI GIẢNG', 'LECTURE', 'KẾT THÚC BÀI GIẢNG', 'END OF LECTURE']);
const plainText = (value) => String(value || '').replace(/<[^>]*>/g, '').trim().toUpperCase();

export function normalizeBoundaryElements(elements = [], type, theme) {
  if (!['title', 'thankyou'].includes(type)) return elements;
  const closingLayout = type === 'thankyou' ? CLOSING_LAYOUTS[theme] : null;
  let changed = false;
  const normalized = elements.flatMap((element) => {
    if (element.type === 'text' && element.role === 'custom' && BOUNDARY_LABELS.has(plainText(element.content))) {
      changed = true;
      return [];
    }
    if (closingLayout && element.type === 'text' && ['title', 'body'].includes(element.role)
      && element.templateLayout === 'cover') {
      const bounds = element.role === 'title' ? closingLayout.title : closingLayout.body;
      const fontSize = element.role === 'body' && [20, 22, 26].includes(Number(element.style?.fontSize))
        ? 24 : element.style?.fontSize;
      const next = { ...element, ...bounds, style: { ...element.style, fontSize } };
      if (['x', 'y', 'width', 'height'].some((key) => next[key] !== element[key])
        || fontSize !== element.style?.fontSize) changed = true;
      return [next];
    }
    if (type === 'thankyou' && element.type === 'text' && element.role === 'body'
      && element.templateLayout === 'cover' && [20, 22].includes(Number(element.style?.fontSize))) {
      changed = true;
      return [{ ...element, style: { ...element.style, fontSize: 24 } }];
    }
    return [element];
  });
  return changed ? normalized : elements;
}

export function normalizeTableElements(elements = []) {
  const hasTable = elements.some((el) => el.type === 'table');
  const isGeneratedBody = (el) => el.type === 'text' && el.role === 'body'
    && ['data-wide', 'data-editorial'].includes(el.templateLayout);
  if (!hasTable || !elements.some(isGeneratedBody)) return elements;
  // Migrate only the body boxes added by the old built-in data layouts.
  // Keep manual annotations, custom templates, and the table payload intact.
  return elements.filter((el) => !isGeneratedBody(el)).map((el) =>
    el.type === 'table' && el.templateLayout === 'data-wide'
      ? { ...el, y: 132, height: 368 } : el);
}

export function orderedBodyElements(elements = []) {
  const bodies = elements.filter((el) => el.type === 'text' && el.role === 'body');
  if (!bodies.length || !bodies.every((el) => el.layoutGroup === bodies[0].layoutGroup && el.layoutGroup)) return bodies;
  return [...bodies].sort((a, b) => (a.layoutOrder || 0) - (b.layoutOrder || 0));
}

const box = (x, y, width, height) => ({ x, y, width, height });
const textLength = (value) => String(value || '').replace(/<[^>]*>/g, '').length;

// Closing slides reserve enough room for four medium-length bullets at 24px.
// The variants keep each theme's characteristic composition without triggering auto-fit.
const CLOSING_LAYOUTS = {
  'soft-blue': { title: box(64, 36, 832, 102), body: box(64, 158, 832, 362), titleAlign: 'left' },
  'royal-purple': { title: box(100, 36, 760, 102), body: box(64, 158, 832, 362), titleAlign: 'center' },
  'clean-white': { title: box(64, 36, 832, 102), body: box(64, 158, 832, 362), titleAlign: 'left' },
  'modern-dark': { title: box(64, 36, 832, 102), body: box(64, 158, 832, 362), titleAlign: 'left' },
  'playful-yellow': { title: box(80, 36, 800, 102), body: box(64, 158, 832, 362), titleAlign: 'center' },
  'gradient-border': { title: box(64, 418, 832, 92), body: box(64, 34, 832, 362), titleAlign: 'left' },
  'blue-planet': { title: box(100, 36, 760, 102), body: box(64, 158, 832, 362), titleAlign: 'center' },
  'nature-green': { title: box(64, 36, 832, 102), body: box(64, 158, 832, 362), titleAlign: 'left' },
  'tech-purple': { title: box(96, 36, 800, 102), body: box(64, 158, 832, 362), titleAlign: 'left' },
};

const EXTRA_LAYOUTS = {
  'royal-purple': {
    columns: 2,
    text: { title: box(128, 52, 704, 104), body: box(96, 194, 768, 286), align: 'center' },
    cover: { title: box(120, 176, 720, 178), body: box(160, 386, 640, 100), eyebrow: box(120, 106, 720, 32), align: 'center' },
    image: { title: box(72, 62, 376, 124), body: box(72, 218, 376, 270), visual: box(496, 62, 392, 426) },
    data: { title: box(64, 66, 232, 180), body: box(64, 282, 232, 202), visual: box(336, 62, 560, 426) },
  },
  'modern-dark': {
    columns: 2,
    text: { title: box(56, 72, 256, 348), body: box(352, 80, 552, 404) },
    cover: { title: box(64, 156, 540, 242), body: box(656, 242, 248, 218), eyebrow: box(64, 86, 540, 32) },
    image: { title: box(56, 60, 460, 126), body: box(56, 218, 460, 270), visual: box(564, 60, 340, 428) },
    data: { title: box(672, 60, 232, 196), body: box(672, 294, 232, 192), visual: box(56, 60, 572, 428) },
  },
  'playful-yellow': {
    columns: 2,
    text: { title: box(80, 44, 800, 104), body: box(80, 184, 800, 304), align: 'center' },
    cover: { title: box(80, 106, 800, 180), body: box(160, 338, 640, 126), eyebrow: box(80, 52, 800, 30), align: 'center' },
    image: { title: box(64, 52, 832, 100), body: box(64, 198, 360, 284), visual: box(480, 188, 416, 294) },
    data: { title: box(72, 48, 816, 84), body: box(648, 188, 240, 296), visual: box(72, 168, 536, 316), align: 'center' },
  },
  'gradient-border': {
    columns: 2,
    text: { title: box(80, 394, 800, 102), body: box(80, 60, 800, 294) },
    cover: { title: box(80, 252, 800, 188), body: box(80, 104, 720, 104), eyebrow: box(80, 54, 720, 30) },
    image: { title: box(64, 378, 496, 112), body: box(608, 70, 288, 414), visual: box(64, 60, 496, 280) },
    data: { title: box(64, 410, 832, 90), body: box(652, 76, 244, 290), visual: box(64, 60, 548, 310) },
  },
  'nature-green': {
    columns: 1,
    text: { title: box(646, 90, 250, 348), body: box(64, 74, 526, 414) },
    cover: { title: box(80, 122, 454, 288), body: box(588, 228, 292, 224), eyebrow: box(80, 62, 454, 30) },
    image: { title: box(64, 44, 832, 96), body: box(462, 170, 434, 318), visual: box(64, 170, 348, 318) },
    data: { title: box(64, 48, 832, 94), body: box(64, 192, 252, 296), visual: box(364, 166, 532, 322) },
  },
  'tech-purple': {
    columns: 3,
    text: { title: box(64, 52, 832, 106), body: box(64, 202, 832, 286) },
    cover: { title: box(320, 126, 560, 240), body: box(320, 390, 560, 100), eyebrow: box(64, 132, 208, 76) },
    image: { title: box(536, 64, 360, 144), body: box(536, 240, 360, 248), visual: box(64, 64, 424, 424) },
    data: { title: box(64, 58, 220, 194), body: box(64, 296, 220, 192), visual: box(324, 58, 572, 430) },
  },
};

function listItems(content, generated) {
  if (typeof DOMParser === 'undefined') return null;
  const doc = new DOMParser().parseFromString(content, 'text/html');
  const lists = [...doc.body.children];
  if (!lists.length || (!generated && lists.length !== 1) || lists.some((el) => el.tagName !== 'UL')) return null;
  if ([...doc.body.childNodes].some((node) => node.nodeType === 3 && node.textContent.trim())) return null;
  const items = lists.flatMap((list) => [...list.children]);
  // Keep nested and ordered lists intact, including their numbering.
  if (items.some((child) => child.tagName !== 'LI' || child.querySelector('ul, ol'))) return null;
  return items.map((child) => child.outerHTML);
}

function mergeLayoutBodies(elements) {
  const generated = orderedBodyElements(elements).filter((el) => el.layoutGroup);
  if (generated.length < 2 || !generated.every((el) => el.layoutGroup === generated[0].layoutGroup)) return elements;
  const merged = { ...generated[0], content: generated.map((el) => el.content).join('') };
  return elements.flatMap((el) => el.id === merged.id ? [merged] : generated.includes(el) ? [] : [el]);
}

export function isDenseVisual(element) {
  const data = element?.data || {};
  if (element?.type === 'table') {
    return (data.headers?.length || 0) > 4 || (data.rows?.length || 0) > 6
      || JSON.stringify(data.rows || []).length > 650;
  }
  return (data.labels?.length || 0) > 6 || (data.series?.length || 0) > 2;
}

// All bounds share the editor's 960 x 540 coordinate system.
export function layoutTemplateElements(slide, source, theme, colors) {
  const content = source.some((el) => el.type === 'table')
    ? source.filter((el) => !(el.type === 'text' && el.role === 'body')) : source;
  const boundary = ['title', 'thankyou'].includes(slide.type);
  let elements = normalizeBoundaryElements(mergeLayoutBodies(content), slide.type, theme)
    .map((el) => ({ ...el, style: el.style ? { ...el.style } : undefined }));
  const title = elements.find((el) => el.type === 'text' && el.role === 'title');
  const bodies = elements.filter((el) => el.type === 'text' && el.role === 'body');
  const visuals = elements.filter((el) => el.type === 'table' || el.type === 'chart');
  const images = elements.filter((el) => el.type === 'image');
  const bodyLength = bodies.reduce((sum, el) => sum + textLength(el.content), 0);
  const place = (el, bounds, style = {}) => {
    if (el) Object.assign(el, bounds, { style: { ...el.style, ...style } });
  };
  elements.forEach((el) => {
    if (el.type !== 'text' || !['title', 'body'].includes(el.role)) return;
    el.style = { ...el.style, fontFamily: el.role === 'title' ? colors.title : colors.body,
      color: el.role === 'title' ? colors.text : colors.sub, textAlign: 'left', verticalAlign: 'top' };
  });
  const adaptive = ADAPTIVE_TEMPLATES.has(theme);
  const profile = EXTRA_LAYOUTS[theme];

  let titleBox = theme === 'blue-planet' ? box(96, 42, 768, 86) : box(64, 40, 832, 86);
  let contentBox = theme === 'blue-planet' ? box(96, 160, 768, 332) : box(64, 150, 832, 342);
  const titleStyle = { fontSize: textLength(title?.content) > 100 ? 28 : 34, lineHeight: 1.2 };
  let variant = 'wide';

  if (boundary && !visuals.length && !images.length) {
    variant = 'cover';
    const eyebrow = elements.find((el) => el.type === 'text' && el.role === 'custom');
    if (profile) {
      titleBox = profile.cover.title;
      contentBox = profile.cover.body;
      titleStyle.textAlign = profile.cover.align || 'left';
      place(eyebrow, profile.cover.eyebrow, { textAlign: profile.cover.align || 'left', color: colors.sub });
    } else if (adaptive && theme === 'soft-blue') {
      titleBox = box(80, 158, 780, 168);
      contentBox = box(80, 350, 700, 126);
      place(eyebrow, box(80, 98, 700, 30), { textAlign: 'left', color: colors.sub });
    } else if (adaptive && theme === 'clean-white') {
      titleBox = box(64, 120, 410, 310);
      contentBox = box(530, 220, 366, 230);
      place(eyebrow, box(64, 65, 410, 30), { textAlign: 'left', color: colors.sub });
    } else {
      titleBox = box(100, 150, 760, 180);
      contentBox = box(160, 360, 640, 120);
      titleStyle.textAlign = 'center';
      place(eyebrow, box(100, 94, 760, 30), { textAlign: 'center', color: colors.sub });
    }
    if (slide.type === 'thankyou' && CLOSING_LAYOUTS[theme]) {
      const closing = CLOSING_LAYOUTS[theme];
      titleBox = closing.title;
      contentBox = closing.body;
      titleStyle.textAlign = closing.titleAlign;
    }
    titleStyle.fontSize = textLength(title?.content) > 100 ? 38 : 46;
  } else if (visuals.length) {
    const dense = visuals.some(isDenseVisual) || visuals.length > 1 || bodyLength > 320 || images.length > 0;
    variant = dense ? 'data-wide' : 'data-editorial';
    if (!dense && profile) {
      titleBox = profile.data.title;
      contentBox = profile.data.body;
      titleStyle.fontSize = titleBox.width < 300 ? 28 : 34;
      titleStyle.textAlign = profile.data.align || 'left';
      const visualBox = !bodies.length && titleBox.width > 600
        ? { ...profile.data.visual, x: titleBox.x, width: titleBox.width }
        : profile.data.visual;
      place(visuals[0], visualBox);
    } else if (!dense && theme === 'clean-white') {
      titleBox = box(56, 76, 224, 190);
      contentBox = box(56, 292, 224, 198);
      titleStyle.fontSize = 28;
      place(visuals[0], box(314, 66, 590, 424));
    } else if (!dense && theme === 'blue-planet') {
      titleBox = box(682, 74, 220, 184);
      contentBox = box(682, 292, 220, 198);
      titleStyle.fontSize = 28;
      place(visuals[0], box(48, 74, 602, 416));
    } else {
      const top = bodies.length ? 212 : 132;
      const slots = [...visuals, ...images];
      const width = (848 - 20 * (slots.length - 1)) / slots.length;
      slots.forEach((el, index) => place(el, box(56 + index * (width + 20), top, width, 500 - top)));
      contentBox = box(64, 130, 832, 70);
    }
  } else if (images.length) {
    variant = 'image-split';
    let imageBox;
    if (profile) {
      titleBox = profile.image.title;
      contentBox = profile.image.body;
      imageBox = profile.image.visual;
    } else if (theme === 'soft-blue' || !adaptive) {
      contentBox = box(64, 154, bodyLength > 650 ? 470 : 410, 338);
      imageBox = box(bodyLength > 650 ? 566 : 506, 146, bodyLength > 650 ? 330 : 390, 346);
    } else if (theme === 'clean-white') {
      titleBox = box(510, 58, 386, 124);
      contentBox = box(510, 208, 386, 284);
      imageBox = box(56, 58, 414, 434);
    } else {
      titleBox = box(56, 48, 848, 86);
      contentBox = box(568, 164, 328, 324);
      imageBox = box(56, 148, 476, 344);
    }
    const height = (imageBox.height - 16 * (images.length - 1)) / images.length;
    images.forEach((el, index) => place(el, box(imageBox.x, imageBox.y + index * (height + 16), imageBox.width, height)));
  } else if (profile && bodyLength <= 800) {
    variant = `${theme}-text`;
    titleBox = profile.text.title;
    contentBox = profile.text.body;
    titleStyle.fontSize = titleBox.width < 300 ? 30 : 34;
    titleStyle.textAlign = profile.text.align || 'left';
  } else if (theme === 'clean-white' && bodyLength <= 800) {
    variant = 'title-rail';
    titleBox = box(64, 94, 258, 338);
    contentBox = box(372, 100, 524, 386);
    titleStyle.fontSize = 32;
  }
  if (!boundary && !visuals.length && !images.length && adaptive && bodies.length === 1 && bodyLength <= 600 && theme !== 'clean-white') {
    const items = listItems(bodies[0].content, bodies[0].layoutGroup);
    if (items?.length >= 3 && items.length <= 6 && items.every((item) => textLength(item) <= 160)) {
      variant = profile ? `${theme}-points` : theme === 'soft-blue' ? 'two-column-points' : 'three-column-points';
      const columns = profile?.columns || (theme === 'soft-blue' ? 2 : 3);
      const rows = Math.ceil(items.length / columns);
      const gap = columns === 1 ? 16 : 28;
      const width = (contentBox.width - gap * (columns - 1)) / columns;
      const height = (contentBox.height - gap * (rows - 1)) / rows;
      const original = bodies[0];
      const parts = items.map((item, index) => ({ ...original,
        id: index === 0 ? original.id : `${original.id}-point-${index}`,
        layoutGroup: original.layoutGroup || original.id,
        layoutOrder: index,
        content: `<ul>${item}</ul>`,
        ...box(contentBox.x + (index % columns) * (width + gap), contentBox.y + Math.floor(index / columns) * (height + gap), width, height),
        style: { ...original.style, fontSize: columns === 1 ? 20 : theme === 'soft-blue' ? 23 : 21, lineHeight: 1.45 },
      }));
      elements = elements.flatMap((el) => el === original ? parts : [el]);
      bodies.length = 0;
    }
  }
  place(title, titleBox, titleStyle);
  const bodyHeight = (contentBox.height - 18 * (bodies.length - 1)) / Math.max(1, bodies.length);
  bodies.forEach((el, index) => place(el, box(contentBox.x, contentBox.y + index * (bodyHeight + 18), contentBox.width, bodyHeight), {
    fontSize: slide.type === 'thankyou' ? 24 : bodyLength > 800 ? 17 : 22, lineHeight: 1.45,
    textAlign: slide.type === 'thankyou' ? 'left'
      : boundary ? profile?.cover.align || (theme === 'blue-planet' ? 'center' : 'left') : 'left',
  }));
  return elements.map((el) => ({ ...el, templateLayout: variant }));
}
