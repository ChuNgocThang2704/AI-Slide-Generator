// Pictures of an uploaded template are served by the template service, addressed
// relative to the API (e.g. "/template/public/assets/<id>/image1.png").
export function resolveTemplateAssetUrl(url) {
  if (!url || !String(url).startsWith('/template/')) return url || '';
  const base = String(import.meta.env?.VITE_API_BASE_URL || '/api').replace(/\/$/, '');
  return `${base}${url}`;
}

export function resolveAssetUrl(url) {
  if (!url) return '';
  if (import.meta.env?.VITE_AI_IMAGES_SAME_ORIGIN === 'true') {
    try {
      const parsed = new URL(url, window.location.origin);
      const internalHost = ['ai-service', 'ai-slide-service', 'localhost', '127.0.0.1', 'host.docker.internal'].includes(parsed.hostname);
      if (internalHost && parsed.pathname.startsWith('/outputs/images/')) {
        return `${parsed.pathname}${parsed.search}`;
      }
    } catch {
      // Leave non-URL assets unchanged.
    }
  }
  if (import.meta.env?.DEV && url.includes('host.docker.internal')) {
    return url.replace('host.docker.internal', 'localhost');
  }
  return url;
}
