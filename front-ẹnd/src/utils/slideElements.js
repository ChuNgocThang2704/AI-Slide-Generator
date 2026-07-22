const id = () => `el-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

const textElement = (role, content, x, y, width, height, style = {}) => ({
  id: id(), type: 'text', role, x, y, width, height, rotation: 0,
  content: content || '',
  style: { fontFamily: 'Inter, sans-serif', fontSize: 22, color: '#1a1a1a', textAlign: 'left', fontWeight: 400, ...style },
});

export function createElementsFromSlide(slide) {
  if (Array.isArray(slide?.elements) && slide.elements.length) return slide.elements;
  const elements = [];
  elements.push(textElement('title', slide?.richText?.title || slide?.title, 64, 48, 832, 72, { fontSize: 36, fontWeight: 700 }));

  const body = slide?.richText?.bullets || slide?.richText?.text ||
    (Array.isArray(slide?.bullets) ? `<ul>${slide.bullets.map((item) => `<li>${item}</li>`).join('')}</ul>` : slide?.text || slide?.subtitle || '');
  if (body) elements.push(textElement('body', body, 70, 140, slide?.imageUrl ? 430 : 820, 320, { fontSize: 20, color: '#374151' }));
  if (slide?.imageUrl) {
    elements.push({ id: id(), type: 'image', role: 'image', x: 540, y: 135, width: 350, height: 300, rotation: 0, src: slide.imageUrl });
  }
  return elements;
}

export function createTextElement() {
  return textElement('custom', 'Nhập nội dung', 280, 220, 400, 80, { fontSize: 28 });
}
