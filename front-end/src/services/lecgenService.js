import axios from 'axios';

// URL Backend gốc của LecGen Video Generator Server
const LECGEN_API_URL = 'https://lecgen.aitc.vn/api/v1';

export const lecgenApiClient = axios.create({
  baseURL: LECGEN_API_URL,
  headers: {
    'Accept': 'application/json, text/plain, */*',
    'Content-Type': 'application/json',
  },
});

export const lecgenService = {
  /**
   * Đăng nhập vào LecGen Server với username chính là email của người dùng
   */
  async loginLecgen(email, password) {
    const username = email; // Dùng trực tiếp Email làm Username
    console.log('🚀 [LecGen Auth] Đăng nhập LecGen Server với username = email:', username);

    try {
      const response = await lecgenApiClient.post('/auth/login', { username, password });
      console.log('✅ [LecGen Direct Login Success]:', response.data);
      if (response.data?.access_token) {
        localStorage.setItem('lecgen_token', response.data.access_token);
      }
      return response.data;
    } catch (error) {
      console.warn('⚠️ Direct Login thất bại/CORS, thử qua Proxy...');
      try {
        const proxyRes = await axios.post('/lecgen-api/api/v1/auth/login', { username, password });
        console.log('✅ [LecGen Proxy Login Success]:', proxyRes.data);
        if (proxyRes.data?.access_token) {
          localStorage.setItem('lecgen_token', proxyRes.data.access_token);
        }
        return proxyRes.data;
      } catch (proxyErr) {
        console.error('❌ [LecGen Login Error]:', proxyErr.response?.data || proxyErr.message);
        throw proxyErr;
      }
    }
  },

  /**
   * Đăng ký tài khoản mới trên LecGen Server với username = email và email = email
   */
  async registerLecgen(email, password) {
    const payload = {
      username: email, // Sử dụng Email làm Username chuẩn
      email: email,
      password: password
    };
    console.log('🚀 [LecGen Register] Đăng ký tài khoản mới trên LecGen Server:', payload);

    try {
      const response = await lecgenApiClient.post('/auth/register', payload);
      console.log('✅ [LecGen Direct Register Success]:', response.data);
      return response.data;
    } catch (error) {
      console.warn('⚠️ Direct Register thất bại, thử qua Proxy...');
      try {
        const proxyRes = await axios.post('/lecgen-api/api/v1/auth/register', payload);
        console.log('✅ [LecGen Proxy Register Success]:', proxyRes.data);
        return proxyRes.data;
      } catch (proxyErr) {
        console.error('❌ [LecGen Register Error]:', proxyErr.response?.data || proxyErr.message);
        throw proxyErr;
      }
    }
  },

  /**
   * Gọi API GET /users/me sang server https://lecgen.aitc.vn/api/v1/users/me
   */
  async getUsersMe(token) {
    const lecgenToken = token || localStorage.getItem('lecgen_token');
    console.log('🚀 [LecGen API Call] Gửi request đến GET /users/me');

    try {
      const response = await lecgenApiClient.get('/users/me', {
        headers: {
          Authorization: `Bearer ${lecgenToken}`,
        },
      });
      console.log('🎉 [LecGen API /users/me Success] Dữ liệu User LecGen:', response.data);
      return response.data;
    } catch (error) {
      console.warn('⚠️ Direct GET /users/me thất bại, thử qua Proxy...');
      return this.getUsersMeViaProxy(lecgenToken);
    }
  },

  /**
   * Gọi API GET /users/me qua Proxy
   */
  async getUsersMeViaProxy(token) {
    const lecgenToken = token || localStorage.getItem('lecgen_token');
    console.log('🚀 [LecGen Proxy Call] Gửi qua Proxy: GET /lecgen-api/api/v1/users/me');

    try {
      const response = await axios.get('/lecgen-api/api/v1/users/me', {
        headers: {
          'Accept': 'application/json, text/plain, */*',
          Authorization: `Bearer ${lecgenToken}`,
        },
      });
      console.log('🎉 [LecGen Proxy /users/me Success] Dữ liệu User LecGen:', response.data);
      return response.data;
    } catch (error) {
      console.error('❌ [LecGen Proxy Error]:', error.response?.data || error.message);
      throw error;
    }
  }
};
