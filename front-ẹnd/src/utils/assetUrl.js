export function resolveAssetUrl(url) {
  if (!url) return '';
  if (import.meta.env?.DEV && url.includes('host.docker.internal')) {
    return url.replace('host.docker.internal', 'localhost');
  }
  return url;
}
