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

export function backendLayoutToFrontend(page) {
  const layout = String(page?.layout || '').toLowerCase();
  const role = String(page?.pedagogicalRole || '').toLowerCase();
  const title = String(page?.title || '').toLocaleLowerCase('vi');

  // Boundary slides keep their dedicated composition even when they contain
  // an optional visual or stale persisted editor metadata.
  if (layout === 'title' || layout === 'intro') return 'title';
  if (['thankyou', 'thank_you'].includes(layout)) return 'thankyou';
  if (Number(page?.pageIndex) === 0 && !['table', 'chart'].includes(layout)) return 'title';
  if (
    role === 'summary'
    && /(tổng kết|kết luận|hỏi đáp|cảm ơn|summary|conclusion|thank|q&a)/i.test(title)
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

function normalizeElementText(value) {
  return String(value || '')
    .replace(/<\/li>/gi, ' ')
    .replace(/<br\s*\/?>/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;|&#160;/gi, ' ')
    .replace(/&amp;/gi, '&')
    .replace(/\s+/g, ' ')
    .trim()
    .toLocaleLowerCase('vi');
}

function currentElements(page, bullets) {
  const elements = Array.isArray(page?.elements) ? page.elements : [];
  if (!elements.length) return [];

  const titleElement = elements.find((element) => element?.type === 'text' && element?.role === 'title');
  const bodyElement = elements.find((element) => element?.type === 'text' && element?.role === 'body');
  const backendLayout = String(page?.layout || '').toLowerCase();
  const frontendType = backendLayoutToFrontend(page);
  const isBoundarySlide = frontendType === 'title' || frontendType === 'thankyou';
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
  if (bodyElement && expectedBody && normalizeElementText(bodyElement.content) !== expectedBody) return [];
  return elements;
}

function parseTwoColumns(bullets) {
  const groups = [];
  bullets.forEach((bullet) => {
    const [heading, ...contentParts] = String(bullet).split(' — ');
    if (!contentParts.length) return;
    const content = contentParts.join(' — ').trim();
    let group = groups.find((item) => item.heading === heading.trim());
    if (!group) {
      group = { heading: heading.trim(), points: [] };
      groups.push(group);
    }
    if (content) group.points.push(content);
  });

  if (groups.length >= 2) return [groups[0], groups[1]];
  const half = Math.ceil(bullets.length / 2);
  return [
    { heading: 'Cơ hội & Lợi ích', points: bullets.slice(0, half) },
    { heading: 'Thách thức & Rủi ro', points: bullets.slice(half) },
  ];
}

function serializeBullets(slide) {
  if (slide.type === 'imageText') return splitText(slide.text);
  if (slide.type === 'twoColumn') {
    const columns = [slide.left, slide.right].filter(Boolean);
    return columns.flatMap((column) => (column.points || []).map((point) => `${column.heading || 'Nội dung'} — ${point}`));
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

export function formatSlidePage(page) {
  const bullets = parseBullets(page);
  const type = backendLayoutToFrontend(page);
  const joinedText = bullets.join('\n');
  const [leftColumn, rightColumn] = parseTwoColumns(bullets);
  const attribution = type === 'quote' ? String(bullets[1] || '').replace(/^—\s*/, '').split(/,\s*/, 2) : [];

  return {
    id: page.id,
    type,
    title: page.title || '',
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
    elements: currentElements(page, bullets),
    notes: page.notes || '',
    primaryVisual: page.primaryVisual || '',
    likelyMultiPptxSlides: page.likelyMultiPptxSlides || false,
    pedagogicalRole: page.pedagogicalRole || '',
    sourcePages: Array.isArray(page.sourcePages) ? page.sourcePages : [],
  };
}

export function toSlidePageUpdate(slide) {
  const elementTitle = slide.elements?.find((element) => element.role === 'title' && element.type === 'text');
  const elementBody = slide.elements?.find((element) => element.role === 'body' && element.type === 'text');
  const plainText = (html) => String(html || '').replace(/<[^>]+>/g, ' ').replace(/&nbsp;/g, ' ').replace(/\s+/g, ' ').trim();
  const semanticTitle = elementTitle ? plainText(elementTitle.content) : slide.title;
  const semanticBullets = elementBody
    ? String(elementBody.content || '').replace(/<\/li>/gi, '\n').replace(/<br\s*\/?>/gi, '\n').replace(/<[^>]+>/g, '').split('\n').map((item) => item.trim()).filter(Boolean)
    : serializeBullets(slide);
  return {
    id: slide.id,
    title: semanticTitle,
    bullets: semanticBullets,
    notes: slide.notes || '',
    imageUrl: slide.imageUrl || '',
    layout: frontendLayoutToBackend(slide),
    chart: slide.chart || null,
    table: slide.table || null,
    richText: slide.richText || {},
    elements: Array.isArray(slide.elements) ? slide.elements : [],
    primaryVisual: slide.table ? 'table' : slide.chart ? 'chart' : slide.primaryVisual || '',
    likelyMultiPptxSlides: slide.likelyMultiPptxSlides || false,
    pedagogicalRole: slide.pedagogicalRole || '',
    sourcePages: Array.isArray(slide.sourcePages) ? slide.sourcePages : [],
  };
}
