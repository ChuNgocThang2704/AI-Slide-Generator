import { resolveAssetUrl } from '../utils/assetUrl.js';
import { documentService } from './documentService.js';

const SLIDE_W = 13.333333;
const SLIDE_H = 7.5;
const EMU_PER_IN = 914400;

const THEMES = {
  'soft-blue': { bg: 'F8FBFF', primary: '0D5099', accent: '3B96D2', text: '0B2E4A', textSub: '4A6A85', surface: 'EAF4FC' },
  'royal-purple': { bg: '0B0518', primary: '9948FF', accent: 'ED7D31', text: 'FFFFFF', textSub: 'C0A8E0', surface: '241336' },
  'clean-white': { bg: 'FFFFFF', primary: '2D2D2D', accent: '4F46E5', text: '1A1A1A', textSub: '555555', surface: 'F5F5F5' },
  'modern-dark': { bg: '0D0D1A', primary: '6C63FF', accent: 'FF6584', text: 'FFFFFF', textSub: 'C7C7D8', surface: '24243B' },
  'playful-yellow': { bg: 'FFFCF0', primary: 'F59E0B', accent: '8B5CF6', text: '2E1E0A', textSub: '654A22', surface: 'FFF4D6' },
  'gradient-border': { bg: 'F8FAFC', primary: '6C63FF', accent: '38BDF8', text: '0F172A', textSub: '475569', surface: 'F1F5F9' },
  'blue-planet': { bg: '02001A', primary: '00F2FE', accent: '4FACFE', text: 'FFFFFF', textSub: 'C8D3FF', surface: '11164A' },
  'nature-green': { bg: '0A2318', primary: '27AE60', accent: '2ECC71', text: 'E8F5E2', textSub: 'BFD9B8', surface: '173B2A' },
  'tech-purple': { bg: '0A0015', primary: '9B59B6', accent: 'E056FD', text: 'FFFFFF', textSub: 'D9B8E8', surface: '1E0A2E' },
};

const relTypes = {
  officeDocument: 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument',
  slide: 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide',
  slideLayout: 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout',
  slideMaster: 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster',
  notesSlide: 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesSlide',
  notesMaster: 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesMaster',
  theme: 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme',
  image: 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/image',
};

