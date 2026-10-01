// Pictures the PPTX export has to draw itself because PowerPoint has no matching native shape.
import { resolveTemplateAssetUrl } from './assetUrl.js';

const SCALE = 3;

const rgbOf = (hex) => {
  const match = /^#?([0-9a-f]{6})$/i.exec(String(hex || '').trim());
  const value = match ? parseInt(match[1], 16) : 0x6c63ff;
  return `${(value >> 16) & 255}, ${(value >> 8) & 255}, ${value & 255}`;
};

/** The dot-grid ornament (radius 1.6, every 18px, the same as on the canvas) as a transparent PNG. */
export function dotsToPng(color, widthPx, heightPx) {
  const canvas = document.createElement('canvas');
  canvas.width = Math.max(1, Math.round(widthPx * SCALE));
  canvas.height = Math.max(1, Math.round(heightPx * SCALE));
  const context = canvas.getContext('2d');
  context.fillStyle = `rgb(${rgbOf(color)})`;
  for (let x = 9; x < widthPx; x += 18) {
    for (let y = 9; y < heightPx; y += 18) {
      context.beginPath();
      context.arc(x * SCALE, y * SCALE, 1.6 * SCALE, 0, Math.PI * 2);
      context.fill();
    }
  }
  return canvas.toDataURL('image/png');
}

const loadImage = (url) => new Promise((resolve, reject) => {
  const image = new Image();
  image.crossOrigin = 'anonymous';
  image.onload = () => resolve(image);
  image.onerror = () => reject(new Error('Không tải được ảnh trang trí'));
  image.src = url;
});

/**
 * A template picture with its crop, flip and rounded corners baked in, so it lands in
 * PowerPoint looking the way it does in the editor. Returns null if the picture is unavailable.
 */
export async function artImageToPng(item, widthPx, heightPx) {
  try {
    const image = await loadImage(resolveTemplateAssetUrl(item.src));
    const style = item.style || {};
    const cropL = style.cropL || 0;
    const cropT = style.cropT || 0;
    const cropW = Math.max(0.05, 1 - cropL - (style.cropR || 0));
    const cropH = Math.max(0.05, 1 - cropT - (style.cropB || 0));
    const canvas = document.createElement('canvas');
    canvas.width = Math.max(1, Math.round(widthPx * 2));
    canvas.height = Math.max(1, Math.round(heightPx * 2));
    const context = canvas.getContext('2d');
    if (style.borderRadius) {
      const radius = String(style.borderRadius).endsWith('%')
        ? (parseFloat(style.borderRadius) / 100) * Math.min(canvas.width, canvas.height)
        : parseFloat(style.borderRadius) * 2;
      context.beginPath();
      context.roundRect(0, 0, canvas.width, canvas.height, radius);
      context.clip();
    }
    context.translate(style.flipX ? canvas.width : 0, style.flipY ? canvas.height : 0);
    context.scale(style.flipX ? -1 : 1, style.flipY ? -1 : 1);
    context.drawImage(
      image,
      cropL * image.naturalWidth, cropT * image.naturalHeight, cropW * image.naturalWidth, cropH * image.naturalHeight,
      0, 0, canvas.width, canvas.height,
    );
    return canvas.toDataURL('image/png');
  } catch {
    return null;
  }
}
