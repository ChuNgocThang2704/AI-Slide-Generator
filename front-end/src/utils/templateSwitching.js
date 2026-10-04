import { createElementsFromSlide, reflowSlideTemplate } from './slideElements.js';
import { toSlidePageUpdate } from './slideMapping.js';
import { ADAPTIVE_TEMPLATES, isBoundaryLabel } from './templateLayouts.js';
import { mapTemplateFont } from './templateFonts.js';
import { isUserGraphic } from './shapeLibrary.js';
import { buildTemplateArt, withoutTemplateArt } from './templateArt.js';
import { avoidArt } from './templateAvoid.js';

const escapeHtml = (text) => String(text || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
// Alignment and size are deliberately not imported: the layout engine already
// fits text to its frame and keeps the traditional left-aligned reading order,
// while a PPTX placeholder's right-aligned or tiny defaults broke both.
const STYLE_KEYS = ['fontFamily', 'fontWeight', 'color', 'lineHeight'];

function styleForRole(match, role) {
  const explicit = role === 'title' ? match?.titleStyle : match?.bodyStyle;
  const fallback = match?.elements?.find((el) => el.type === 'text' && el.role === role)?.style;
  const source = explicit && Object.keys(explicit).length ? explicit : fallback || {};
  const style = Object.fromEntries(STYLE_KEYS.filter((key) => source[key] !== undefined).map((key) => [key, source[key]]));
  // Only fonts this app has loaded; an unknown template font would fall back to a serif default.
  style.fontFamily = mapTemplateFont(style.fontFamily || (role === 'title' ? match?.headingFont : match?.bodyFont));
  return style;
}

function baseThemeFor(slide, preferredTheme) {
  if (ADAPTIVE_TEMPLATES.has(preferredTheme)) return preferredTheme;
  return slide?.elements?.find((el) => ADAPTIVE_TEMPLATES.has(el.templateBaseTheme))?.templateBaseTheme || 'soft-blue';
}

function importedTheme(match, titleStyle, bodyStyle) {
  return {
    primary: match?.primaryColor || titleStyle.color || '#4f46e5',
    background: '#ffffff',
    text: titleStyle.color || '#1f2937',
    textSub: bodyStyle.color || '#374151',
    fontTitle: titleStyle.fontFamily || mapTemplateFont(match?.headingFont),
    fontBody: bodyStyle.fontFamily || mapTemplateFont(match?.bodyFont),
  };
}

function supplements(elements) {
  const primaryImage = elements.find((el) => el.type === 'image' && el.src && !el.templateSupplement);
  return elements.filter((el) => {
    if (el.templateSupplement) return true;
    if (String(el.id).startsWith('template-')) return false;
    if (isUserGraphic(el)) return true;
    if (el.type === 'image' && el.src && el !== primaryImage) return true;
    if (el.type !== 'text' || el.role !== 'custom') return false;
    return !isBoundaryLabel(el);
  }).map((el) => ({ ...el, templateSupplement: true }));
}

export function prepareTemplateContent(slide, theme) {
  const elements = createElementsFromSlide(slide, theme);
  const update = toSlidePageUpdate({ ...slide, elements });
  const image = elements.find((el) => el.type === 'image' && el.src && !el.templateSupplement);
  const table = elements.find((el) => el.type === 'table');
  const chart = elements.find((el) => el.type === 'chart');
  const bullets = elements.some((el) => el.type === 'text' && el.role === 'body') || table || chart ? update.bullets : [];
  return {
    ...slide, ...update, type: slide.type,
    title: elements.some((el) => el.type === 'text' && el.role === 'title') ? update.title : '',
    bullets, text: bullets.join('\n'),
    subtitle: ['title', 'thankyou'].includes(slide.type) ? bullets.join('\n') : slide.subtitle,
    imageUrl: image?.src || '', table: table?.data || null, chart: chart?.data || null,
    elements,
  };
}

export function applyCustomTemplateResult(slide, match, preferredBaseTheme) {
  const hasImportedStyles = [match?.titleStyle, match?.bodyStyle]
    .some((style) => style && Object.keys(style).length);
  if (!hasImportedStyles && (!Array.isArray(match?.elements) || !match.elements.length)) {
    throw new Error('Template không trả về thông tin định dạng hợp lệ');
  }
  const baseTheme = baseThemeFor(slide, preferredBaseTheme);
  const titleStyle = styleForRole(match, 'title');
  const bodyStyle = styleForRole(match, 'body');
  const theme = importedTheme(match, titleStyle, bodyStyle);
  const extras = supplements(slide.elements || []);
  // The sample slide's background and pictures live beside the elements, and tell the
  // layout where the art sits so the text keeps clear of it.
  const art = buildTemplateArt(match);
  const richText = withoutTemplateArt(slide.richText);
  if (art.decor.length) {
    richText._decor = art.decor;
    if (art.pageColor) richText._tplBg = art.pageColor;
    if (art.safe) richText._safe = art.safe;
  }
  const rebuilt = reflowSlideTemplate({ ...slide, richText, elements: [] }, baseTheme);
  // The layout only knows a left/right band; move any text still lying on a picture or shape clear of it.
  const elements = avoidArt(rebuilt.elements, art.decor).map((element) => {
    const importedStyle = element.type === 'text' && element.role === 'title'
      ? titleStyle
      : element.type === 'text' && element.role === 'body' ? bodyStyle : null;
    return {
      ...element,
      templateStyleOnly: true,
      templateBaseTheme: baseTheme,
      templateTheme: theme,
      style: importedStyle ? { ...element.style, ...importedStyle } : element.style,
    };
  });
  return {
    ...slide,
    richText,
    templateLayoutId: match.layoutId,
    elements: [...elements, ...extras],
  };
}

const withoutTemplateFlags = (element) => {
  const next = { ...element };
  delete next.templateTheme;
  delete next.templateStyleOnly;
  delete next.templateBaseTheme;
  return next;
};

export function restoreBuiltInTemplate(slide, theme) {
  const content = prepareTemplateContent(slide, theme);
  // Carried-over extras must not keep a custom template's palette or style-only flag.
  const extras = supplements(content.elements).map(withoutTemplateFlags);
  const images = content.elements.filter((el) => el.type === 'image' && el.src && !el.templateSupplement);
  const uniqueImages = images.filter((el, index) => images.findIndex((item) => item.src === el.src) === index);
  const rebuilt = reflowSlideTemplate({
    ...content,
    elements: [],
    // Remove imported inline styling while keeping literal user text safe as HTML.
    title: escapeHtml(content.title),
    bullets: content.bullets, // plain text: the element builder escapes list items itself
    subtitle: content.bullets.map(escapeHtml).join('<br>'),
    text: content.bullets.map(escapeHtml).join('<br>'),
    richText: { ...withoutTemplateArt(content.richText), title: '', bullets: '', subtitle: '', text: '' },
  }, theme);
  const primary = rebuilt.elements.find((el) => el.type === 'image');
  if (primary && uniqueImages[0]) {
    for (const key of ['assetId', 'storageUrl', 'objectFit', 'objectPositionX', 'objectPositionY']) {
      if (uniqueImages[0][key] !== undefined) primary[key] = uniqueImages[0][key];
    }
  }
  return {
    ...content, templateLayoutId: undefined,
    richText: withoutTemplateArt(content.richText),
    elements: [...rebuilt.elements, ...extras, ...uniqueImages.slice(1)
      .filter((el) => !extras.some((extra) => extra.id === el.id))
      .map((el) => ({ ...el, templateSupplement: true }))],
  };
}