function xmlEscape(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

function safeFileName(value) {
  return String(value || 'presentation')
    .replace(/[\\/:*?"<>|]+/g, '')
    .replace(/\s+/g, '_')
    .slice(0, 80) || 'presentation';
}

function emu(inches) {
  return Math.round(inches * EMU_PER_IN);
}

function color(hex) {
  return String(hex || '000000').replace('#', '').slice(0, 6).toUpperCase().padEnd(6, '0');
}

function solidFill(hex) {
  return `<a:solidFill><a:srgbClr val="${color(hex)}"/></a:solidFill>`;
}

function shape(id, name, x, y, w, h, fill, line = fill, radius = 'rect') {
  const lineXml = line ? `<a:ln>${solidFill(line)}</a:ln>` : '<a:ln><a:noFill/></a:ln>';
  return `<p:sp><p:nvSpPr><p:cNvPr id="${id}" name="${xmlEscape(name)}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr><a:xfrm><a:off x="${emu(x)}" y="${emu(y)}"/><a:ext cx="${emu(w)}" cy="${emu(h)}"/></a:xfrm><a:prstGeom prst="${radius}"><a:avLst/></a:prstGeom>${solidFill(fill)}${lineXml}</p:spPr></p:sp>`;
}

function run(text, size, hex, opts = {}) {
  const bold = opts.bold ? ' b="1"' : '';
  const italic = opts.italic ? ' i="1"' : '';
  return `<a:r><a:rPr lang="vi-VN" sz="${Math.round(size * 100)}"${bold}${italic}>${solidFill(hex)}<a:latin typeface="${xmlEscape(opts.font || 'Arial')}"/><a:cs typeface="${xmlEscape(opts.font || 'Arial')}"/></a:rPr><a:t>${xmlEscape(text)}</a:t></a:r>`;
}

function paragraph(text, opts = {}) {
  const align = opts.align ? ` algn="${opts.align}"` : '';
  const bullet = opts.bullet ? '<a:buChar char="•"/>' : '';
  const marL = opts.bullet ? ' marL="285750" indent="-171450"' : '';
  return `<a:p><a:pPr${align}${marL}>${bullet}<a:defRPr sz="${Math.round((opts.size || 16) * 100)}"/></a:pPr>${run(text, opts.size || 16, opts.color || '000000', opts)}<a:endParaRPr lang="vi-VN"/></a:p>`;
}

function textBox(id, name, x, y, w, h, paragraphs, opts = {}) {
  const valign = opts.valign ? ` anchor="${opts.valign}"` : '';
  const margin = opts.margin == null ? 91440 : Math.round(opts.margin);
  const fillXml = opts.fill ? solidFill(opts.fill) : '<a:noFill/>';
  const lineXml = opts.line ? `<a:ln>${solidFill(opts.line)}</a:ln>` : '<a:ln><a:noFill/></a:ln>';
  const rotation = Number(opts.rotation) ? ` rot="${Math.round(Number(opts.rotation) * 60000)}"` : '';
  return `<p:sp><p:nvSpPr><p:cNvPr id="${id}" name="${xmlEscape(name)}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr><p:spPr><a:xfrm${rotation}><a:off x="${emu(x)}" y="${emu(y)}"/><a:ext cx="${emu(w)}" cy="${emu(h)}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom>${fillXml}${lineXml}</p:spPr><p:txBody><a:bodyPr wrap="square"${valign} lIns="${margin}" tIns="${margin}" rIns="${margin}" bIns="${margin}"/><a:lstStyle/>${paragraphs.join('')}</p:txBody></p:sp>`;
}

function imagePic(id, name, relId, x, y, w, h, opts = {}) {
  const rotation = Number(opts.rotation) ? ` rot="${Math.round(Number(opts.rotation) * 60000)}"` : '';
  const sourceRect = opts.crop
    ? `<a:srcRect l="${Math.round(opts.crop.left * 1000)}" t="${Math.round(opts.crop.top * 1000)}" r="${Math.round(opts.crop.right * 1000)}" b="${Math.round(opts.crop.bottom * 1000)}"/>`
    : '';
  return `<p:pic><p:nvPicPr><p:cNvPr id="${id}" name="${xmlEscape(name)}"/><p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr><p:blipFill><a:blip r:embed="${relId}"/>${sourceRect}<a:stretch><a:fillRect/></a:stretch></p:blipFill><p:spPr><a:xfrm${rotation}><a:off x="${emu(x)}" y="${emu(y)}"/><a:ext cx="${emu(w)}" cy="${emu(h)}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>`;
}

function imagePlacement(element, imageRef, x, y, w, h) {
  const imageWidth = Number(imageRef?.width || 0);
  const imageHeight = Number(imageRef?.height || 0);
  if (!imageWidth || !imageHeight || !w || !h) return { x, y, w, h };
  const imageAspect = imageWidth / imageHeight;
  const frameAspect = w / h;
  const positionX = clampPercent(element.objectPositionX ?? 50) / 100;
  const positionY = clampPercent(element.objectPositionY ?? 50) / 100;

  if (element.objectFit === 'contain') {
    if (imageAspect > frameAspect) {
      const fittedHeight = w / imageAspect;
      return { x, y: y + (h - fittedHeight) * positionY, w, h: fittedHeight };
    }
    const fittedWidth = h * imageAspect;
    return { x: x + (w - fittedWidth) * positionX, y, w: fittedWidth, h };
  }

  if (imageAspect > frameAspect) {
    const totalCrop = (1 - frameAspect / imageAspect) * 100;
    return { x, y, w, h, crop: { left: totalCrop * positionX, right: totalCrop * (1 - positionX), top: 0, bottom: 0 } };
  }
  const totalCrop = (1 - imageAspect / frameAspect) * 100;
  return { x, y, w, h, crop: { left: 0, right: 0, top: totalCrop * positionY, bottom: totalCrop * (1 - positionY) } };
}

function clampPercent(value) {
  return Math.min(100, Math.max(0, Number(value) || 0));
}

async function readImage(imageSource) {
  const imageUrl = typeof imageSource === 'string' ? imageSource : imageSource?.src;
  if (!imageUrl) return null;
  try {
    let urlToFetch = resolveAssetUrl(imageUrl);
    let response = await fetch(urlToFetch);
    if (!response.ok && typeof imageSource === 'object' && (imageSource.assetId || imageSource.storageUrl)) {
      urlToFetch = imageSource.assetId
        ? await documentService.getViewUrl(imageSource.assetId)
        : await documentService.getViewUrlByStorageUrl(imageSource.storageUrl);
      response = await fetch(urlToFetch);
    }
    if (!response.ok) return null;
    const blob = await response.blob();
    const buffer = new Uint8Array(await blob.arrayBuffer());
    const mime = blob.type || 'image/png';
    const ext = mime.includes('jpeg') || mime.includes('jpg') ? 'jpg' : mime.includes('webp') ? 'webp' : 'png';
    let width = 0;
    let height = 0;
    try {
      const bitmap = await createImageBitmap(blob);
      width = bitmap.width;
      height = bitmap.height;
      bitmap.close();
    } catch {
      // Dimensions are optional; export can still use the original frame.
    }
    return { buffer, ext, mime, width, height };
  } catch {
    return null;
  }
}

function buildSlideShapes(slide, index, theme, imageRefs = []) {
  const t = THEMES[theme] || THEMES['clean-white'];
  const shapes = [shape(2, 'Background', 0, 0, SLIDE_W, SLIDE_H, t.bg, t.bg)];
  const number = String(index + 1).padStart(2, '0');
  let nextId = 10;

  shapes.push(shape(nextId++, 'Accent', 0.65, 0.55, 0.08, 0.55, t.accent, t.accent));

  if (Array.isArray(slide.elements) && slide.elements.length) {
    slide.elements.forEach((element) => {
      const x = Number(element.x || 0) / 72;
      const y = Number(element.y || 0) / 72;
      const w = Number(element.width || 100) / 72;
      const h = Number(element.height || 40) / 72;
      if (element.type === 'image') {
        const imageElementIndex = slide.elements.filter((item) => item.type === 'image').findIndex((item) => item.id === element.id);
        const imageRef = imageRefs[imageElementIndex];
        if (imageRef?.relId) {
          const placement = imagePlacement(element, imageRef, x, y, w, h);
          shapes.push(imagePic(nextId++, 'Canvas image', imageRef.relId, placement.x, placement.y, placement.w, placement.h, { rotation: element.rotation, crop: placement.crop }));
        }
        return;
      }
      if (element.type !== 'text') return;
      const holder = document.createElement('div');
      holder.innerHTML = element.content || '';
      const lines = holder.innerText.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
      const style = element.style || {};
      shapes.push(textBox(nextId++, `Canvas text ${nextId}`, x, y, w, h,
        (lines.length ? lines : ['']).map((line) => paragraph(line, {
          size: Number(style.fontSize) || 20,
          color: style.color || t.text,
          bold: Number(style.fontWeight) >= 600,
          align: style.textAlign === 'center' ? 'ctr' : style.textAlign === 'right' ? 'r' : 'l',
          font: String(style.fontFamily || 'Arial').split(',')[0].replace(/["']/g, ''),
        })), { margin: 0, rotation: element.rotation }));
    });
    shapes.push(textBox(nextId++, 'Slide Number', 12.2, 7.0, 0.55, 0.25, [paragraph(number, { size: 8, color: t.textSub, align: 'r' })], { margin: 0 }));
    return shapes.join('');
  }

  if (slide.type === 'title') {
    shapes.push(textBox(nextId++, 'Title', 1.1, 1.75, 8.1, 1.8, [
      paragraph(slide.title || '', { size: 34, color: t.text, bold: true }),
    ], { margin: 0, valign: 'mid' }));
    if (slide.subtitle) {
      shapes.push(textBox(nextId++, 'Subtitle', 1.12, 3.45, 7.3, 0.9, [
        paragraph(slide.subtitle, { size: 16, color: t.textSub }),
      ], { margin: 0 }));
    }
    shapes.push(shape(nextId++, 'Divider', 1.12, 4.65, 1.2, 0.05, t.accent, t.accent));
  } else if (slide.type === 'twoColumn') {
    shapes.push(textBox(nextId++, 'Title', 0.95, 0.55, 11.2, 0.75, [
      paragraph(slide.title || '', { size: 26, color: t.text, bold: true }),
    ], { margin: 0 }));
    const cols = [
      { data: slide.left || {}, x: 0.95 },
      { data: slide.right || {}, x: 6.85 },
    ];
    cols.forEach((col, colIndex) => {
      shapes.push(shape(nextId++, `Column ${colIndex + 1}`, col.x, 1.65, 5.35, 4.8, t.surface, t.primary, 'roundRect'));
      const points = Array.isArray(col.data.points) ? col.data.points : [];
      shapes.push(textBox(nextId++, `Column Text ${colIndex + 1}`, col.x + 0.25, 1.85, 4.85, 4.25, [
        paragraph(col.data.heading || '', { size: 16, color: t.primary, bold: true }),
        ...points.map((point) => paragraph(point, { size: 13, color: t.textSub, bullet: true })),
      ], { margin: 0 }));
    });
  } else if (slide.type === 'imageText') {
    const imageOnRight = ['modern-dark', 'blue-planet', 'tech-purple'].includes(theme);
    const textX = imageOnRight ? 0.95 : 5.95;
    const imageX = imageOnRight ? 8.1 : 0.95;
    if (imageRefs[0]?.relId) {
      shapes.push(imagePic(nextId++, 'Slide image', imageRefs[0].relId, imageX, 1.65, 4.1, 3.2));
    } else {
      shapes.push(shape(nextId++, 'Image placeholder', imageX, 1.65, 4.1, 3.2, t.surface, t.primary, 'roundRect'));
      shapes.push(textBox(nextId++, 'Image label', imageX + 0.35, 2.75, 3.4, 0.6, [
        paragraph(slide.imageEmoji || 'Image', { size: 18, color: t.textSub, align: 'ctr' }),
      ], { margin: 0, valign: 'mid' }));
    }
    shapes.push(textBox(nextId++, 'Title', textX, 1.1, 5.2, 0.95, [
      paragraph(slide.title || '', { size: 24, color: t.text, bold: true }),
    ], { margin: 0 }));
    shapes.push(textBox(nextId++, 'Body', textX, 2.15, 5.2, 3.0, [
      paragraph(slide.text || (slide.bullets || []).join('\n'), { size: 15, color: t.textSub }),
    ], { margin: 0 }));
  } else if (slide.type === 'table') {
    const headers = Array.isArray(slide.table?.headers) ? slide.table.headers : [];
    const rows = Array.isArray(slide.table?.rows) ? slide.table.rows.slice(0, 8) : [];
    const colCount = Math.max(headers.length, 1);
    const colWidth = 11.4 / colCount;
    const rowHeight = Math.min(0.62, 4.8 / Math.max(rows.length + 1, 1));
    shapes.push(textBox(nextId++, 'Title', 0.95, 0.55, 11.2, 0.75, [paragraph(slide.title || '', { size: 25, color: t.text, bold: true })], { margin: 0 }));
    headers.forEach((header, colIndex) => {
      shapes.push(textBox(nextId++, `Header ${colIndex + 1}`, 0.95 + colIndex * colWidth, 1.55, colWidth, rowHeight, [paragraph(header, { size: 11, color: t.text, bold: true })], { fill: t.surface, line: t.primary, valign: 'mid' }));
    });
    rows.forEach((row, rowIndex) => headers.forEach((_, colIndex) => {
      shapes.push(textBox(nextId++, `Cell ${rowIndex + 1}-${colIndex + 1}`, 0.95 + colIndex * colWidth, 1.55 + (rowIndex + 1) * rowHeight, colWidth, rowHeight, [paragraph(String(row?.[colIndex] ?? ''), { size: 10, color: t.textSub })], { line: t.surface, valign: 'mid' }));
    }));
  } else if (slide.type === 'chart') {
    const labels = slide.chart?.labels || slide.chart?.categories || [];
    const values = (slide.chart?.series?.[0]?.values || slide.chart?.values || []).map((value) => Number(value) || 0);
    const maxValue = Math.max(...values.map(Math.abs), 1);
    const groupWidth = 10.8 / Math.max(labels.length, 1);
    shapes.push(textBox(nextId++, 'Title', 0.95, 0.55, 11.2, 0.75, [paragraph(slide.title || '', { size: 25, color: t.text, bold: true })], { margin: 0 }));
    labels.slice(0, 10).forEach((label, index) => {
      const value = values[index] || 0;
      const barHeight = Math.max(0.08, Math.abs(value) / maxValue * 3.75);
      const x = 1.15 + index * groupWidth + groupWidth * 0.25;
      shapes.push(shape(nextId++, `Bar ${index + 1}`, x, 5.65 - barHeight, groupWidth * 0.5, barHeight, index % 2 ? t.primary : t.accent, null, 'roundRect'));
      shapes.push(textBox(nextId++, `Value ${index + 1}`, x - groupWidth * 0.15, 5.42 - barHeight, groupWidth * 0.8, 0.3, [paragraph(String(value), { size: 9, color: t.text, bold: true, align: 'ctr' })], { margin: 0 }));
      shapes.push(textBox(nextId++, `Label ${index + 1}`, x - groupWidth * 0.2, 5.78, groupWidth * 0.9, 0.45, [paragraph(String(label), { size: 9, color: t.textSub, align: 'ctr' })], { margin: 0 }));
    });
  } else if (slide.type === 'quote') {
    shapes.push(shape(nextId++, 'Quote card', 1.75, 1.45, 9.85, 4.55, t.surface, t.primary, 'roundRect'));
    shapes.push(textBox(nextId++, 'Quote', 2.35, 2.0, 8.65, 1.75, [
      paragraph(slide.quote || '', { size: 19, color: t.text, italic: true, align: 'ctr' }),
    ], { margin: 0 }));
    shapes.push(textBox(nextId++, 'Author', 3.2, 4.15, 7.0, 0.75, [
      paragraph(slide.author || '', { size: 14, color: t.primary, bold: true, align: 'ctr' }),
      paragraph(slide.role || '', { size: 11, color: t.textSub, align: 'ctr' }),
    ], { margin: 0 }));
  } else if (slide.type === 'thankyou') {
    shapes.push(textBox(nextId++, 'Thank you', 2.1, 2.05, 9.1, 1.25, [
      paragraph(slide.title || 'Cảm ơn!', { size: 36, color: t.text, bold: true, align: 'ctr' }),
    ], { margin: 0, valign: 'mid' }));
    shapes.push(textBox(nextId++, 'Subtitle', 2.8, 3.35, 7.7, 0.9, [
      paragraph(slide.subtitle || '', { size: 15, color: t.textSub, align: 'ctr' }),
    ], { margin: 0 }));
    if (slide.contact) {
      shapes.push(textBox(nextId++, 'Contact', 4.1, 4.55, 5.1, 0.55, [
        paragraph(slide.contact, { size: 12, color: t.primary, align: 'ctr' }),
      ], { fill: t.surface, line: t.primary, margin: 0, valign: 'mid' }));
    }
  } else {
    const bullets = Array.isArray(slide.bullets) ? slide.bullets : [];
    shapes.push(textBox(nextId++, 'Title', 0.95, 0.55, 11.2, 0.8, [
      paragraph(slide.title || '', { size: 25, color: t.text, bold: true }),
    ], { margin: 0 }));
    shapes.push(textBox(nextId++, 'Bullets', 1.05, 1.65, 10.8, 4.65, bullets.map((bullet) => (
      paragraph(bullet, { size: bullets.length > 5 ? 13 : 15, color: t.textSub, bullet: true })
    )), { margin: 0 }));
  }

  shapes.push(textBox(nextId++, 'Slide number', 11.75, 6.85, 0.75, 0.28, [
    paragraph(number, { size: 9, color: t.textSub, align: 'r' }),
  ], { margin: 0 }));

  return shapes.join('');
}

function slideXml(slide, index, theme, imageRefs) {
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>${buildSlideShapes(slide, index, theme, imageRefs)}</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>`;
}

function snapshotSlideXml(imageRelId) {
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>${imagePic(2, 'Rendered slide', imageRelId, 0, 0, SLIDE_W, SLIDE_H)}</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>`;
}

function notesSlideXml(notes) {
  const noteLines = String(notes || '')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  const noteParagraphs = noteLines.length > 0
    ? noteLines.map((line) => paragraph(line, { size: 12, color: '333333' })).join('')
    : paragraph('', { size: 12, color: '333333' });

  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:notes xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr><p:sp><p:nvSpPr><p:cNvPr id="2" name="Speaker Notes"/><p:cNvSpPr txBox="1"/><p:nvPr><p:ph type="body" idx="1"/></p:nvPr></p:nvSpPr><p:spPr><a:xfrm><a:off x="685800" y="4286250"/><a:ext cx="5486400" cy="3600450"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/><a:ln><a:noFill/></a:ln></p:spPr><p:txBody><a:bodyPr wrap="square" lIns="91440" tIns="91440" rIns="91440" bIns="91440"/><a:lstStyle/>${noteParagraphs}</p:txBody></p:sp></p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:notes>`;
}

function notesSlideRels(slideIndex) {
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="${relTypes.slide}" Target="../slides/slide${slideIndex}.xml"/><Relationship Id="rId2" Type="${relTypes.notesMaster}" Target="../notesMasters/notesMaster1.xml"/></Relationships>`;
}

function slideRels(images, hasNotes, slideIndex) {
  const imageRels = images.map((image, index) => `<Relationship Id="rId${index + 2}" Type="${relTypes.image}" Target="../media/image${image.index}.${image.ext}"/>`).join('');
  const notesRelId = `rId${images.length + 2}`;
  const notesRel = hasNotes ? `<Relationship Id="${notesRelId}" Type="${relTypes.notesSlide}" Target="../notesSlides/notesSlide${slideIndex}.xml"/>` : '';
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="${relTypes.slideLayout}" Target="../slideLayouts/slideLayout1.xml"/>${imageRels}${notesRel}</Relationships>`;
}

function contentTypes(slideCount, media, noteSlideIndexes) {
  const imageTypes = [...new Set(media.map((item) => item.ext))].map((ext) => {
    const contentType = ext === 'jpg' ? 'image/jpeg' : ext === 'webp' ? 'image/webp' : 'image/png';
    return `<Default Extension="${ext}" ContentType="${contentType}"/>`;
  }).join('');
  const slides = Array.from({ length: slideCount }, (_, i) => `<Override PartName="/ppt/slides/slide${i + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>`).join('');
  const notesSlides = noteSlideIndexes.map((index) => `<Override PartName="/ppt/notesSlides/notesSlide${index}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.notesSlide+xml"/>`).join('');
  const notesMasterType = noteSlideIndexes.length > 0 ? '<Override PartName="/ppt/notesMasters/notesMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.notesMaster+xml"/>' : '';
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>${imageTypes}<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/><Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>${notesMasterType}<Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/><Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>${slides}${notesSlides}</Types>`;
}

function presentationXml(slideCount, hasNotes) {
  const ids = Array.from({ length: slideCount }, (_, i) => `<p:sldId id="${256 + i}" r:id="rId${i + 2}"/>`).join('');
  const notesMaster = hasNotes ? `<p:notesMasterIdLst><p:notesMasterId r:id="rId${slideCount + 2}"/></p:notesMasterIdLst>` : '';
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>${notesMaster}<p:sldIdLst>${ids}</p:sldIdLst><p:sldSz cx="${emu(SLIDE_W)}" cy="${emu(SLIDE_H)}" type="wide"/><p:notesSz cx="6858000" cy="9144000"/></p:presentation>`;
}

function presentationRels(slideCount, hasNotes) {
  const slides = Array.from({ length: slideCount }, (_, i) => `<Relationship Id="rId${i + 2}" Type="${relTypes.slide}" Target="slides/slide${i + 1}.xml"/>`).join('');
  const notesMaster = hasNotes ? `<Relationship Id="rId${slideCount + 2}" Type="${relTypes.notesMaster}" Target="notesMasters/notesMaster1.xml"/>` : '';
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="${relTypes.slideMaster}" Target="slideMasters/slideMaster1.xml"/>${slides}${notesMaster}</Relationships>`;
}

const rootRels = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="${relTypes.officeDocument}" Target="ppt/presentation.xml"/></Relationships>`;

const slideMaster = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld><p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/><p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst><p:txStyles><p:titleStyle/><p:bodyStyle/><p:otherStyle/></p:txStyles></p:sldMaster>`;
const slideMasterRels = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="${relTypes.slideLayout}" Target="../slideLayouts/slideLayout1.xml"/><Relationship Id="rId2" Type="${relTypes.theme}" Target="../theme/theme1.xml"/></Relationships>`;
const slideLayout = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="blank" preserve="1"><p:cSld name="Blank"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>`;
const slideLayoutRels = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="${relTypes.slideMaster}" Target="../slideMasters/slideMaster1.xml"/></Relationships>`;
const notesMaster = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:notesMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld><p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/></p:notesMaster>`;
const notesMasterRels = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="${relTypes.theme}" Target="../theme/theme1.xml"/></Relationships>`;
const themeXml = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="GenSlideAuto"><a:themeElements><a:clrScheme name="GenSlideAuto"><a:dk1><a:srgbClr val="000000"/></a:dk1><a:lt1><a:srgbClr val="FFFFFF"/></a:lt1><a:dk2><a:srgbClr val="1F2937"/></a:dk2><a:lt2><a:srgbClr val="F8FAFC"/></a:lt2><a:accent1><a:srgbClr val="4F46E5"/></a:accent1><a:accent2><a:srgbClr val="38BDF8"/></a:accent2><a:accent3><a:srgbClr val="22C55E"/></a:accent3><a:accent4><a:srgbClr val="F59E0B"/></a:accent4><a:accent5><a:srgbClr val="E056FD"/></a:accent5><a:accent6><a:srgbClr val="FF6584"/></a:accent6><a:hlink><a:srgbClr val="2563EB"/></a:hlink><a:folHlink><a:srgbClr val="7C3AED"/></a:folHlink></a:clrScheme><a:fontScheme name="GenSlideAuto"><a:majorFont><a:latin typeface="Arial"/></a:majorFont><a:minorFont><a:latin typeface="Arial"/></a:minorFont></a:fontScheme><a:fmtScheme name="GenSlideAuto"><a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst><a:lnStyleLst><a:ln w="6350"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln></a:lnStyleLst><a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst><a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst></a:fmtScheme></a:themeElements></a:theme>`;

const crcTable = Array.from({ length: 256 }, (_, n) => {
  let c = n;
  for (let k = 0; k < 8; k += 1) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  return c >>> 0;
});

function crc32(bytes) {
  let c = 0xffffffff;
  for (let i = 0; i < bytes.length; i += 1) c = crcTable[(c ^ bytes[i]) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

function u16(value) {
  return [value & 0xff, (value >>> 8) & 0xff];
}

function u32(value) {
  return [value & 0xff, (value >>> 8) & 0xff, (value >>> 16) & 0xff, (value >>> 24) & 0xff];
}

function textBytes(text) {
  return new TextEncoder().encode(text);
}

function bytesOf(data) {
  if (data instanceof Uint8Array) return data;
  return textBytes(data);
}

function createZip(files) {
  const localParts = [];
  const centralParts = [];
  let offset = 0;

  files.forEach(({ name, data }) => {
    const nameBytes = textBytes(name);
    const body = bytesOf(data);
    const crc = crc32(body);
    const local = new Uint8Array([
      ...u32(0x04034b50), ...u16(20), ...u16(0), ...u16(0), ...u16(0), ...u16(0),
      ...u32(crc), ...u32(body.length), ...u32(body.length), ...u16(nameBytes.length), ...u16(0),
    ]);
    localParts.push(local, nameBytes, body);

    const central = new Uint8Array([
      ...u32(0x02014b50), ...u16(20), ...u16(20), ...u16(0), ...u16(0), ...u16(0), ...u16(0),
      ...u32(crc), ...u32(body.length), ...u32(body.length), ...u16(nameBytes.length), ...u16(0), ...u16(0),
      ...u16(0), ...u16(0), ...u32(0), ...u32(offset),
    ]);
    centralParts.push(central, nameBytes);
    offset += local.length + nameBytes.length + body.length;
  });

  const centralSize = centralParts.reduce((sum, part) => sum + part.length, 0);
  const end = new Uint8Array([
    ...u32(0x06054b50), ...u16(0), ...u16(0), ...u16(files.length), ...u16(files.length),
    ...u32(centralSize), ...u32(offset), ...u16(0),
  ]);
  const allParts = [...localParts, ...centralParts, end];
  const total = allParts.reduce((sum, part) => sum + part.length, 0);
  const zip = new Uint8Array(total);
  let cursor = 0;
  allParts.forEach((part) => {
    zip.set(part, cursor);
    cursor += part.length;
  });
  return zip;
}

export async function exportSlidesToPptx({ slides, theme = 'clean-white', fileName = 'presentation', slideSnapshots = [] }) {
  const media = [];
  const hasNotes = slides.some((slide) => String(slide.notes || slide.script || '').trim());
  const noteSlideIndexes = [];
  const files = [
    { name: '_rels/.rels', data: rootRels },
    { name: 'ppt/slideMasters/slideMaster1.xml', data: slideMaster },
    { name: 'ppt/slideMasters/_rels/slideMaster1.xml.rels', data: slideMasterRels },
    { name: 'ppt/slideLayouts/slideLayout1.xml', data: slideLayout },
    { name: 'ppt/slideLayouts/_rels/slideLayout1.xml.rels', data: slideLayoutRels },
    { name: 'ppt/theme/theme1.xml', data: themeXml },
    { name: 'ppt/presentation.xml', data: presentationXml(slides.length, hasNotes) },
    { name: 'ppt/_rels/presentation.xml.rels', data: presentationRels(slides.length, hasNotes) },
  ];

  if (hasNotes) {
    files.push(
      { name: 'ppt/notesMasters/notesMaster1.xml', data: notesMaster },
      { name: 'ppt/notesMasters/_rels/notesMaster1.xml.rels', data: notesMasterRels },
    );
  }

  for (let i = 0; i < slides.length; i += 1) {
    const noteText = String(slides[i].notes || slides[i].script || '').trim();
    const slideHasNotes = Boolean(noteText);
    const hasSnapshot = Boolean(slideSnapshots[i]);
    const imageUrls = hasSnapshot
      ? [slideSnapshots[i]]
      : Array.isArray(slides[i].elements) && slides[i].elements.length
        ? slides[i].elements.filter((element) => element.type === 'image' && element.src).map((element) => ({ src: element.src, storageUrl: element.storageUrl, assetId: element.assetId }))
        : [slides[i].imageUrl].filter(Boolean);
    const slideImages = [];
    const imageRefs = [];
    for (let sourceIndex = 0; sourceIndex < imageUrls.length; sourceIndex += 1) {
      const imageUrl = imageUrls[sourceIndex];
      const image = await readImage(imageUrl);
      if (!image) continue;
      const imageIndex = media.length + 1;
      const mediaImage = { ...image, index: imageIndex };
      media.push(mediaImage);
      slideImages.push(mediaImage);
      imageRefs[sourceIndex] = { ...mediaImage, relId: `rId${slideImages.length + 1}` };
      files.push({ name: `ppt/media/image${imageIndex}.${image.ext}`, data: image.buffer });
    }
    files.push({
      name: `ppt/slides/slide${i + 1}.xml`,
      data: hasSnapshot && slideImages[0] ? snapshotSlideXml(imageRefs[0].relId) : slideXml(slides[i], i, theme, imageRefs),
    });
    files.push({ name: `ppt/slides/_rels/slide${i + 1}.xml.rels`, data: slideRels(slideImages, slideHasNotes, i + 1) });
    if (slideHasNotes) {
      noteSlideIndexes.push(i + 1);
      files.push({ name: `ppt/notesSlides/notesSlide${i + 1}.xml`, data: notesSlideXml(noteText) });
      files.push({ name: `ppt/notesSlides/_rels/notesSlide${i + 1}.xml.rels`, data: notesSlideRels(i + 1) });
    }
  }

  files.unshift({ name: '[Content_Types].xml', data: contentTypes(slides.length, media, noteSlideIndexes) });

  const zip = createZip(files);
  const blob = new Blob([zip], {
    type: 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  });

  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `${safeFileName(fileName)}.pptx`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
}
