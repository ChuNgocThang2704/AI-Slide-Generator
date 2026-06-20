import os
import time
from typing import Optional
from google.oauth2 import service_account
import google.auth.transport.requests

_cached_token: Optional[str] = None
_cached_token_expires_at: float = 0.0

def get_vertex_access_token() -> Optional[str]:
    """Load GCP Service Account key and generate a cached access token."""
    global _cached_token, _cached_token_expires_at
    from config import GCP_SERVICE_ACCOUNT_JSON_PATH, BASE_DIR
    
    path = GCP_SERVICE_ACCOUNT_JSON_PATH
    if not path:
        return None
        
    # Handle relative paths: check current working dir, project root (BASE_DIR), and script parent
    if not os.path.isabs(path):
        if os.path.exists(path):
            path = os.path.abspath(path)
        elif os.path.exists(os.path.join(BASE_DIR, path)):
            path = os.path.join(BASE_DIR, path)
        else:
            # Check relative to backend folder (BASE_DIR / 'backend')
            backend_rel = os.path.join(BASE_DIR, "backend", path)
            if os.path.exists(backend_rel):
                path = backend_rel
            
    if not os.path.exists(path):
        print(f"[vertex_auth] Google Cloud service account JSON file not found at: {path}")
        return None
        
    # Return cached token if valid (with a 2-minute buffer before expiry)
    if _cached_token and time.time() < _cached_token_expires_at - 120:
        return _cached_token
        
    try:
        scopes = ["https://www.googleapis.com/auth/cloud-platform"]
        credentials = service_account.Credentials.from_service_account_file(
            path, scopes=scopes
        )
        request = google.auth.transport.requests.Request()
        credentials.refresh(request)
        
        _cached_token = credentials.token
        if credentials.expiry:
            import datetime
            _cached_token_expires_at = credentials.expiry.replace(tzinfo=datetime.timezone.utc).timestamp()
        else:
            _cached_token_expires_at = time.time() + 3600
            
        print(f"[vertex_auth] Successfully retrieved OAuth2 token using credentials at {path}")
        return _cached_token
    except Exception as e:
        print(f"[vertex_auth] Failed to retrieve Google Cloud access token: {e}")
        return None
