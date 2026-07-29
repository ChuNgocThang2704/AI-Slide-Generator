import { fitTextToBox } from './textFit';

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

const isVietnameseSlide = (slide) => {
  const language = String(slide?.language || slide?.lang || '').toLowerCase();
  if (language.startsWith('vi')) return true;
  if (language.startsWith('en')) return false;
  const text = [slide?.title, slide?.subtitle, ...(slide?.bullets || [])].filter(Boolean).join(' ');
  return /[ăâđêôơưàáạảãằắặẳẵầấậẩẫèéẹẻẽềếệểễìíịỉĩòóọỏõồốộổỗờớợởỡùúụủũừứựửữỳýỵỷỹ]/i.test(text)
    || /\b(bài giảng|tổng kết|mục tiêu|nội dung|cảm ơn)\b/i.test(text);
};

const contentTextMetrics = (slide) => {
  const bullets = Array.isArray(slide?.bullets) ? slide.bullets.filter(Boolean) : [];
  const hasVisual = Boolean(slide?.imageUrl || slide?.table || slide?.chart);
  const width = slide?.imageUrl ? 430 : 832;
  const x = slide?.imageUrl ? 64 : bullets.length <= 4 ? 84 : 64;
  const adjustedWidth = slide?.imageUrl ? width : bullets.length <= 4 ? 792 : width;
  const lineHeight = bullets.length <= 4 ? 1.6 : 1.5;
  const fontSize = fitTextToBox(bullets.join('\n'), {
    width: adjustedWidth,
    height: 344,
    min: hasVisual ? 12 : 13,
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

  if (slide?.type === 'title') {
    elements.push(textElement('custom', isVietnamese ? 'BÀI GIẢNG' : 'LECTURE', 110, 116, 740, 34, {
      fontFamily: colors.body,
      fontSize: 14,
      color: colors.sub,
      fontWeight: 700,
      textAlign: 'center',
      letterSpacing: 2,
    }));
    elements.push(textElement('title', slide?.title || slide?.richText?.title, 110, 164, 740, 132, {
      fontFamily: colors.title,
      fontSize: 48,
      color: colors.text,
      fontWeight: 800,
      lineHeight: 1.12,
      textAlign: 'center',
    }));
    const subtitle = slide?.subtitle
      || (Array.isArray(slide?.bullets) ? slide.bullets[0] : '')
      || slide?.richText?.subtitle
      || '';
    if (subtitle) {
      elements.push(textElement('body', subtitle, 180, 318, 600, 90, {
        fontFamily: colors.body,
        fontSize: 20,
        color: colors.sub,
        lineHeight: 1.45,
        textAlign: 'center',
      }));
    }
    return elements;
  }

  if (slide?.type === 'thankyou') {
    elements.push(textElement('custom', isVietnamese ? 'KẾT THÚC BÀI GIẢNG' : 'END OF LECTURE', 130, 112, 700, 34, {
      fontFamily: colors.body,
      fontSize: 14,
      color: colors.sub,
      fontWeight: 700,
      textAlign: 'center',
      letterSpacing: 2,
    }));
    elements.push(textElement('title', slide?.title || (isVietnamese ? 'Tổng kết và Hỏi đáp' : 'Summary and Q&A'), 120, 164, 720, 112, {
      fontFamily: colors.title,
      fontSize: 46,
      color: colors.text,
      fontWeight: 800,
      lineHeight: 1.15,
      textAlign: 'center',
    }));
    const closingItems = Array.isArray(slide?.bullets)
      ? slide.bullets
      : [slide?.subtitle, slide?.contact].filter(Boolean);
    if (closingItems.length) {
      elements.push(textElement(
        'body',
        `<ul>${closingItems.map((item) => `<li>${item}</li>`).join('')}</ul>`,
        190,
        302,
        580,
        132,
        {
          fontFamily: colors.body,
          fontSize: 19,
          color: colors.sub,
          lineHeight: 1.5,
          textAlign: 'left',
        },
      ));
    }
    return elements;
  }

  const contentMetrics = contentTextMetrics(slide);
  const hasVisual = Boolean(slide?.imageUrl || slide?.table || slide?.chart);
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

  const body = Array.isArray(slide?.bullets) && slide.bullets.length
    ? `<ul>${slide.bullets.map((item) => `<li>${item}</li>`).join('')}</ul>`
    : slide?.text || slide?.subtitle || slide?.richText?.bullets || slide?.richText?.text || '';
  if (body && !slide?.table && !slide?.chart) elements.push(textElement(
    'body',
    body,
    contentMetrics.x,
    126,
    contentMetrics.width,
    344,
    {
      fontFamily: colors.body,
      fontSize: contentMetrics.fontSize,
      color: colors.sub,
      lineHeight: contentMetrics.lineHeight,
    },
  ));
  if (slide?.imageUrl) {
    elements.push({ id: id(), type: 'image', role: 'image', x: 540, y: 135, width: 350, height: 300, rotation: 0, src: slide.imageUrl });
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
