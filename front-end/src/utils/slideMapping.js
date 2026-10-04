import { inferImageFit } from './imageFit.js';
import { reflowSlideTemplate } from './slideElements.js';
import { ADAPTIVE_TEMPLATES, normalizeBoundaryElements, normalizeTableElements, orderedBodyElements } from './templateLayouts.js';

// Compositions the first template generator produced (rails, split columns,
// per-theme text profiles). They hid the traditional horizontal text layout,
// so slides still carrying them return to the classic arrangement on load.
const LEGACY_GENERATED_LAYOUT = /(^title-rail$|-points$|-text$)/;
// Cover/closing slides saved by the first generator carry the bare "cover"
// marker (the current engine writes cover-* / closing-*).
const hasLegacyBoundaryLayout = (elements) => elements.some((element) => (
  element?.type === 'text' && element.templateLayout === 'cover'
));
const isLegacyGeneratedLayout = (elements) => elements.some((element) => (
  element?.type === 'text' && LEGACY_GENERATED_LAYOUT.test(String(element.templateLayout || ''))
));

export function parseBullets(page) {
  if (Array.isArray(page?.bullets)) return page.bullets;
  if (typeof page?.bullets === 'string') {
    try {
      const parsed = JSON.parse(page.bullets);
      if (Array.isArray(parsed)) return parsed;
    } catch {
      // Plain text bullets are handled below.
    }
    return page.bullets.split('\n').filter((line) => line.trim());
  }
  return [];
}

// The closing composition shows two lines (a closing sentence and a contact line). A last slide
// the AI filled with a real summary has more points than that: it is shown as a content slide,
// otherwise every point after the second is dropped on screen and then on the next save.
const CLOSING_LINES = 2;
const fitsClosingComposition = (page) => (
  parseBullets(page).filter((bullet) => String(bullet || '').trim()).length <= CLOSING_LINES
);

export function backendLayoutToFrontend(page) {
  const layout = String(page?.layout || '').toLowerCase();
  const role = String(page?.pedagogicalRole || '').toLowerCase();
  const title = String(page?.title || '').toLocaleLowerCase('vi');

  // Boundary slides keep their dedicated composition even when they contain
  // an optional visual or stale persisted editor metadata.
  if (layout === 'title' || layout === 'intro') return 'title';
  if (['thankyou', 'thank_you'].includes(layout) && fitsClosingComposition(page)) return 'thankyou';
  if (Number(page?.pageIndex) === 0 && !['table', 'chart'].includes(layout)) return 'title';
  if (
    role === 'summary'
    && /(tổng kết|kết luận|hỏi đáp|cảm ơn|summary|conclusion|thank|q&a)/i.test(title)
    && fitsClosingComposition(page)
  ) return 'thankyou';

  if (page?.table) return 'table';
  if (page?.chart) return 'chart';
  if (page?.imageUrl) return 'imageText';

  if (['text_image', 'image_text', 'imagetext'].includes(layout)) return 'imageText';
  if (['twocolumn', 'two_column', 'split_columns'].includes(layout)) return 'twoColumn';
  if (['quote', 'big_quote'].includes(layout)) return 'quote';
  // Never render an empty visual frame when the structured payload is absent.
  if (layout === 'text_table') return page?.table ? 'table' : 'content';
  if (layout === 'text_chart') return page?.chart ? 'chart' : 'content';
  return page?.pageIndex === 0 && !layout ? 'title' : 'content';
}

export function frontendLayoutToBackend(slide) {
  if (slide?.table || slide?.type === 'table') return 'text_table';
  if (slide?.chart || slide?.type === 'chart') return 'text_chart';

  return {
    title: 'title',
    content: 'text_only',
    imageText: 'text_image',
    twoColumn: 'split_columns',
    quote: 'big_quote',
    thankyou: 'thankyou',
  }[slide?.type] || 'text_only';
}

function splitText(value) {
  return String(value || '').split(/\r?\n+/).map((item) => item.trim()).filter(Boolean);
}

