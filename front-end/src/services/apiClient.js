import axios from 'axios';
import { useAuthStore } from '../store';

const configuredBaseUrl = String(import.meta.env.VITE_API_BASE_URL || '').trim();
const gatewayPort = String(import.meta.env.VITE_GATEWAY_PORT || '8080').trim();
const API_BASE_URL = configuredBaseUrl || (
  typeof window !== 'undefined'
    ? `${window.location.protocol}//${window.location.hostname}:${gatewayPort}/api`
    : `http://localhost:${gatewayPort}/api`
);

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

let refreshPromise = null;

apiClient.interceptors.request.use((config) => {
  const { token } = useAuthStore.getState();
  if (token) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

const MESSAGE_TRANSLATIONS = {
  'Email or password incorrect': 'Email hoặc mật khẩu không đúng',
  'User existed': 'Email này đã được đăng ký',
  'User already exists': 'Email này đã được đăng ký',
  'User not existed': 'Không tìm thấy người dùng',
  'User not found': 'Không tìm thấy người dùng',
  'User is inactive': 'Tài khoản đã bị vô hiệu hóa',
  'Invalid email address': 'Địa chỉ email không hợp lệ',
  'Email is required': 'Vui lòng nhập địa chỉ email',
  'Invalid code or expired': 'Mã xác thực không đúng hoặc đã hết hạn',
  'Google authentication failed': 'Đăng nhập Google thất bại',
  'Unauthenticated': 'Phiên đăng nhập đã hết hạn',
  'Token not found in request!': 'Vui lòng đăng nhập để tiếp tục',
  'Token is invalid!': 'Phiên đăng nhập không hợp lệ, vui lòng đăng nhập lại',
  'Token has expired!': 'Phiên đăng nhập đã hết hạn, vui lòng đăng nhập lại',
  'You do not have permission': 'Bạn không có quyền thực hiện thao tác này',
  'You do not have permission to access this resource': 'Bạn không có quyền truy cập nội dung này',
  'Project not found': 'Không tìm thấy project',
  'Document not found': 'Không tìm thấy tài liệu',
  'Daily slide generation limit reached': 'Bạn đã dùng hết lượt tạo slide hôm nay',
  'Internal server error': 'Máy chủ gặp lỗi, vui lòng thử lại sau',
  'Uncategorized error': 'Máy chủ gặp lỗi, vui lòng thử lại sau',
};

function validationMessage(data) {
  const details = data?.details || data?.errors || data?.detail;
  if (typeof details === 'string') return details;
  if (Array.isArray(details)) {
    const messages = details
      .map((item) => item?.message || item?.msg || (typeof item === 'string' ? item : ''))
      .filter(Boolean);
    if (messages.length) return messages.join('. ');
  }
  if (details && typeof details === 'object') {
    const messages = Object.values(details).flat().filter((item) => typeof item === 'string');
    if (messages.length) return messages.join('. ');
  }
  return '';
}

function fallbackMessage(status) {
  if (status === 400) return 'Dữ liệu gửi lên chưa hợp lệ';
  if (status === 401) return 'Phiên đăng nhập đã hết hạn';
  if (status === 403) return 'Bạn không có quyền thực hiện thao tác này';
  if (status === 404) return 'Không tìm thấy dữ liệu yêu cầu';
  if (status === 409) return 'Dữ liệu đã tồn tại hoặc đang bị xung đột';
  if (status === 413) return 'Tệp tải lên vượt quá dung lượng cho phép';
  if (status === 429) return 'Bạn thao tác quá nhanh, vui lòng thử lại sau';
  if (status >= 500) return 'Máy chủ đang gặp sự cố, vui lòng thử lại sau';
  return 'Không thể thực hiện yêu cầu';
}

function responseMessage(data, status) {
  const validation = validationMessage(data);
  if (validation) return validation;

  const backendMessage = typeof data?.message === 'string' ? data.message.trim() : '';
  if (MESSAGE_TRANSLATIONS[backendMessage]) return MESSAGE_TRANSLATIONS[backendMessage];
  if (/^(uncategorized error|internal server error)(\s*-|$)/i.test(backendMessage)) {
    return fallbackMessage(status || 500);
  }
  return backendMessage || fallbackMessage(status);
}

apiClient.interceptors.response.use(
  (response) => response,
  async (axiosError) => {
    const response = axiosError.response;
    const status = response?.status;
    const data = response?.data;
    const originalRequest = axiosError.config || {};
    const requestUrl = String(originalRequest.url || '');
    const authState = useAuthStore.getState();
    const isAuthRequest = requestUrl.startsWith('/auth/');
    const failedAuthorization = String(
      originalRequest.headers?.Authorization || originalRequest.headers?.authorization || '',
    );

    if (
      status === 401
      && authState.token
      && !isAuthRequest
      && !originalRequest._retry
      && failedAuthorization
      && failedAuthorization !== `Bearer ${authState.token}`
    ) {
      originalRequest._retry = true;
      originalRequest.headers = originalRequest.headers || {};
      originalRequest.headers.Authorization = `Bearer ${authState.token}`;
      return apiClient(originalRequest);
    }

    if (
      status === 401
      && authState.token
      && authState.refreshToken
      && !isAuthRequest
      && !originalRequest._retry
    ) {
      originalRequest._retry = true;
      try {
        if (!refreshPromise) {
          refreshPromise = axios
            .post(
              `${API_BASE_URL}/auth/refresh`,
              { token: authState.refreshToken },
              { headers: { 'Content-Type': 'application/json' } },
            )
            .then((refreshResponse) => {
              const payload = refreshResponse?.data?.data ?? refreshResponse?.data;
              if (!payload?.token) {
                throw new Error('Refresh response does not contain an access token');
              }
              useAuthStore.getState().updateTokens(
                payload.token,
                payload.refreshToken || authState.refreshToken,
              );
              return payload.token;
            })
            .finally(() => {
              refreshPromise = null;
            });
        }

        const newToken = await refreshPromise;
        originalRequest.headers = originalRequest.headers || {};
        originalRequest.headers.Authorization = `Bearer ${newToken}`;
        return apiClient(originalRequest);
      } catch {
        useAuthStore.getState().logout();
        const refreshError = new Error('Phiên đăng nhập đã hết hạn, vui lòng đăng nhập lại');
        refreshError.name = 'ApiError';
        refreshError.status = 401;
        refreshError.code = 401;
        refreshError.details = null;
        return Promise.reject(refreshError);
      }
    }

    let message;
    if (!response) {
      message = axiosError.code === 'ECONNABORTED'
        ? 'Máy chủ phản hồi quá lâu, vui lòng thử lại'
        : 'Không thể kết nối tới máy chủ. Vui lòng kiểm tra kết nối và thử lại';
    } else {
      message = responseMessage(data, status);
    }

    const error = new Error(message);
    error.name = 'ApiError';
    error.status = status || 0;
    error.code = data?.code ?? axiosError.code;
    error.details = data?.details || data?.errors || data?.detail || null;

    const hadToken = Boolean(useAuthStore.getState().token);
    if (status === 401 && hadToken && !isAuthRequest) {
      useAuthStore.getState().logout();
      error.message = 'Phiên đăng nhập đã hết hạn, vui lòng đăng nhập lại';
    }

    return Promise.reject(error);
  }
);

export default apiClient;
