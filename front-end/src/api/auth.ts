import api from './axios';
import type { ApiResponse, User } from '../types';

export const authApi = {
  login: (credentials: { email: string; password: string }) =>
    api.post<ApiResponse<{ token: string, user: User }>>('/auth/login', credentials),

  register: (data: { email: string; password: string }) =>
    api.post<ApiResponse<User>>('/auth/register', data),

  verifyCode: (data: { email: string; code: string }) =>
    api.post<ApiResponse<string>>('/auth/verify-code', data),

  refreshToken: (token: string) =>
    api.post<ApiResponse<{ token: string, user: User }>>('/auth/refresh', { token }),

  getGoogleAuthUrl: () =>
    api.get<ApiResponse<{ url: string }>>('/auth/google/login'),

  googleRedirect: (code: string) =>
    api.post<ApiResponse<{ token: string, user: User }>>('/auth/google/redirect', { code }),

  getProfile: () =>
    api.get<ApiResponse<User>>('/users/my-info'),
};