export function slideTextLines(html) {
  const separated = String(html || '').replace(/<\/(?:li|p|div|h[1-6])>/gi, '\n').replace(/<br\s*\/?>/gi, '\n');
  let text;
  if (typeof DOMParser !== 'undefined') {
    text = new DOMParser().parseFromString(separated, 'text/html').body.textContent || '';
  } else {
    text = separated.replace(/<[^>]+>/g, '').replace(/&nbsp;|&#160;/gi, ' ')
      .replace(/&lt;/gi, '<').replace(/&gt;/gi, '>').replace(/&quot;/gi, '"').replace(/&#39;/gi, "'").replace(/&amp;/gi, '&');
  }
  return text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
}

function normalizeElementText(value) {
  return slideTextLines(value).join(' ')
    .replace(/\s+/g, ' ')
    .trim()
    .toLocaleLowerCase('vi');
}

function currentElements(page, bullets) {
  const elements = Array.isArray(page?.elements) ? page.elements : [];
  if (!elements.length) return [];

  const titleElement = elements.find((element) => element?.type === 'text' && element?.role === 'title');
  const bodyElement = elements.find((element) => element?.type === 'text' && element?.role === 'body');
  const bodyContent = orderedBodyElements(elements)
    .map((element) => element.content).join(' ');
  const frontendType = backendLayoutToFrontend(page);
  const isBoundarySlide = frontendType === 'title' || frontendType === 'thankyou';
  const isLegacyBoundaryTextCanvas = isBoundarySlide
    && elements.length > 0
    && elements.every((element) => (
      element?.type === 'text'
      && ['title', 'body'].includes(element?.role)
    ))
    && Number(titleElement?.style?.fontSize || 0) <= 40
    && String(titleElement?.style?.textAlign || 'left') === 'left'
    && (
      !bodyElement
      || (
        Number(bodyElement?.style?.fontSize || 0) <= 22
        && String(bodyElement?.style?.textAlign || 'left') === 'left'
      )
    );
  if (isLegacyBoundaryTextCanvas) return [];
  const genericCanvasLayout = titleElement
    && titleElement.x === 64
    && [44, 48].includes(Number(titleElement.y))
    && (!bodyElement || (
      bodyElement.x === 64
      && [112, 140].includes(Number(bodyElement.y))
    ));
  // Migrate only the old generic boundary layout. Custom user positioning
  // does not match these coordinates and remains untouched.
  if (isBoundarySlide && genericCanvasLayout) return [];
  const legacyDefaultLayout = titleElement
    && Number(titleElement?.style?.fontSize) === 36
    && titleElement.x === 64
    && titleElement.y === 48
    && (!bodyElement || (Number(bodyElement?.style?.fontSize) === 20 && bodyElement.y === 140));
  if (legacyDefaultLayout) return [];
  const expectedTitle = normalizeElementText(page?.title);
  const expectedBody = normalizeElementText(bullets.join(' '));

  // AI revision updates semantic fields first. Do not let persisted editor
  // elements from the previous revision hide that newer content.
  if (titleElement && expectedTitle && normalizeElementText(titleElement.content) !== expectedTitle) return [];
  if (bodyElement && expectedBody && normalizeElementText(bodyContent) !== expectedBody) return [];
  return elements;
}

// A two-column slide carries its column headings in its bullets ("Heading — point"). The AI
// service's text clean-up turns the long dash into a plain hyphen, so both are read; a hyphen only
// counts when it yields exactly two headings shared by every bullet (a lone "A - b" is just text).
function groupByHeading(bullets, separator) {
  const groups = [];
  for (const bullet of bullets) {
    const text = String(bullet);
    const at = text.indexOf(separator);
    if (at <= 0) return null;
    const heading = text.slice(0, at).trim();
    const content = text.slice(at + separator.length).trim();
    if (!heading || !content) return null;
    let group = groups.find((item) => item.heading === heading);
    if (!group) {
      group = { heading, points: [] };
      groups.push(group);
    }
    group.points.push(content);
  }
  return groups;
}

export function parseTwoColumns(bullets) {
  for (const separator of [' — ', ' – ', ' - ']) {
    const groups = groupByHeading(bullets, separator);
    if (groups && groups.length === 2) return groups;
  }
  // No headings to read: two plain columns, without inventing names for them.
  const half = Math.ceil(bullets.length / 2);
  return [
    { heading: '', points: bullets.slice(0, half) },
    { heading: '', points: bullets.slice(half) },
  ];
}

function serializeBullets(slide) {
  if (slide.type === 'imageText') return splitText(slide.text);
  if (slide.type === 'twoColumn') {
    const columns = [slide.left, slide.right].filter(Boolean);
    return columns.flatMap((column) => (column.points || []).map((point) => (column.heading ? `${column.heading} — ${point}` : point)));
  }
  if (slide.type === 'quote') {
    const attribution = [slide.author, slide.role].filter(Boolean).join(', ');
    return [slide.quote, attribution ? `— ${attribution}` : ''].filter(Boolean);
  }
  if (slide.type === 'title' || slide.type === 'thankyou') {
    return [slide.subtitle, slide.contact].filter(Boolean);
  }
  return Array.isArray(slide.bullets) ? slide.bullets : [];
}

export function formatSlidePage(page, { presentationMode = 'presentation', theme } = {}) {
  const bullets = parseBullets(page);
  const type = backendLayoutToFrontend(page);
  const joinedText = bullets.join('\n');
  const [leftColumn, rightColumn] = parseTwoColumns(bullets);
  const attribution = type === 'quote' ? String(bullets[1] || '').replace(/^—\s*/, '').split(/,\s*/, 2) : [];

  const imageFit = page?.richText?._imageFit || inferImageFit(page);
  const elements = currentElements(page, bullets).map((element) => {
    if (element?.type !== 'image' || element.fitExplicit) return element;
    return {
      ...element,
      objectFit: inferImageFit({ ...page, imageUrl: element.src || page?.imageUrl }),
    };
  });

  const formatted = {
    id: page.id,
    type,
    title: page.title || page.table?.title || '',
    bullets,
    subtitle: page.subtitle || ((type === 'title' || type === 'thankyou') ? bullets[0] || '' : ''),
    contact: type === 'thankyou' ? bullets[1] || '' : '',
    left: type === 'twoColumn' ? leftColumn : null,
    right: type === 'twoColumn' ? rightColumn : null,
    imageEmoji: '✨',
    text: page.content || joinedText,
    quote: type === 'quote' ? bullets[0] || '' : '',
    author: type === 'quote' ? attribution[0] || 'Expert' : '',
    role: page.role || (type === 'quote' ? attribution[1] || 'Chuyên gia' : 'Chuyên gia'),
    imagePrompt: page.imagePrompt || '',
    imageUrl: page.imageUrl || '',
    pageIndex: page.pageIndex,
    chart: page.chart || null,
    table: page.table || null,
    richText: page.richText || {},
    elements: normalizeBoundaryElements(normalizeTableElements(elements), type, theme),
    imageFit,
    notes: page.notes || '',
    primaryVisual: page.primaryVisual || '',
    likelyMultiPptxSlides: page.likelyMultiPptxSlides || false,
    pedagogicalRole: page.pedagogicalRole || '',
    sourcePages: Array.isArray(page.sourcePages) ? page.sourcePages : [],
    presentationMode: String(
      page.presentationMode || page.presentation_mode || presentationMode || 'presentation'
    ).toLowerCase(),
  };
  if (ADAPTIVE_TEMPLATES.has(theme) && !['title', 'thankyou', 'quote'].includes(type)
    && isLegacyGeneratedLayout(formatted.elements)) {
    return { ...formatted, elements: reflowSlideTemplate(formatted, theme).elements };
  }
  return formatted;
}

function polishedCoverSubtitle(slide) {
  const current = String(slide?.subtitle || '').trim();
  const plain = current.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
  const folded = plain.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  const definitionLike = !plain
    || plain.length > 150
    || plain.slice(0, 40).includes(':')
    || /^(dinh nghia|khai niem|definition\b|defined as\b)/.test(folded);
  if (!definitionLike) return { subtitle: plain, replaced: false };

  const rawTitle = String(slide?.title || '').trim();
  const topic = rawTitle
    .replace(/^\s*(giới thiệu|tổng quan)\s+(về\s+)?/i, '')
    .replace(/^\s*(introduction|overview)\s+(to|of)\s+/i, '')
    .trim() || rawTitle;
  const vietnamese = /[ăâđêôơưàáạảãằắặẳẵầấậẩẫèéẹẻẽềếệểễìíịỉĩòóọỏõồốộổỗờớợởỡùúụủũừứựửữỳýỵỷỹ]/i.test(rawTitle + plain);
  return {
    subtitle: vietnamese
      ? `Khám phá ${topic} qua các nội dung trọng tâm và góc nhìn thực tiễn.`
      : `Explore ${topic} through its key ideas and practical perspectives.`,
    replaced: true,
  };
}

export function formatSlideDeck(pages, presentationMode = '', theme) {
  const source = Array.isArray(pages) ? pages : [];
  const explicitMode = String(presentationMode || '').trim().toLowerCase();
  const pageMode = source
    .map((page) => String(page?.presentationMode || page?.presentation_mode || '').trim().toLowerCase())
    .find((mode) => mode === 'lecture' || mode === 'presentation');
  const hasLectureMetadata = source.some((page) => (
    Boolean(page?.pedagogicalRole || page?.pedagogical_role)
    || (Array.isArray(page?.sourcePages || page?.source_pages) && (page.sourcePages || page.source_pages).length > 0)
  ));
  const effectiveMode = explicitMode === 'lecture' || explicitMode === 'presentation'
    ? explicitMode
    : pageMode || (hasLectureMetadata ? 'lecture' : 'presentation');
  const slides = source.map((page) => formatSlidePage(page, { presentationMode: effectiveMode, theme }));
  if (!slides.length) return slides;

  // Cover and closing slides are ordinary canvases. Whatever the user placed,
  // resized or restyled must survive a reload, so saved elements are kept as-is;
  // only a slide with no canvas yet is generated (and its subtitle polished).
  const first = slides[0];
  const hasCanvas = (slide) => Array.isArray(slide?.elements) && slide.elements.length > 0;
  if (hasCanvas(first)) {
    slides[0] = { ...first, type: 'title' };
  } else {
    const cover = polishedCoverSubtitle(first);
    slides[0] = { ...first, type: 'title', subtitle: cover.subtitle, bullets: [cover.subtitle], elements: [] };
  }

  if (slides.length > 1) {
    const lastIndex = slides.length - 1;
    const rawLast = source[lastIndex] || {};
    const last = slides[lastIndex];
    const rawLayout = String(rawLast.layout || '').toLowerCase();
    const rawRole = String(rawLast.pedagogicalRole || '').toLowerCase();
    const closingTitle = String(rawLast.title || last.title || '').toLocaleLowerCase('vi');
    const isClosing = fitsClosingComposition(rawLast) && (
      ['thankyou', 'thank_you'].includes(rawLayout)
      || (
        rawRole === 'summary'
        && /(tổng kết|kết luận|hỏi đáp|cảm ơn|summary|conclusion|thank|q&a)/i.test(closingTitle)
      )
    );
    if (isClosing) slides[lastIndex] = { ...last, type: 'thankyou' };
  }

  // Old-generator covers and closings return to the current composition once.
  if (ADAPTIVE_TEMPLATES.has(theme)) {
    [0, slides.length - 1].forEach((index) => {
      const slide = slides[index];
      if (slide && ['title', 'thankyou'].includes(slide.type) && hasLegacyBoundaryLayout(slide.elements || [])) {
        slides[index] = { ...slide, elements: reflowSlideTemplate(slide, theme).elements };
      }
    });
  }

  return slides;
}

export function toSlidePageUpdate(slide) {
  slide = { ...slide, elements: normalizeBoundaryElements(normalizeTableElements(slide.elements), slide.type) };
  const elementTitle = slide.elements?.find((element) => element.role === 'title' && element.type === 'text');
  const bodyElements = orderedBodyElements(slide.elements);
  const plainText = (html) => slideTextLines(html).join(' ');
  const semanticTitle = elementTitle ? plainText(elementTitle.content) : slide.title;
  const semanticBullets = bodyElements.length
    ? bodyElements.flatMap((element) => slideTextLines(element.content))
    : serializeBullets(slide);
  const richText = {
    ...(slide.richText || {}),
    ...(slide.imageFit ? { _imageFit: slide.imageFit } : {}),
  };
  return {
    id: slide.id,
    title: semanticTitle,
    bullets: semanticBullets,
    notes: slide.notes || '',
    imageUrl: slide.imageUrl || '',
    layout: frontendLayoutToBackend(slide),
    chart: slide.chart || null,
    table: slide.table || null,
    richText,
    elements: Array.isArray(slide.elements) ? slide.elements : [],
    primaryVisual: slide.table ? 'table' : slide.chart ? 'chart' : slide.primaryVisual || '',
    likelyMultiPptxSlides: slide.likelyMultiPptxSlides || false,
    pedagogicalRole: slide.pedagogicalRole || '',
    sourcePages: Array.isArray(slide.sourcePages) ? slide.sourcePages : [],
  };
}
