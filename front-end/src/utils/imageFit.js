const DIAGRAM_HINTS = [
  'diagram', 'workflow', 'flowchart', 'architecture', 'schematic', 'infographic',
  'chart', 'graph', 'plot', 'matrix', 'sơ đồ', 'biểu đồ', 'quy trình', 'kiến trúc',
];

export function inferImageFit(slideOrUrl) {
  if (slideOrUrl && typeof slideOrUrl === 'object' && slideOrUrl.imageFit) {
    return slideOrUrl.imageFit;
  }

  const slide = typeof slideOrUrl === 'object' ? slideOrUrl : {};
  const imageUrl = typeof slideOrUrl === 'string' ? slideOrUrl : slide.imageUrl || slide.src || '';
  const normalizedUrl = String(imageUrl).toLowerCase().replace(/\\/g, '/');
  const semanticText = [
    slide.imageKind,
    slide.primaryVisual,
    slide.imagePrompt,
    slide.title,
  ].filter(Boolean).join(' ').toLocaleLowerCase('vi');

  // Source-document visuals often contain labels, axes, or multiple panels.
  // Showing the complete figure is more important than filling a decorative mask.
  if (normalizedUrl.includes('/outputs/images/source/')) return 'contain';
  // External PNG/WebP assets are commonly diagrams, plots, charts or document
  // figures with transparent/white margins. Cropping them can remove labels.
  if (/_external\.(?:png|webp)(?:$|[?#])/.test(normalizedUrl)) return 'contain';
  if (DIAGRAM_HINTS.some((hint) => semanticText.includes(hint))) return 'contain';
  return 'cover';
}
