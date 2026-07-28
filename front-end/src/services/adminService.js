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

export const adminService = {
  // ── USER MANAGEMENT ──
  async getUsers(page = 0, size = 10) {
    const response = await apiClient.get('/users', {
      params: { page, size }
    });
    return normalizeApiResponse(response.data);
  },

  async deleteUser(userId) {
    const response = await apiClient.delete(`/users/${userId}`);
    return normalizeApiResponse(response.data);
  },

  // ── ROLE MANAGEMENT ──
  async getRoles() {
    const response = await apiClient.get('/roles');
    return normalizeApiResponse(response.data);
  },

  async createRole(roleObj) {
    const response = await apiClient.post('/roles', roleObj);
    return normalizeApiResponse(response.data);
  },

  async deleteRole(roleName) {
    const response = await apiClient.delete(`/roles/${roleName}`);
    return normalizeApiResponse(response.data);
  },

  // ── PERMISSION MANAGEMENT ──
  async getPermissions() {
    const response = await apiClient.get('/permissions');
    return normalizeApiResponse(response.data);
  },

  async createPermission(permObj) {
    const response = await apiClient.post('/permissions', permObj);
    return normalizeApiResponse(response.data);
  },

  async deletePermission(permName) {
    const response = await apiClient.delete(`/permissions/${permName}`);
    return normalizeApiResponse(response.data);
  }
};
