const asElements = (value) => (Array.isArray(value) ? value.filter(Boolean) : []);

const elementOrder = (left, right) => {
  const y = (Number(left?.y) || 0) - (Number(right?.y) || 0);
  return y || ((Number(left?.x) || 0) - (Number(right?.x) || 0));
};

export function orderedBodyElements(elements) {
  return asElements(elements)
    .filter((element) => (
      element?.type === 'text'
      && (element?.role === 'body' || String(element?.role || '').startsWith('body-'))
    ))
    .sort(elementOrder);
}

export function normalizeTableElements(elements) {
  return asElements(elements).map((element) => {
    if (element?.type !== 'table') return element;
    return {
      ...element,
      role: element.role || 'visual',
      data: element.data || element.table || {},
    };
  });
}

export function layoutTemplateElements(slide, elements) {
  const normalized = normalizeTableElements(elements).map((element) => ({ ...element }));
  const title = normalized.find((element) => element?.type === 'text' && element?.role === 'title');
  const bodies = orderedBodyElements(normalized);
  const visual = normalized.find((element) => ['image', 'table', 'chart'].includes(element?.type));

  if (title) {
    title.x = 64;
    title.y = 44;
    title.width = 832;
    title.height = Math.max(58, Number(title.height) || 0);
  }

  if (visual && bodies.length === 1 && visual.type === 'image') {
    Object.assign(bodies[0], { x: 64, y: 126, width: 430, height: 344 });
    Object.assign(visual, { x: 540, y: 130, width: 356, height: 330 });
  } else if (bodies.length === 1) {
    Object.assign(bodies[0], { x: 64, y: 126, width: 832, height: 344 });
  } else if (bodies.length > 1) {
    const width = 396;
    bodies.forEach((element, index) => {
      Object.assign(element, { x: index % 2 ? 500 : 64, y: 126, width, height: 344 });
    });
  }

  return normalized;
}
