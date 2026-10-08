import apiClient from './apiClient';

const normalizeApiResponse = (response) => {
  if (!response) {
    throw new Error('Không nhận được phản hồi từ máy chủ');
  }

  if (response.code && response.code !== 200) {
    throw new Error(response.message || 'Yêu cầu thất bại');
  }

  if (typeof response.data !== 'undefined') {
    return response.data;
  }

  return response;
};

const buildAvatarUrl = (name) => {
  const safeName = name || 'User';
  return `https://ui-avatars.com/api/?name=${encodeURIComponent(safeName)}&background=6c63ff&color=fff`;
};

const mapUser = (userResponse) => {
  if (!userResponse) return null;

  const roleNames = (userResponse.roles || [])
    .map((role) => role?.name || role?.code || role)
    .filter(Boolean);
  const plan = roleNames.includes('USER_ULTRA')
    ? 'ultra'
    : roleNames.includes('USER_PRO')
      ? 'pro'
      : 'free';

  const name = userResponse.profile?.fullName || userResponse.username || userResponse.email?.split('@')[0] || 'User';
  const avatar = userResponse.profile?.avatarUrl || buildAvatarUrl(name);

  return {
    id: userResponse.id,
    email: userResponse.email,
    name,
    avatar,
    phoneNumber: userResponse.profile?.phoneNumber || '',
    dateOfBirth: userResponse.profile?.dateOfBirth || '',
    plan,
    credits: 0,
    roles: userResponse.roles || [],
  };
};

export const authService = {
  async getMe() {
    const response = await apiClient.get('/users/my-info');
    return mapUser(normalizeApiResponse(response.data));
  },

  async updateProfile(userId, updates) {
    const response = await apiClient.post(`/users/${userId}`, updates);
    return mapUser(normalizeApiResponse(response.data));
  },

  async login(email, password) {
    const authResponse = await apiClient.post('/auth/login', { email, password });
    const authData = normalizeApiResponse(authResponse.data);

    if (!authData?.token) {
      throw new Error('Đăng nhập thất bại');
    }

    const meResponse = await apiClient.get('/users/my-info', {
      headers: {
        Authorization: `Bearer ${authData.token}`,
      },
    });
    const meData = normalizeApiResponse(meResponse.data);
    const mappedUser = mapUser(meData);

    return {
      user: mappedUser,
      token: authData.token,
      refreshToken: authData.refreshToken,
    };
  },

  async getGoogleAuthUrl() {
    try {
      const response = await apiClient.get('/auth/google/login');
      return normalizeApiResponse(response.data);
    } catch {
      try {
        const fallback = await apiClient.get('/auth/google/url');
        return normalizeApiResponse(fallback.data);
      } catch (e) {
        console.warn('Google Auth URL endpoint failed:', e.message);
        return { url: '#' };
      }
    }
  },

  async loginWithGoogle(code) {
    let response;
    try {
      response = await apiClient.post('/auth/google/redirect', { code });
    } catch {
      response = await apiClient.post('/auth/google/callback', { code });
    }
    const authData = normalizeApiResponse(response.data);
    if (!authData?.token) {
      throw new Error('Đăng nhập Google thất bại');
    }
    const meResponse = await apiClient.get('/users/my-info', {
      headers: { Authorization: `Bearer ${authData.token}` },
    });
    const meData = normalizeApiResponse(meResponse.data);
    const mappedUser = mapUser(meData);

    return {
      user: mappedUser,
      token: authData.token,
      refreshToken: authData.refreshToken,
    };
  },

  async register(email, password) {
    // Chỉ gửi đăng ký để tạo mã OTP; tài khoản được kích hoạt sau khi người dùng nhập mã.
    const response = await apiClient.post('/auth/register', { email, password });
    return normalizeApiResponse(response.data);
  },

  async verifyCode(email, code) {
    const response = await apiClient.post('/auth/verify-code', { email, code });
    return normalizeApiResponse(response.data);
  },

  async resendVerification(email) {
    const response = await apiClient.post('/auth/resend-verification', { email });
    return normalizeApiResponse(response.data);
  },

  async forgotPassword(email) {
    const response = await apiClient.post('/auth/forgot-password', { email });
    return normalizeApiResponse(response.data);
  },

  async verifyResetCode(email, code) {
    const response = await apiClient.post('/auth/verify-reset-code', { email, code });
    return normalizeApiResponse(response.data);
  },

  async resetPassword(token, newPassword) {
    const response = await apiClient.post('/auth/reset-password', { token, newPassword });
    return normalizeApiResponse(response.data);
  },

  async logout() {
    const token = localStorage.getItem('token');
    if (!token) return;

    try {
      await apiClient.post('/auth/logout', null, {
        headers: { Authorization: `Bearer ${token}` },
        timeout: 3000
      });
    } catch (err) {
      console.warn('Logout API background call warning:', err.message);
    }
  }
};
