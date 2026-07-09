import os
import time
from typing import Optional
from google.oauth2 import service_account
import google.auth.transport.requests

_cached_token: Optional[str] = None
_cached_token_expires_at: float = 0.0

def get_vertex_access_token() -> Optional[str]:
    """Tải tệp khóa Service Account của GCP và tạo token truy cập được lưu tạm (cached)."""
    global _cached_token, _cached_token_expires_at
    from config import GCP_SERVICE_ACCOUNT_JSON_PATH, BASE_DIR
    
    path = GCP_SERVICE_ACCOUNT_JSON_PATH
    if not path:
        return None
        
    # Xử lý đường dẫn tương đối: kiểm tra thư mục làm việc hiện tại, thư mục gốc dự án (BASE_DIR) và thư mục chứa script
    if not os.path.isabs(path):
        if os.path.exists(path):
            path = os.path.abspath(path)
        elif os.path.exists(os.path.join(BASE_DIR, path)):
            path = os.path.join(BASE_DIR, path)
        else:
            # Kiểm tra đường dẫn tương đối so với thư mục backend (BASE_DIR / 'backend')
            backend_rel = os.path.join(BASE_DIR, "backend", path)
            if os.path.exists(backend_rel):
                path = backend_rel
            
    if not os.path.exists(path):
        print(f"[vertex_auth] Google Cloud service account JSON file not found at: {path}")
        return None
        
    # Trả về token đã được lưu tạm nếu vẫn hợp lệ (với bộ đệm 2 phút trước khi hết hạn)
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
