import PptxGenJS from 'pptxgenjs';
import JSZip from 'jszip';
import { projectService } from './documentService';
import { createElementsFromSlide } from '../utils/slideElements';
import { resolveShape } from '../utils/shapeLibrary';
import { iconToPng } from '../utils/rasterize';
import { artImageToPng, dotsToPng } from '../utils/exportGraphics';
import { hasOwnOrnaments, themeOrnaments } from '../utils/themeOrnaments';
import { isBackdrop } from '../utils/templateArt';
import { ICON_COMPONENTS } from '../components/slides/iconMap';
import { withGeneratedThemes } from '../utils/generatedTheme';

const PX_PER_INCH = 72;
const SLIDE_W = 13.333333;
const SLIDE_H = 7.5;

const BASE_THEMES = {
  'soft-blue': { bg: 'F8FBFF', accent: '3B96D2', text: '0B2E4A', textSub: '4A6A85', surface: 'EAF4FC' },
  'royal-purple': { bg: '0B0518', accent: 'ED7D31', text: 'FFFFFF', textSub: 'C0A8E0', surface: '241336' },
  'clean-white': { bg: 'FFFFFF', accent: '4F46E5', text: '1A1A1A', textSub: '555555', surface: 'F5F5F5' },
  'modern-dark': { bg: '0D0D1A', accent: 'FF6584', text: 'FFFFFF', textSub: 'C7C7D8', surface: '24243B' },
  'playful-yellow': { bg: 'FFFCF0', accent: '8B5CF6', text: '2E1E0A', textSub: '654A22', surface: 'FFF4D6' },
  'gradient-border': { bg: 'F8FAFC', accent: '38BDF8', text: '0F172A', textSub: '475569', surface: 'F1F5F9' },
  'blue-planet': { bg: '02001A', accent: '4FACFE', text: 'FFFFFF', textSub: 'C8D3FF', surface: '11164A' },
  'nature-green': { bg: '0A2318', accent: '2ECC71', text: 'E8F5E2', textSub: 'BFD9B8', surface: '173B2A' },
  'tech-purple': { bg: '0A0015', accent: 'E056FD', text: 'FFFFFF', textSub: 'D9B8E8', surface: '1E0A2E' },
  'ocean-teal': { bg: 'F0FDFA', accent: '14B8A6', text: '083344', textSub: '3F6B73', surface: 'E6F7F5' },
  'editorial-paper': { bg: 'F6EFE3', accent: 'C2410C', text: '2B1D12', textSub: '6B5646', surface: 'EFE4D0' },
  'midnight-gold': { bg: '0B0F1A', accent: 'F5C542', text: 'F8F5E6', textSub: 'C9C6B6', surface: '1A2138' },
};

const THEMES = withGeneratedThemes(BASE_THEMES, (built) => built.exportPalette);

const cleanColor = (value, fallback = '000000') => {
  const match = String(value || '').match(/[0-9a-f]{6}/i);
  return match ? match[0].toUpperCase() : fallback;
};

