import { fitTextToBox } from './textFit';
import { inferImageFit } from './imageFit';

const id = () => `el-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

const THEME_TEXT = {
  'soft-blue': { title: "'Nunito', sans-serif", body: "'Inter', sans-serif", text: '#0b2e4a', sub: '#4a6a85' },
  'royal-purple': { title: "'Playfair Display', serif", body: "'Inter', sans-serif", text: '#ffffff', sub: '#c0a8e0' },
  'clean-white': { title: "'Playfair Display', serif", body: "'Inter', sans-serif", text: '#1a1a1a', sub: '#555555' },
  'modern-dark': { title: "'Space Grotesk', sans-serif", body: "'Inter', sans-serif", text: '#ffffff', sub: 'rgba(255,255,255,0.65)' },
  'playful-yellow': { title: "'Fredoka One', cursive", body: "'Inter', sans-serif", text: '#2e1e0a', sub: 'rgba(46,30,10,0.72)' },
  'gradient-border': { title: "'Plus Jakarta Sans', sans-serif", body: "'Inter', sans-serif", text: '#0f172a', sub: '#475569' },
  'blue-planet': { title: "'Exo 2', sans-serif", body: "'Inter', sans-serif", text: '#ffffff', sub: 'rgba(255,255,255,0.65)' },
  'nature-green': { title: "'Merriweather', serif", body: "'Inter', sans-serif", text: '#e8f5e2', sub: 'rgba(232,245,226,0.75)' },
  'tech-purple': { title: "'Rajdhani', sans-serif", body: "'Inter', sans-serif", text: '#ffffff', sub: 'rgba(255,255,255,0.65)' },
};

const textElement = (role, content, x, y, width, height, style = {}) => ({
  id: id(), type: 'text', role, x, y, width, height, rotation: 0,
  content: content || '',
  style: { fontFamily: 'Inter, sans-serif', fontSize: 22, color: '#1a1a1a', textAlign: 'left', fontWeight: 400, ...style },
});

const CODE_LINE = /^\s*(?:>>>.*|\.\.\..*|def\s+.*|class\s+.*|return\b.*|import\s+.*|from\s+\S+\s+import\s+.*|print\s*\(.*|if\s+.+:|for\s+.+:|while\s+.+:|[A-Za-z_]\w*\s*=.*|[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*\s*\([^()\n]*\)\s*)$/;
const CODE_PREFIX = /^\s*(?:(?:v[ií]\s+d[uụ](?:\s+m[aã])?|c[uú]\s+ph[aá]p|m[aã](?:\s+python)?|code|syntax|example)\s*:\s*)/i;
const LANGUAGE_MARKER = /^\s*(?:python|py|javascript|typescript|java|c\+\+|cpp)\s*$/i;
const escapeHtml = (value) => String(value || '')
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const richBulletHtml = (item) => {
  const value = String(item || '').trim();
  if (/^[^:]{2,38}:$/.test(value)) {
    return `<li class="slide-section-label">${escapeHtml(value.slice(0, -1))}</li>`;
  }
  const labelled = value.match(/^([^:]{2,32}):\s+(.+)$/);
  if (labelled) {
    return `<li><strong>${escapeHtml(labelled[1])}:</strong> ${escapeHtml(labelled[2])}</li>`;
  }
  return `<li>${escapeHtml(value)}</li>`;
};
const contentPartsFromBullets = (bullets) => {
  const normal = [];
  const code = [];
  (bullets || []).forEach((item) => {
    const lines = String(item || '').split(/\r?\n/).filter((line) => line.trim());
    lines.forEach((rawValue) => {
      const value = rawValue.trim();
      if (LANGUAGE_MARKER.test(value)) return;
      const withoutPrefix = value.replace(CODE_PREFIX, '').trim();
      if (CODE_LINE.test(value)) code.push(rawValue);
      else if (withoutPrefix !== value && CODE_LINE.test(withoutPrefix)) code.push(withoutPrefix);
      else normal.push(value.replace(/^\*\*(.+)\*\*$/, '$1'));
    });
  });
  const list = normal.length === 1 && code.length
    ? `<p class="slide-lead">${escapeHtml(normal[0])}</p>`
    : normal.length
      ? `<ul class="slide-content-flow">${normal.map(richBulletHtml).join('')}</ul>`
      : '';
  return { body: list, code: code.join('\n'), normal, codeLines: code };
};

const isVietnameseSlide = (slide) => {
  const language = String(slide?.language || slide?.lang || '').toLowerCase();
  if (language.startsWith('vi')) return true;
  if (language.startsWith('en')) return false;
  const text = [slide?.title, slide?.subtitle, ...(slide?.bullets || [])].filter(Boolean).join(' ');
  return /[ăâđêôơưàáạảãằắặẳẵầấậẩẫèéẹẻẽềếệểễìíịỉĩòóọỏõồốộổỗờớợởỡùúụủũừứựửữỳýỵỷỹ]/i.test(text)
    || /\b(bài giảng|tổng kết|mục tiêu|nội dung|cảm ơn)\b/i.test(text);
};

const contentTextMetrics = (slide, options = {}) => {
  const bullets = Array.isArray(slide?.bullets) ? slide.bullets.filter(Boolean) : [];
  const hasVisual = Boolean(slide?.imageUrl || slide?.table || slide?.chart);
  const width = slide?.imageUrl ? 452 : 832;
  const x = slide?.imageUrl ? 64 : bullets.length <= 4 ? 84 : 64;
  const adjustedWidth = slide?.imageUrl ? width : bullets.length <= 4 ? 792 : width;
  const lineHeight = bullets.length <= 4 ? 1.6 : 1.5;
  const fontSize = fitTextToBox(bullets.join('\n'), {
    width: adjustedWidth,
    height: options.height || 344,
    min: hasVisual ? 14 : 15,
    max: hasVisual ? 22 : 24,
    lineHeight,
    itemCount: bullets.length,
  });
  return { fontSize, lineHeight, x, width: adjustedWidth };
};

export function createElementsFromSlide(slide, theme = 'clean-white') {
  if (Array.isArray(slide?.elements) && slide.elements.length) return slide.elements;
  const colors = THEME_TEXT[theme] || THEME_TEXT['clean-white'];
  const elements = [];
  const isVietnamese = isVietnameseSlide(slide);
  const isLecture = String(slide?.presentationMode || '').toLowerCase() === 'lecture';

  if (slide?.type === 'title') {
    const introTitle = slide?.title || slide?.richText?.title || '';
    const introSubtitle = slide?.subtitle
      || (Array.isArray(slide?.bullets) ? slide.bullets[0] : '')
      || slide?.richText?.subtitle
      || '';
    const introTitleSize = fitTextToBox(introTitle, {
      width: 740, height: 132, min: 30, max: 54, lineHeight: 1.12,
    });
    const introSubtitleSize = fitTextToBox(introSubtitle, {
      width: 600, height: 90, min: 15, max: 24, lineHeight: 1.45,
    });
    const introLabel = isLecture
      ? (isVietnamese ? 'BÀI GIẢNG' : 'LECTURE')
      : (isVietnamese ? 'BÀI THUYẾT TRÌNH' : 'PRESENTATION');
    elements.push(textElement('custom', introLabel, 110, 116, 740, 34, {
      fontFamily: colors.body,
      fontSize: 14,
      color: colors.sub,
      fontWeight: 700,
      textAlign: 'center',
      letterSpacing: 2,
    }));
    elements.push(textElement('title', introTitle, 110, 164, 740, 132, {
      fontFamily: colors.title,
      fontSize: introTitleSize,
      color: colors.text,
      fontWeight: 800,
      lineHeight: 1.12,
      textAlign: 'center',
    }));
    if (introSubtitle) {
      elements.push(textElement('body', introSubtitle, 180, 318, 600, 90, {
        fontFamily: colors.body,
        fontSize: introSubtitleSize,
        color: colors.sub,
        lineHeight: 1.45,
        textAlign: 'center',
      }));
    }
    return elements;
  }

  if (slide?.type === 'thankyou') {
    const closingTitle = slide?.title || (isVietnamese ? 'Tổng kết và Hỏi đáp' : 'Summary and Q&A');
    const closingItems = Array.isArray(slide?.bullets)
      ? slide.bullets.filter(Boolean)
      : [slide?.subtitle, slide?.contact].filter(Boolean);
    const closingTitleSize = fitTextToBox(closingTitle, {
      width: 720, height: 112, min: 30, max: 50, lineHeight: 1.15,
    });
    const closingBodySize = fitTextToBox(closingItems.join('\n'), {
      width: 660, height: 168, min: 16, max: 24, lineHeight: 1.45, itemCount: closingItems.length,
    });
    const closingLabel = isLecture
      ? (isVietnamese ? 'KẾT THÚC BÀI GIẢNG' : 'END OF LECTURE')
      : (isVietnamese ? 'KẾT LUẬN' : 'CLOSING');
    elements.push(textElement('custom', closingLabel, 130, 112, 700, 34, {
      fontFamily: colors.body,
      fontSize: 14,
      color: colors.sub,
      fontWeight: 700,
      textAlign: 'center',
      letterSpacing: 2,
    }));
    elements.push(textElement('title', closingTitle, 120, 164, 720, 112, {
      fontFamily: colors.title,
      fontSize: closingTitleSize,
      color: colors.text,
      fontWeight: 800,
      lineHeight: 1.15,
      textAlign: 'center',
    }));
    if (closingItems.length) {
      elements.push(textElement(
        'body',
        `<ul>${closingItems.map((item) => `<li>${item}</li>`).join('')}</ul>`,
        150,
        286,
        660,
        168,
        {
          fontFamily: colors.body,
          fontSize: closingBodySize,
          color: colors.sub,
          lineHeight: 1.45,
          textAlign: 'left',
        },
      ));
    }
    return elements;
  }

  const sourceBullets = Array.isArray(slide?.bullets) ? slide.bullets.filter(Boolean) : [];
  const sourceTextLength = sourceBullets.join(' ').length;
  const contentParts = sourceBullets.length
    ? contentPartsFromBullets(sourceBullets)
    : { body: slide?.text || slide?.subtitle || slide?.richText?.bullets || slide?.richText?.text || '', code: '', normal: [] };
  const body = contentParts.body;
  const hasCode = Boolean(contentParts.code);
  // Dense teaching slides are clearer as full-width text. A decorative image
  // should not force the lesson itself into an undersized column. Code already
  // provides the visual anchor, so code and decorative imagery never compete.
  const showImage = Boolean(slide?.imageUrl)
    && !hasCode
    && sourceBullets.length <= 7
    && sourceTextLength <= 760;
  const hasVisual = Boolean(showImage || slide?.table || slide?.chart);
  const titleFontSize = fitTextToBox(slide?.title || slide?.richText?.title, {
    width: 832,
    height: 66,
    min: 24,
    max: hasVisual ? 34 : 38,
    lineHeight: 1.2,
    padding: 0,
  });
  elements.push(textElement('title', slide?.title || slide?.richText?.title, 64, 44, 832, 66, {
    fontFamily: colors.title, fontSize: titleFontSize, color: colors.text, fontWeight: 700, lineHeight: 1.2,
  }));

  const normalTextLength = contentParts.normal.join(' ').length;
  const codeBodyHeight = body
    ? Math.min(150, Math.max(
      78,
      (contentParts.normal.length * 24) + (Math.ceil(normalTextLength / 90) * 14),
    ))
    : 0;
  const bodyHeight = hasCode ? codeBodyHeight : 344;
  const bodyMetrics = contentTextMetrics(
    { ...slide, imageUrl: showImage ? slide?.imageUrl : '', bullets: contentParts.normal },
    { height: bodyHeight },
  );
  if (body && !slide?.table && !slide?.chart) elements.push(textElement(
    'body',
    body,
    bodyMetrics.x,
    126,
    bodyMetrics.width,
    bodyHeight,
    {
      fontFamily: colors.body,
      fontSize: bodyMetrics.fontSize,
      color: colors.sub,
      lineHeight: bodyMetrics.lineHeight,
    },
  ));
  if (hasCode && !slide?.table && !slide?.chart) {
    const codeY = body ? 126 + bodyHeight + 12 : 126;
    const codeHeight = 470 - codeY;
    const codeWidth = 832;
    const codeSize = fitTextToBox(contentParts.code, {
      width: codeWidth - 28,
      height: codeHeight - 24,
      min: 13,
      max: 20,
      lineHeight: 1.42,
      padding: 0,
    });
    elements.push(textElement(
      'code',
      `<pre class="slide-code-block"><code>${escapeHtml(contentParts.code)}</code></pre>`,
      64,
      codeY,
      codeWidth,
      codeHeight,
      {
        fontFamily: "'JetBrains Mono','Cascadia Code',Consolas,monospace",
        fontSize: codeSize,
        color: '#e2e8f0',
        lineHeight: 1.42,
      },
    ));
  }
  if (showImage) {
    elements.push({
      id: id(), type: 'image', role: 'image', x: 550, y: 140,
      width: 330, height: 290, rotation: 0, src: slide.imageUrl,
      objectFit: inferImageFit(slide),
    });
  }
  if (slide?.table) {
    elements.push({
      id: id(), type: 'table', role: 'visual', x: 64, y: 120,
      width: 832, height: 350, rotation: 0, data: slide.table,
    });
  } else if (slide?.chart) {
    elements.push({
      id: id(), type: 'chart', role: 'visual', x: 64, y: 120,
      width: 832, height: 350, rotation: 0, data: slide.chart,
    });
  }
  return elements;
}

export function createTextElement() {
  return textElement('custom', 'Nhập nội dung', 280, 220, 400, 80, { fontSize: 28 });
}
