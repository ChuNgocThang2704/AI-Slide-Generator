import PptxGenJS from 'pptxgenjs';
import { projectService } from './documentService';
import { createElementsFromSlide } from '../utils/slideElements';

const PX_PER_INCH = 72;
const SLIDE_W = 13.333333;
const SLIDE_H = 7.5;

const THEMES = {
  'soft-blue': { bg: 'F8FBFF', accent: '3B96D2', text: '0B2E4A', textSub: '4A6A85', surface: 'EAF4FC' },
  'royal-purple': { bg: '0B0518', accent: 'ED7D31', text: 'FFFFFF', textSub: 'C0A8E0', surface: '241336' },
  'clean-white': { bg: 'FFFFFF', accent: '4F46E5', text: '1A1A1A', textSub: '555555', surface: 'F5F5F5' },
  'modern-dark': { bg: '0D0D1A', accent: 'FF6584', text: 'FFFFFF', textSub: 'C7C7D8', surface: '24243B' },
  'playful-yellow': { bg: 'FFFCF0', accent: '8B5CF6', text: '2E1E0A', textSub: '654A22', surface: 'FFF4D6' },
  'gradient-border': { bg: 'F8FAFC', accent: '38BDF8', text: '0F172A', textSub: '475569', surface: 'F1F5F9' },
  'blue-planet': { bg: '02001A', accent: '4FACFE', text: 'FFFFFF', textSub: 'C8D3FF', surface: '11164A' },
  'nature-green': { bg: '0A2318', accent: '2ECC71', text: 'E8F5E2', textSub: 'BFD9B8', surface: '173B2A' },
  'tech-purple': { bg: '0A0015', accent: 'E056FD', text: 'FFFFFF', textSub: 'D9B8E8', surface: '1E0A2E' },
};

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

function addEditableText(pptxSlide, element, theme) {
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
  pptx.author = 'PSlideAI';
  pptx.subject = 'Editable AI presentation';
  pptx.title = fileName;
  pptx.company = 'PSlideAI';
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
    pptxSlide.addShape(pptx.ShapeType.rect, {
      x: 0.65, y: 0.55, w: 0.07, h: 0.55,
      line: { color: activeTheme.accent, transparency: 100 },
      fill: { color: activeTheme.accent },
    });

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
      }
    }

    pptxSlide.addText(String(index + 1).padStart(2, '0'), {
      x: 12.2, y: 7.0, w: 0.55, h: 0.22,
      fontFace: 'Arial', fontSize: 8, color: activeTheme.textSub,
      align: 'right', margin: 0,
    });
    const notes = String(sourceSlide.notes || sourceSlide.script || '').trim();
    if (notes) pptxSlide.addNotes(notes);
  }

  await pptx.writeFile({ fileName: `${safeFileName(fileName)}_editable.pptx`, compression: true });
}
