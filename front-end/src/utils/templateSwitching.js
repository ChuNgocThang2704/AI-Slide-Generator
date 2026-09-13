import { createElementsFromSlide } from './slideElements';

const cloneElements = (elements) => (Array.isArray(elements)
  ? elements.map((element) => ({
      ...element,
      style: element?.style ? { ...element.style } : undefined,
      data: element?.data && typeof element.data === 'object'
        ? structuredClone(element.data)
        : element?.data,
    }))
  : []);

export function prepareTemplateContent(slide, sourceTheme) {
  return {
    ...slide,
    sourceTheme: sourceTheme || slide?.sourceTheme || '',
    elements: cloneElements(slide?.elements).filter((element) => element?.role !== 'background'),
  };
}

export function applyCustomTemplateResult(slide, match) {
  const matchedElements = cloneElements(match?.elements);
  return {
    ...slide,
    layout: match?.layoutType || slide?.layout || slide?.type || 'content',
    templateLayoutId: match?.layoutId || '',
    templateBackgroundColor: match?.backgroundColor || '#FFFFFF',
    elements: matchedElements.length ? matchedElements : cloneElements(slide?.elements),
  };
}

export function restoreBuiltInTemplate(slide, theme = 'clean-white') {
  const semanticSlide = {
    ...slide,
    elements: [],
    templateLayoutId: undefined,
    templateBackgroundColor: undefined,
    sourceTheme: undefined,
  };
  return {
    ...semanticSlide,
    elements: createElementsFromSlide(semanticSlide, theme),
  };
}
