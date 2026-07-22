import { useRef, useState } from 'react';
import { documentService } from '../../services/documentService';
import { resolveAssetUrl } from '../../utils/assetUrl';

export default function AssetImage({ src, storageUrl, assetId, alt = '', onResolved, ...props }) {
  const [refreshed, setRefreshed] = useState(null);
  const refreshingRef = useRef(false);
  const resolvedSrc = refreshed?.source === src ? refreshed.url : resolveAssetUrl(src);

  const refresh = async () => {
    if ((!assetId && !storageUrl && !src) || refreshingRef.current) return;
    refreshingRef.current = true;
    try {
      const viewUrl = assetId
        ? await documentService.getViewUrl(assetId)
        : await documentService.getViewUrlByStorageUrl(storageUrl || src);
      if (viewUrl) {
        setRefreshed({ source: src, url: viewUrl });
        onResolved?.(viewUrl);
      }
    } catch {
      // Keep the broken state visible when the asset cannot be refreshed.
    } finally {
      refreshingRef.current = false;
    }
  };

  return <img {...props} src={resolvedSrc} alt={alt} onError={refresh}/>;
}
