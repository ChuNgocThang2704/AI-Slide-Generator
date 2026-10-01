import PptxGenJS from 'pptxgenjs';
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

function htmlText(value) {
  const holder = document.createElement('div');
  holder.innerHTML = String(value || '');
  return (holder.innerText || holder.textContent || '').replace(/\u00a0/g, ' ').trim();
}

function textRuns(value) {
  const holder = document.createElement('div');
  holder.innerHTML = String(value || '');
  const listItems = Array.from(holder.querySelectorAll('li'));
  if (listItems.length) {
    const ordered = Boolean(listItems[0]?.closest('ol'));
    return listItems.map((item, index) => ({
      text: (item.innerText || item.textContent || '').trim(),
      options: {
        bullet: ordered ? { type: 'ul', startAt: index + 1 } : { type: 'ul' },
        breakLine: index < listItems.length - 1,
      },
    }));
  }
  return htmlText(value);
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
  const { info, fill, borderColor, borderWidth, opacity } = resolveShape(element);
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
      line: { color: cleanColor(hasBorder ? borderColor : fill, activeTheme.accent), width: Math.max(0.5, borderWidth || 4), transparency },
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
  if (item.style?.shape) {
    // A template shape the editor knows (triangle, star, arrow, outline…) exports as that native shape.
    await addShapeElement(pptx, pptxSlide, {
      shape: item.style.shape, fill: item.fill, borderColor: item.borderColor, borderWidth: item.style.borderWidth,
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

function addEditableText(pptxSlide, element, theme) {
  addDecor(pptxSlide, element);
  const style = element.style || {};
  const content = textRuns(element.content);
  pptxSlide.addText(content, {
    x: toInches(element.x),
    y: toInches(element.y),
    w: Math.max(0.1, toInches(element.width)),
    h: Math.max(0.1, toInches(element.height)),
    fontFace: cleanFont(style.fontFamily),
    fontSize: Math.max(5, (Number(style.fontSize) || 16) * 0.75),
    color: cleanColor(style.color, element.role === 'body' ? theme.textSub : theme.text),
    bold: Number(style.fontWeight) >= 600 || style.fontWeight === 'bold',
    italic: style.fontStyle === 'italic',
    underline: style.textDecoration?.includes('underline'),
    align: ['center', 'right', 'justify'].includes(style.textAlign) ? style.textAlign : 'left',
    valign: { top: 'top', middle: 'mid', bottom: 'bottom' }[style.verticalAlign] || 'top',
    breakLine: false,
    margin: 0,
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
        bold: true,
        color: cleanColor(headerStyles[index]?.color, theme.text),
        fill: cleanColor(headerStyles[index]?.background, theme.surface),
        align: headerStyles[index]?.textAlign || 'center',
        valign: 'mid',
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
        },
      };
    })),
  ];
  const width = Math.max(0.5, toInches(element.width));
  const rawWidths = Array.isArray(table.columnWidths) && table.columnWidths.length === headers.length
    ? table.columnWidths.map((value) => Math.max(1, Number(value) || 1))
    : headers.map(() => 1);
  const widthTotal = rawWidths.reduce((sum, value) => sum + value, 0);

  pptxSlide.addTable(tableRows, {
    x: toInches(element.x),
    y: toInches(element.y),
    w: width,
    h: Math.max(0.4, toInches(element.height)),
    colW: rawWidths.map((value) => width * value / widthTotal),
    border: { type: 'solid', color: cleanColor(theme.textSub), pt: 0.6, transparency: 65 },
    fontFace: 'Arial',
    fontSize: 9,
    color: theme.text,
    margin: 0.06,
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

  await pptx.writeFile({ fileName: `${safeFileName(fileName)}_editable.pptx`, compression: true });
}
