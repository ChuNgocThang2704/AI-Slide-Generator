// The ornaments of a generated theme (glows, frame, waves, dots, rings, stripe) as real shape
// elements. They are used twice: to draw the theme's decoration into exported files, and to
// "adopt" the decoration onto a slide so each piece can be selected, moved or deleted.
import { buildGeneratedTheme, isGeneratedTheme } from './generatedTheme.js';
import { shapeInfo } from './shapeLibrary.js';

const uid = () => `orn-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

const piece = (shape, box, style) => {
  const info = shapeInfo(shape);
  return {
    id: uid(),
    type: 'shape',
    role: 'ornament',
    ornament: true,
    shape: info.id,
    x: Math.round(box.x),
    y: Math.round(box.y),
    width: Math.round(box.width),
    height: Math.round(box.height),
    rotation: box.rotation || 0,
    fill: style.fill ?? 'transparent',
    borderColor: style.borderColor ?? 'transparent',
    borderWidth: style.borderWidth ?? 0,
    opacity: style.opacity ?? 1,
  };
};

/** Ornament elements for a theme code; empty for built-in themes and for the "none" choice. */
export function themeOrnaments(code) {
  if (!isGeneratedTheme(code)) return [];
  const { theme } = buildGeneratedTheme(code);
  const dark = !theme.isLight;
  const accent = theme.accent;
  const primary = theme.primary;

  switch (theme.decorKind) {
    case 'frame':
      return [
        piece('rect', { x: 20, y: 20, width: 920, height: 500 }, { borderColor: accent, borderWidth: 1, opacity: dark ? 0.32 : 0.28 }),
        piece('corner', { x: 14, y: 14, width: 34, height: 34 }, { fill: accent, opacity: 0.9 }),
        piece('corner', { x: 912, y: 492, width: 34, height: 34, rotation: 180 }, { fill: accent, opacity: 0.9 }),
      ];
    case 'waves':
      return [
        piece('wave', { x: 0, y: 390, width: 960, height: 150 }, { fill: primary, opacity: dark ? 0.16 : 0.1 }),
        piece('wave2', { x: 0, y: 402, width: 960, height: 138 }, { fill: accent, opacity: dark ? 0.14 : 0.09 }),
      ];
    case 'dots':
      return [
        piece('dots', { x: 700, y: 26, width: 230, height: 130 }, { fill: accent, opacity: 0.5 }),
        piece('dots', { x: 30, y: 424, width: 150, height: 90 }, { fill: primary, opacity: 0.4 }),
      ];
    case 'rings':
      return [300, 210, 120].map((size, index) => piece(
        'ellipse',
        { x: 960 - (size * 2) / 3, y: 540 - (size * 2) / 3, width: size, height: size },
        { borderColor: accent, borderWidth: 1.5, opacity: 0.34 - index * 0.06 },
      ));
    case 'stripe':
      return [
        piece('rect', { x: 800, y: -40, width: 90, height: 640, rotation: 18 }, { fill: accent, opacity: dark ? 0.1 : 0.08 }),
        piece('rect', { x: 916, y: -40, width: 4, height: 640, rotation: 18 }, { fill: accent, opacity: 0.5 }),
      ];
    case 'none':
      return [];
    default:
      return [
        piece('glow', { x: -130, y: 290, width: 420, height: 420 }, { fill: accent, opacity: dark ? 0.22 : 0.16 }),
        piece('glow', { x: 720, y: -140, width: 340, height: 340 }, { fill: primary, opacity: dark ? 0.24 : 0.14 }),
      ];
  }
}

/** Slides whose theme ornaments are already on the slide as elements (or hidden on purpose). */
export const hasOwnOrnaments = (slide) => Boolean(slide?.richText?._noOrnaments)
  || (Array.isArray(slide?.elements) && slide.elements.some((element) => element.ornament));
