import axios from 'axios';

// Tất cả request đi qua proxy /lecgen-api để tránh CORS
// Vite dev: proxy trong vite.config.js, Production: proxy trong Nginx
const proxyClient = axios.create({
  baseURL: '/lecgen-api/api/v1',
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
    const username = email;
    console.log('🚀 [LecGen Auth] Đăng nhập LecGen Server:', username);
    try {
      const res = await proxyClient.post('/auth/login', { username, password });
      console.log('✅ [LecGen Login Success]:', res.data);
      if (res.data?.access_token) {
        localStorage.setItem('lecgen_token', res.data.access_token);
      }
      return res.data;
    } catch (err) {
      console.error('❌ [LecGen Login Error]:', err.response?.data || err.message);
      throw err;
    }
  },

  /**
   * Đăng ký tài khoản mới trên LecGen Server
   */
  async registerLecgen(email, password) {
    const payload = { username: email, email, password };
    console.log('🚀 [LecGen Register]:', payload);
    try {
      const res = await proxyClient.post('/auth/register', payload);
      console.log('✅ [LecGen Register Success]:', res.data);
      return res.data;
    } catch (err) {
      console.error('❌ [LecGen Register Error]:', err.response?.data || err.message);
      throw err;
    }
  },

  /**
   * Gọi API GET /users/me
   */
  async getUsersMe(token) {
    const lecgenToken = token || localStorage.getItem('lecgen_token');
    console.log('🚀 [LecGen] GET /users/me');
    try {
      const res = await proxyClient.get('/users/me', {
        headers: { Authorization: `Bearer ${lecgenToken}` },
      });
      console.log('🎉 [LecGen /users/me]:', res.data);
      return res.data;
    } catch (err) {
      console.error('❌ [LecGen /users/me Error]:', err.response?.data || err.message);
      throw err;
    }
  },

  // Backward compat alias
  async getUsersMeViaProxy(token) {
    return this.getUsersMe(token);
  }
};