const cleanFont = (value) => String(value || 'Arial').split(',')[0].replace(/["']/g, '').trim() || 'Arial';
const toInches = (value) => Math.max(0, Number(value) || 0) / PX_PER_INCH;
const safeFileName = (value) => String(value || 'presentation')
  .replace(/[\\/:*?"<>|]+/g, '')
  .replace(/\s+/g, '_')
  .slice(0, 80) || 'presentation';

const blobToDataUrl = (blob) => new Promise((resolve, reject) => {
  const reader = new FileReader();
  reader.onload = () => resolve(reader.result);
  reader.onerror = () => reject(reader.error);
  reader.readAsDataURL(blob);
});

// An SVG path in the 0..100 box (M, L, C, Q, Z) as pptxgenjs custom-geometry points, in inches.
function pathToPoints(d, w, h) {
  const tokens = String(d).match(/[MLCQZ]|-?\d*\.?\d+/gi) || [];
  const sx = w / 100;
  const sy = h / 100;
  const points = [];
  let i = 0;
  const num = () => Number(tokens[i++]);
  let command = '';
  while (i < tokens.length) {
    if (/[MLCQZ]/i.test(tokens[i])) command = tokens[i++].toUpperCase();
    if (command === 'Z') { points.push({ close: true }); continue; }
    if (command === 'M' || command === 'L') {
      points.push({ x: num() * sx, y: num() * sy, ...(command === 'M' ? { moveTo: true } : {}) });
    } else if (command === 'C') {
      const [x1, y1, x2, y2, x, y] = [num(), num(), num(), num(), num(), num()];
      points.push({ x: x * sx, y: y * sy, curve: { type: 'cubic', x1: x1 * sx, y1: y1 * sy, x2: x2 * sx, y2: y2 * sy } });
    } else if (command === 'Q') {
      const [x1, y1, x, y] = [num(), num(), num(), num()];
      points.push({ x: x * sx, y: y * sy, curve: { type: 'quadratic', x1: x1 * sx, y1: y1 * sy } });
    } else {
      i += 1;
    }
  }
  return points.filter((point) => point.close || Number.isFinite(point.x));
}

function htmlText(value) {
  const holder = document.createElement('div');
  holder.innerHTML = String(value || '');
  return (holder.innerText || holder.textContent || '').replace(/\u00a0/g, ' ').trim();
}

const BULLET_CODES = { 'bu-box': '2751', 'bu-arrow': '27A2', 'bu-circle': '25CB', 'bu-square': '25AA', 'bu-diamond': '2756', 'bu-check': '2713', 'bu-dash': '2013' };

// A CSS colour (hex or rgb()) as the six hex digits PowerPoint wants, or null.
function cssHex(value) {
  const text = String(value || '').trim();
  const hex = text.match(/^#([0-9a-f]{6})$/i);
  if (hex) return hex[1].toUpperCase();
  const short = text.match(/^#([0-9a-f]{3})$/i);
  if (short) return short[1].split('').map((c) => c + c).join('').toUpperCase();
  const rgb = text.match(/^rgba?\(\s*(\d+)[,\s]+(\d+)[,\s]+(\d+)/i);
  if (rgb) return rgb.slice(1, 4).map((n) => Number(n).toString(16).padStart(2, '0')).join('').toUpperCase();
  return null;
}

// What an inline element adds to the formatting of the text inside it.
function inlineFormat(node, format) {
  const next = { ...format };
  const tag = node.tagName;
  if (tag === 'STRONG' || tag === 'B') next.bold = true;
  if (tag === 'EM' || tag === 'I') next.italic = true;
  if (tag === 'U') next.underline = true;
  const css = node.style;
  if (css) {
    if (css.color && cssHex(css.color)) next.color = cssHex(css.color);
    if (css.fontSize && /px$/.test(css.fontSize)) next.fontSize = Math.max(5, parseFloat(css.fontSize));
    if (css.fontFamily) next.fontFace = cleanFont(css.fontFamily);
    if (css.letterSpacing && /px$/.test(css.letterSpacing)) next.charSpacing = parseFloat(css.letterSpacing);
    if (css.fontWeight) next.bold = Number(css.fontWeight) >= 600 || css.fontWeight === 'bold';
    if (css.fontStyle === 'italic') next.italic = true;
    if ((css.textDecoration || '').includes('underline')) next.underline = true;
  }
  return next;
}

function inlineRuns(node, format, runs) {
  node.childNodes.forEach((child) => {
    if (child.nodeType === 3) {
      const text = child.textContent.replace(/\u00a0/g, ' ').replace(/[\r\n]+/g, ' ');
      if (text) runs.push({ text, format });
    } else if (child.nodeType === 1) {
      if (child.tagName === 'UL' || child.tagName === 'OL') return;
      if (child.tagName === 'BR') runs.push({ text: '', format, lineBreak: true });
      else inlineRuns(child, inlineFormat(child, format), runs);
    }
  });
}

// The text of a box as PowerPoint paragraphs: one per block, one per list item, nested lists as
// levels with the bullet each list class stands for, and every run with its own formatting.
// (Reading the box as one string glued paragraphs together, and pptxgenjs ignores `{ type: 'ul' }`.)
function textRuns(value) {
  const holder = document.createElement('div');
  holder.innerHTML = String(value || '');
  const paragraphs = [];
  const addParagraph = (node, extra) => {
    const runs = [];
    inlineRuns(node, inlineFormat(node, {}), runs);
    // A blank paragraph is a vertical gap in the file's text, so it stays, as a line holding a space.
    if (!runs.some((run) => run.text.trim())) runs.splice(0, runs.length, { text: ' ', format: {} });
    // A list item whose spacing needed a <p> of its own carries it there.
    const styled = node.tagName === 'LI' && node.firstElementChild?.tagName === 'P' ? node.firstElementChild : node;
    const css = styled.style || {};
    paragraphs.push({
      runs,
      align: css.textAlign || node.style?.textAlign || '',
      marginLeft: parseFloat(css.marginLeft) || 0,
      spaceBefore: parseFloat(css.marginTop) || 0,
      spaceAfter: parseFloat(css.marginBottom) || 0,
      ...extra,
    });
  };
  const walkList = (list, level) => {
    const ordered = list.tagName === 'OL';
    const code = BULLET_CODES[Array.from(list.classList).find((name) => BULLET_CODES[name])];
    Array.from(list.children).forEach((item) => {
      if (item.tagName !== 'LI') return;
      addParagraph(item, {
        level,
        bullet: ordered ? { type: 'number' } : code ? { characterCode: code, indent: 22 } : { indent: 22 },
      });
      Array.from(item.children).forEach((nested) => {
        if (nested.tagName === 'UL' || nested.tagName === 'OL') walkList(nested, level + 1);
      });
    });
  };
  Array.from(holder.children).forEach((child) => {
    if (child.tagName === 'UL' || child.tagName === 'OL') walkList(child, 0);
    else addParagraph(child, { level: 0 });
  });
  if (!paragraphs.length) return htmlText(value);

  const out = [];
  paragraphs.forEach((paragraph, index) => {
    const last = index === paragraphs.length - 1;
    paragraph.runs.forEach((run, runIndex) => {
      const first = runIndex === 0;
      const options = {
        ...(run.format.bold ? { bold: true } : {}),
        ...(run.format.italic ? { italic: true } : {}),
        ...(run.format.underline ? { underline: true } : {}),
        ...(run.format.color ? { color: run.format.color } : {}),
        ...(run.format.fontSize ? { fontSize: run.format.fontSize } : {}),
        ...(run.format.fontFace ? { fontFace: run.format.fontFace } : {}),
        ...(run.format.charSpacing ? { charSpacing: run.format.charSpacing } : {}),
        ...(['center', 'right', 'justify'].includes(paragraph.align) ? { align: paragraph.align } : {}),
        // pptxgenjs has no left indent for plain text: a blank bullet with a hanging indent is one.
        ...(first && (paragraph.bullet || paragraph.marginLeft > 2)
          ? { bullet: paragraph.bullet || { characterCode: '0020', indent: Math.round(paragraph.marginLeft) } } : {}),
        ...(first && paragraph.spaceBefore ? { paraSpaceBefore: paragraph.spaceBefore } : {}),
        ...(first && paragraph.spaceAfter ? { paraSpaceAfter: paragraph.spaceAfter } : {}),
        ...(first && paragraph.level ? { indentLevel: paragraph.level } : {}),
        ...(run.lineBreak && !first ? { softBreakBefore: true } : {}),
        breakLine: runIndex === paragraph.runs.length - 1 && !last,
      };
      if (run.lineBreak) {
        out.push({ text: ' ', options: { ...options, softBreakBefore: true } });
      } else {
        out.push({ text: run.text, options });
      }
    });
  });
  return out;
}

async function imageData(projectId, element, cache) {
  const source = element.src || element.storageUrl;
  if (!source) return null;
  if (source.startsWith('data:')) return source;
  if (!cache.has(source)) {
    cache.set(source, projectService.getProjectImage(projectId, source).then(blobToDataUrl));
  }
  return cache.get(source);
}

// Shapes placed by the user (and template ornaments) become native PowerPoint shapes, so they
// stay editable there; icons have no native equivalent and go in as pictures.
async function addShapeElement(pptx, pptxSlide, element, activeTheme) {
  const { info, path: shapePath, dash, fill, borderColor, borderWidth, opacity } = resolveShape(element);
  const x = toInches(element.x);
  const y = toInches(element.y);
  const w = Math.max(0.01, toInches(element.width));
  const h = Math.max(0.01, toInches(element.height));
  const rotate = Number(element.rotation) || 0;
  const hasBorder = borderColor !== 'transparent' && borderWidth > 0;
  const transparency = Math.round((1 - opacity) * 100);

  if (info.kind === 'dots') {
    pptxSlide.addImage({ data: dotsToPng(fill, element.width, element.height), x, y, w, h, rotate, transparency });
    return;
  }
  if (info.kind === 'glow') {
    // A soft radial disc has no PowerPoint equivalent; a faint ellipse is the closest editable stand-in.
    pptxSlide.addShape(pptx.ShapeType.ellipse, {
      x, y, w, h, rotate,
      line: { color: 'FFFFFF', transparency: 100 },
      fill: { color: cleanColor(fill, activeTheme.bg), transparency: Math.round((1 - opacity * 0.45) * 100) },
    });
    return;
  }
  if (info.kind === 'path' && shapePath) {
    pptxSlide.addShape(pptx.ShapeType.custGeom, {
      x, y, w, h, rotate,
      points: pathToPoints(shapePath, w, h),
      line: hasBorder ? { color: cleanColor(borderColor), width: borderWidth, transparency, ...(dash ? { dashType: dash === 'dot' ? 'sysDot' : 'dash' } : {}) } : { color: 'FFFFFF', transparency: 100 },
      fill: fill === 'transparent' ? { color: 'FFFFFF', transparency: 100 } : { color: cleanColor(fill, activeTheme.bg), transparency },
    });
    return;
  }
  if (info.kind === 'polygon' && !info.pptx) {
    pptxSlide.addShape(pptx.ShapeType.custGeom, {
      x, y, w, h, rotate,
      points: [
        ...info.points.map(([px, py], index) => ({ x: (px / 100) * w, y: (py / 100) * h, moveTo: index === 0 })),
        { close: true },
      ],
      line: hasBorder ? { color: cleanColor(borderColor), width: borderWidth, transparency } : { color: 'FFFFFF', transparency: 100 },
      fill: fill === 'transparent' ? { color: 'FFFFFF', transparency: 100 } : { color: cleanColor(fill, activeTheme.bg), transparency },
    });
    return;
  }

  if (info.kind === 'line') {
    pptxSlide.addShape(pptx.ShapeType.line, {
      x, y: y + h / 2, w, h: 0, rotate,
      line: {
        color: cleanColor(hasBorder ? borderColor : fill, activeTheme.accent),
        width: Math.max(0.5, borderWidth || 4),
        transparency,
        ...(dash ? { dashType: dash === 'dot' ? 'sysDot' : 'dash' } : {}),
      },
    });
    return;
  }

  const noFill = fill === 'transparent';
  pptxSlide.addShape(pptx.ShapeType[info.pptx] || pptx.ShapeType.rect, {
    x, y, w, h, rotate,
    rectRadius: info.id === 'roundRect' ? Math.min(0.3, Math.min(w, h) * 0.14) : undefined,
    line: hasBorder
      ? { color: cleanColor(borderColor), width: borderWidth, transparency }
      : { color: 'FFFFFF', transparency: 100 },
    fill: noFill
      ? { color: 'FFFFFF', transparency: 100 }
      : { color: cleanColor(fill, activeTheme.bg), transparency },
  });
}

// A picture or plain shape from an uploaded template (crop, flip and rounding baked into the PNG).
async function addArtItem(pptx, pptxSlide, item, activeTheme) {
  const x = toInches(item.x);
  const y = toInches(item.y);
  const w = Math.max(0.01, toInches(item.width));
  const h = Math.max(0.01, toInches(item.height));
  const rotate = Number(item.rotation) || 0;
  const transparency = Math.round((1 - Math.min(1, Math.max(0, Number(item.opacity ?? 1)))) * 100);
  if (item.type === 'image') {
    const data = await artImageToPng(item, item.width, item.height);
    if (data) pptxSlide.addImage({ data, x, y, w, h, rotate, transparency });
    return;
  }
  if (item.style?.shape || item.style?.path) {
    // A template shape the editor knows (triangle, star, arrow, outline…) exports as that native shape.
    await addShapeElement(pptx, pptxSlide, {
      shape: item.style.path ? 'path' : item.style.shape, path: item.style.path, dash: item.style.dash, fill: item.fill, borderColor: item.borderColor, borderWidth: item.style.borderWidth,
      opacity: item.opacity ?? 1, x: item.x, y: item.y, width: item.width, height: item.height, rotation: item.rotation,
    }, activeTheme);
    return;
  }
  // Gradients cannot be a native fill; use the first colour they contain.
  const colour = String(item.fill || '').match(/#[0-9a-f]{6}/i)?.[0];
  if (!colour) return;
  const round = String(item.style?.borderRadius || '').includes('50%');
  pptxSlide.addShape(round ? pptx.ShapeType.ellipse : pptx.ShapeType.rect, {
    x, y, w, h, rotate,
    line: { color: 'FFFFFF', transparency: 100 },
    fill: { color: cleanColor(colour, activeTheme.bg), transparency: Math.max(transparency, 60) },
  });
}

async function addIconElement(pptxSlide, element) {
  const Icon = ICON_COMPONENTS[element.icon];
  if (!Icon) return;
  const data = await iconToPng(Icon, { color: element.color || '#6c63ff', strokeWidth: Number(element.strokeWidth) || 2 });
  pptxSlide.addImage({
    data,
    x: toInches(element.x),
    y: toInches(element.y),
    w: Math.max(0.1, toInches(element.width)),
    h: Math.max(0.1, toInches(element.height)),
    rotate: Number(element.rotation) || 0,
    transparency: Math.round((1 - Math.min(1, Math.max(0, Number(element.opacity ?? 1)))) * 100),
  });
}

// Title treatments are CSS pseudo-elements on the canvas; rebuild them as real
// shapes so the exported slide keeps the band/underline the text was designed on.
function addDecor(pptxSlide, element) {
  const accent = cleanColor(element.style?.['--decor-accent'], '');
  if (!element.decor || !accent) return;
  const x = toInches(element.x);
  const y = toInches(element.y);
  const w = Math.max(0.1, toInches(element.width));
  const h = Math.max(0.1, toInches(element.height));
  const fill = { color: accent };
  const line = { color: accent, width: 0 };
  if (element.decor === 'band') {
    pptxSlide.addShape('roundRect', { x, y, w, h, fill, line, rectRadius: 0.12 });
  } else if (element.decor === 'underline') {
    pptxSlide.addShape('rect', { x: x + 0.05, y: y + h - 0.07, w: 0.9, h: 0.055, fill, line });
  } else if (element.decor === 'underline-center') {
    pptxSlide.addShape('rect', { x: x + (w - 0.9) / 2, y: y + h - 0.07, w: 0.9, h: 0.055, fill, line });
  } else if (element.decor === 'rule-left') {
    pptxSlide.addShape('rect', { x: x + 0.05, y: y + 0.08, w: 0.045, h: Math.max(0.1, h - 0.16), fill, line });
  }
}

// "3.6px 7.2px 3.6px 7.2px" (top right bottom left) as pptxgenjs's [left, right, bottom, top] points.
function boxMargin(padding) {
  const parts = String(padding || '').split(/\s+/).map((part) => parseFloat(part)).filter(Number.isFinite);
  if (!parts.length) return 0;
  const [top, right = top, bottom = top, left = right] = parts;
  return [left, right, bottom, top];
}

function boxLook(style) {
  const look = {};
  const fill = cssHex(style.background);
  if (fill) look.fill = { color: fill };
  const border = String(style.border || '').match(/^([\d.]+)px\s+(\w+)\s+(#[0-9a-f]{3,6})/i);
  if (border && cssHex(border[3])) {
    look.line = { color: cssHex(border[3]), width: Math.max(0.5, parseFloat(border[1])), ...(border[2] === 'dashed' ? { dashType: 'dash' } : {}) };
  }
  if (look.fill || look.line) {
    look.shape = style.borderRadius === '50%' ? 'ellipse' : parseFloat(style.borderRadius) > 0 ? 'roundRect' : 'rect';
    if (look.shape === 'roundRect') look.rectRadius = 0.12;
  }
  return look;
}

function addEditableText(pptxSlide, element, theme) {
  addDecor(pptxSlide, element);
  const style = element.style || {};
  const content = textRuns(element.content);
  pptxSlide.addText(content, {
    ...boxLook(style),
    x: toInches(element.x),
    y: toInches(element.y),
    w: Math.max(0.1, toInches(element.width)),
    h: Math.max(0.1, toInches(element.height)),
    fontFace: cleanFont(style.fontFamily),
    fontSize: Math.max(5, Number(style.fontSize) || 16),
    color: cleanColor(style.color, element.role === 'body' ? theme.textSub : theme.text),
    bold: Number(style.fontWeight) >= 600 || style.fontWeight === 'bold',
    italic: style.fontStyle === 'italic',
    underline: style.textDecoration?.includes('underline'),
    align: ['center', 'right', 'justify'].includes(style.textAlign) ? style.textAlign : 'left',
    valign: { top: 'top', middle: 'mid', bottom: 'bottom' }[style.verticalAlign] || 'top',
    breakLine: false,
    margin: boxMargin(style.padding),
    ...(style.whiteSpace === 'nowrap' ? { wrap: false } : {}),
    ...(parseFloat(style.letterSpacing) ? { charSpacing: parseFloat(style.letterSpacing) } : {}),
    fit: 'shrink',
    rotate: Number(element.rotation) || 0,
    lineSpacingMultiple: Math.max(0.7, Number(style.lineHeight) || 1.2),
    transparency: 0,
  });
}

function addEditableTable(pptxSlide, element, slideData, theme) {
  const table = element.data || slideData.table || {};
  const headers = Array.isArray(table.headers) ? table.headers : [];
  const rows = Array.isArray(table.rows) ? table.rows : [];
  if (!headers.length) return;

  const headerStyles = Array.isArray(table.headerStyles) ? table.headerStyles : [];
  const cellStyles = Array.isArray(table.cellStyles) ? table.cellStyles : [];
  const tableRows = [
    headers.map((value, index) => ({
      text: String(value ?? ''),
      options: {
        bold: headerStyles[index]?.fontWeight ? Number(headerStyles[index].fontWeight) >= 600 : true,
        italic: headerStyles[index]?.fontStyle === 'italic',
        color: cleanColor(headerStyles[index]?.color, theme.text),
        fill: cleanColor(headerStyles[index]?.background, theme.surface),
        align: headerStyles[index]?.textAlign || 'center',
        valign: { top: 'top', middle: 'mid', bottom: 'bottom' }[headerStyles[index]?.verticalAlign] || 'mid',
        ...(headerStyles[index]?.fontSize ? { fontSize: Number(headerStyles[index].fontSize) } : {}),
        ...(headerStyles[index]?.fontFamily ? { fontFace: cleanFont(headerStyles[index].fontFamily) } : {}),
      },
    })),
    ...rows.map((row, rowIndex) => headers.map((_, colIndex) => {
      const style = cellStyles[rowIndex]?.[colIndex] || {};
      return {
        text: String(row?.[colIndex] ?? ''),
        options: {
          color: cleanColor(style.color, theme.textSub),
          fill: cleanColor(style.background, theme.bg),
          bold: Number(style.fontWeight) >= 600,
          italic: style.fontStyle === 'italic',
          align: style.textAlign || 'left',
          valign: { top: 'top', middle: 'mid', bottom: 'bottom' }[style.verticalAlign] || 'mid',
          ...(style.fontSize ? { fontSize: Number(style.fontSize) } : {}),
          ...(style.fontFamily ? { fontFace: cleanFont(style.fontFamily) } : {}),
        },
      };
    })),
  ];
  const width = Math.max(0.5, toInches(element.width));
  const rawWidths = Array.isArray(table.columnWidths) && table.columnWidths.length === headers.length
    ? table.columnWidths.map((value) => Math.max(1, Number(value) || 1))
    : headers.map(() => 1);
  const widthTotal = rawWidths.reduce((sum, value) => sum + value, 0);
  const height = Math.max(0.4, toInches(element.height));
  const rawHeights = Array.isArray(table.rowHeights) && table.rowHeights.length === rows.length + 1
    ? table.rowHeights.map((value) => Math.max(1, Number(value) || 1))
    : null;
  const heightTotal = rawHeights ? rawHeights.reduce((sum, value) => sum + value, 0) : 0;

  pptxSlide.addTable(tableRows, {
    x: toInches(element.x),
    y: toInches(element.y),
    w: width,
    h: height,
    colW: rawWidths.map((value) => width * value / widthTotal),
    ...(rawHeights ? { rowH: rawHeights.map((value) => height * value / heightTotal) } : {}),
    border: { type: 'solid', color: cleanColor(theme.textSub), pt: 0.6, transparency: 65 },
    fontFace: 'Arial',
    fontSize: 9,
    color: theme.text,
    margin: rawHeights ? 0.03 : 0.06,
    autoFit: false,
    valign: 'mid',
  });
}

function chartType(pptx, value) {
  const type = String(value || 'bar').toLowerCase();
  if (type.includes('pie')) return pptx.ChartType.pie;
  if (type.includes('doughnut') || type.includes('donut')) return pptx.ChartType.doughnut;
  if (type.includes('line')) return pptx.ChartType.line;
  if (type.includes('area')) return pptx.ChartType.area;
  if (type.includes('radar')) return pptx.ChartType.radar;
  return pptx.ChartType.bar;
}

function addEditableChart(pptx, pptxSlide, element, slideData, theme) {
  const chart = element.data || slideData.chart || {};
  const labels = (chart.labels || chart.categories || []).map(String);
  const rawSeries = Array.isArray(chart.series) && chart.series.length
    ? chart.series
    : [{ name: chart.title || 'Data', values: chart.values || [] }];
  if (!labels.length || !rawSeries.length) return;

  const series = rawSeries.map((item, index) => ({
    name: item?.name || `Series ${index + 1}`,
    labels,
    values: (item?.values || item?.data || []).map((value) => Number(value) || 0),
  }));
  const type = chartType(pptx, chart.chart_type || chart.type);
  pptxSlide.addChart(type, series, {
    x: toInches(element.x),
    y: toInches(element.y),
    w: Math.max(0.5, toInches(element.width)),
    h: Math.max(0.5, toInches(element.height)),
    showTitle: Boolean(chart.title),
    title: chart.title || '',
    showLegend: series.length > 1 || type === pptx.ChartType.pie || type === pptx.ChartType.doughnut,
    showValue: true,
    showCategoryName: type === pptx.ChartType.pie || type === pptx.ChartType.doughnut,
    catAxisLabelColor: theme.textSub,
    valAxisLabelColor: theme.textSub,
    chartColors: ['14B8A6', '6366F1', 'F59E0B', 'EC4899', '22C55E', '38BDF8'],
    showCatName: true,
    showPercent: type === pptx.ChartType.pie || type === pptx.ChartType.doughnut,
    border: { color: cleanColor(theme.textSub), transparency: 70, pt: 0.5 },
  });
}

// pptxgenjs writes a paragraph-properties block in front of every run of a paragraph, but the file
// format allows one, first. Several runs in one paragraph (a bold word, a coloured one) made files
// PowerPoint would offer to repair, so only the first block of each paragraph is kept.
export async function withSingleParagraphProperties(bytes) {
  const zip = await JSZip.loadAsync(bytes);
  const blocks = /<a:pPr(?=[\s>/])[^>]*?(?:\/>|>[\s\S]*?<\/a:pPr>)/g;
  await Promise.all(Object.keys(zip.files)
    .filter((name) => /^ppt\/(slides|notesSlides)\/[^/]+\.xml$/.test(name))
    .map(async (name) => {
      const xml = await zip.file(name).async('string');
      const fixed = xml.replace(/<a:p>[\s\S]*?<\/a:p>/g, (paragraph) => {
        let seen = false;
        return paragraph.replace(blocks, (block) => {
          if (!seen) { seen = true; return block; }
          return '';
        });
      });
      if (fixed !== xml) zip.file(name, fixed);
    }));
  return zip.generateAsync({ type: 'blob', mimeType: 'application/vnd.openxmlformats-officedocument.presentationml.presentation', compression: 'DEFLATE' });
}

export async function exportEditablePptx({ slides, theme = 'clean-white', fileName = 'presentation', projectId }) {
  const pptx = new PptxGenJS();
  pptx.defineLayout({ name: 'GENSLIDE_WIDE', width: SLIDE_W, height: SLIDE_H });
  pptx.layout = 'GENSLIDE_WIDE';
  pptx.author = 'LecGen';
  pptx.subject = 'Editable AI presentation';
  pptx.title = fileName;
  pptx.company = 'LecGen';
  pptx.lang = 'vi-VN';
  pptx.theme = {
    headFontFace: 'Arial',
    bodyFontFace: 'Arial',
    lang: 'vi-VN',
  };

  const activeTheme = THEMES[theme] || THEMES['clean-white'];
  const imageCache = new Map();

  for (let index = 0; index < slides.length; index += 1) {
    const sourceSlide = slides[index];
    const elements = Array.isArray(sourceSlide.elements) && sourceSlide.elements.length
      ? sourceSlide.elements
      : createElementsFromSlide(sourceSlide, theme);
    const pptxSlide = pptx.addSlide();
    pptxSlide.background = { color: activeTheme.bg };
    // An uploaded template brings its own page colour, pictures and ornaments.
    const templateArt = Array.isArray(sourceSlide.richText?._decor) ? sourceSlide.richText._decor : [];
    if (sourceSlide.richText?._tplBg) pptxSlide.background = { color: cleanColor(sourceSlide.richText._tplBg, activeTheme.bg) };
    if (!templateArt.length) {
      pptxSlide.addShape(pptx.ShapeType.rect, {
        x: 0.65, y: 0.55, w: 0.07, h: 0.55,
        line: { color: activeTheme.accent, transparency: 100 },
        fill: { color: activeTheme.accent },
      });
    }
    // The theme's own decoration, drawn as real shapes unless it already lives on the slide as elements.
    const themeItems = hasOwnOrnaments(sourceSlide) ? [] : themeOrnaments(theme);
    for (const ornament of themeItems) await addShapeElement(pptx, pptxSlide, ornament, activeTheme);
    const shownArt = sourceSlide.richText?._noOrnaments ? templateArt.filter(isBackdrop) : templateArt;
    for (const item of shownArt) {
      if (item.role === 'background' && item.type !== 'image') continue;
      await addArtItem(pptx, pptxSlide, item, activeTheme);
    }

    for (const element of elements) {
      if (element.type === 'text') {
        addEditableText(pptxSlide, element, activeTheme);
      } else if (element.type === 'image') {
        const data = await imageData(projectId, element, imageCache);
        if (data) {
          pptxSlide.addImage({
            data,
            x: toInches(element.x),
            y: toInches(element.y),
            w: Math.max(0.1, toInches(element.width)),
            h: Math.max(0.1, toInches(element.height)),
            rotate: Number(element.rotation) || 0,
            sizing: {
              type: element.objectFit === 'contain' ? 'contain' : 'cover',
              w: Math.max(0.1, toInches(element.width)),
              h: Math.max(0.1, toInches(element.height)),
            },
          });
        }
      } else if (element.type === 'table') {
        addEditableTable(pptxSlide, element, sourceSlide, activeTheme);
      } else if (element.type === 'chart') {
        addEditableChart(pptx, pptxSlide, element, sourceSlide, activeTheme);
      } else if (element.type === 'shape') {
        await addShapeElement(pptx, pptxSlide, element, activeTheme);
      } else if (element.type === 'art') {
        await addArtItem(pptx, pptxSlide, {
          type: element.artType, src: element.src, fill: element.fill, style: element.style,
          x: element.x, y: element.y, width: element.width, height: element.height,
          rotation: element.rotation, opacity: element.opacity,
        }, activeTheme);
      } else if (element.type === 'icon') {
        await addIconElement(pptxSlide, element);
      }
    }

    const notes = String(sourceSlide.notes || sourceSlide.script || '').trim();
    if (notes) pptxSlide.addNotes(notes);
  }

  const bytes = await pptx.write({ outputType: 'arraybuffer', compression: true });
  const blob = await withSingleParagraphProperties(bytes);
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = `${safeFileName(fileName)}_editable.pptx`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(link.href), 10_000);
}
