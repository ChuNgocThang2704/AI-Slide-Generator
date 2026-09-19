import { createElementsFromSlide, reflowSlideTemplate } from './slideElements.js';
import { toSlidePageUpdate } from './slideMapping.js';
import { ADAPTIVE_TEMPLATES } from './templateLayouts.js';

const escapeHtml = (text) => String(text || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const STYLE_KEYS = ['fontFamily', 'fontSize', 'fontWeight', 'color', 'textAlign', 'verticalAlign', 'lineHeight'];

const clamp = (value, min, max, fallback) => {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? Math.min(max, Math.max(min, numeric)) : fallback;
};

function styleForRole(match, role) {
  const explicit = role === 'title' ? match?.titleStyle : match?.bodyStyle;
  const fallback = match?.elements?.find((el) => el.type === 'text' && el.role === role)?.style;
  const source = explicit && Object.keys(explicit).length ? explicit : fallback || {};
  const style = Object.fromEntries(STYLE_KEYS.filter((key) => source[key] !== undefined).map((key) => [key, source[key]]));
  style.fontSize = role === 'title'
    ? clamp(style.fontSize, 26, 54, 34)
    : clamp(style.fontSize, 14, 26, 18);
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
    fontTitle: titleStyle.fontFamily || match?.headingFont || 'Arial, sans-serif',
    fontBody: bodyStyle.fontFamily || match?.bodyFont || 'Arial, sans-serif',
  };
}

function supplements(elements) {
  const primaryImage = elements.find((el) => el.type === 'image' && el.src && !el.templateSupplement);
  return elements.filter((el) => {
    if (el.templateSupplement) return true;
    if (String(el.id).startsWith('template-')) return false;
    if (el.type === 'image' && el.src && el !== primaryImage) return true;
    if (el.type !== 'text' || el.role !== 'custom') return false;
    return !(el.templateLayout === 'cover' && ['BÀI GIẢNG', 'LECTURE', 'KẾT THÚC BÀI GIẢNG', 'END OF LECTURE'].includes(el.content));
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
  const rebuilt = reflowSlideTemplate({ ...slide, elements: [] }, baseTheme);
  const elements = rebuilt.elements.map((element) => {
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
    templateLayoutId: match.layoutId,
    elements: [...elements, ...extras],
  };
}

export function restoreBuiltInTemplate(slide, theme) {
  const content = prepareTemplateContent(slide, theme);
  const extras = supplements(content.elements);
  const images = content.elements.filter((el) => el.type === 'image' && el.src && !el.templateSupplement);
  const uniqueImages = images.filter((el, index) => images.findIndex((item) => item.src === el.src) === index);
  const rebuilt = reflowSlideTemplate({
    ...content,
    elements: [],
    // Remove imported inline styling while keeping literal user text safe as HTML.
    title: escapeHtml(content.title),
    bullets: content.bullets.map(escapeHtml),
    subtitle: content.bullets.map(escapeHtml).join('<br>'),
    text: content.bullets.map(escapeHtml).join('<br>'),
    richText: { ...content.richText, title: '', bullets: '', subtitle: '', text: '' },
  }, theme);
  const primary = rebuilt.elements.find((el) => el.type === 'image');
  if (primary && uniqueImages[0]) {
    for (const key of ['assetId', 'storageUrl', 'objectFit', 'objectPositionX', 'objectPositionY']) {
      if (uniqueImages[0][key] !== undefined) primary[key] = uniqueImages[0][key];
    }
  }
  return {
    ...content, templateLayoutId: undefined,
    elements: [...rebuilt.elements, ...extras, ...uniqueImages.slice(1)
      .filter((el) => !extras.some((extra) => extra.id === el.id))
      .map((el) => ({ ...el, templateSupplement: true }))],
  };
}
