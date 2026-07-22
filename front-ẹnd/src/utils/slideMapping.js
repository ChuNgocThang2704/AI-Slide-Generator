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
  if (page?.table) return 'table';
  if (page?.chart) return 'chart';
  if (page?.imageUrl) return 'imageText';

  const layout = String(page?.layout || '').toLowerCase();
  if (layout === 'title' || layout === 'intro') return 'title';
  if (['text_image', 'image_text', 'imagetext'].includes(layout)) return 'imageText';
  if (['twocolumn', 'two_column', 'split_columns'].includes(layout)) return 'twoColumn';
  if (['quote', 'big_quote'].includes(layout)) return 'quote';
  if (['thankyou', 'thank_you'].includes(layout)) return 'thankyou';
  if (layout === 'text_table') return 'table';
  if (layout === 'text_chart') return 'chart';
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
    elements: Array.isArray(page.elements) ? page.elements : [],
    notes: page.notes || '',
    primaryVisual: page.primaryVisual || '',
    likelyMultiPptxSlides: page.likelyMultiPptxSlides || false,
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
  };
}
