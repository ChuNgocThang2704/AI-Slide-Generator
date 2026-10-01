// SVG markup -> PNG data URL in the browser. Used to export things PowerPoint cannot draw
// natively from our data (icons), as pictures that stay movable and resizable there.

export function svgToPng(svgMarkup, width, height) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => {
      const canvas = document.createElement('canvas');
      canvas.width = Math.max(1, Math.round(width));
      canvas.height = Math.max(1, Math.round(height));
      const context = canvas.getContext('2d');
      context.drawImage(image, 0, 0, canvas.width, canvas.height);
      resolve(canvas.toDataURL('image/png'));
    };
    image.onerror = () => reject(new Error('Không thể chuyển biểu tượng thành ảnh'));
    image.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svgMarkup)}`;
  });
}

/** PNG of a Lucide icon component (looked up by the caller), drawn at 4x for a sharp result. */
export async function iconToPng(IconComponent, { color, strokeWidth, sizePx = 256 }) {
  const [{ createElement }, { renderToStaticMarkup }] = await Promise.all([
    import('react'),
    import('react-dom/server'),
  ]);
  const markup = renderToStaticMarkup(createElement(IconComponent, {
    size: sizePx,
    color,
    strokeWidth,
    xmlns: 'http://www.w3.org/2000/svg',
  }));
  return svgToPng(markup, sizePx, sizePx);
}
