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

// ─────────────────────────────────────────────
// PROJECT SERVICE
// ─────────────────────────────────────────────
export const projectService = {
  // Tạo project mới
  async create(title, templateId = 'clean-white', prompt = '', fileUrl = null, fileName = null, fileSize = null) {
    const response = await apiClient.post('/document/projects', {
      prompt: prompt || title,
      templateId: null,  // Tạm thời null vì template ID từ FE là string, backend cần UUID
      fileUrl,
      fileName,
      fileSize
    });
    return normalizeApiResponse(response.data);
  },

  // Lấy danh sách projects của user
  async getAll(page = 0, size = 10, search = '') {
    const response = await apiClient.get('/document/projects', {
      params: { page, size, search },
    });
    return normalizeApiResponse(response.data);
  },

  // Lấy chi tiết project
  async getById(id) {
    const response = await apiClient.get(`/document/projects/${id}`);
    return normalizeApiResponse(response.data);
  },

  // Cập nhật project
  async update(id, updates) {
    const response = await apiClient.post(`/document/projects/${id}`, updates);
    return normalizeApiResponse(response.data);
  },

  // Xóa nhiều projects
  async deleteMultiple(ids) {
    const response = await apiClient.delete('/document/projects', {
      data: ids,
    });
    return normalizeApiResponse(response.data);
  },

  // Lấy tất cả slide pages của project
  async getSlidePages(projectId) {
    const response = await apiClient.get(`/document/projects/${projectId}/pages`);
    return normalizeApiResponse(response.data);
  },

  // Cập nhật 1 slide page
  async updateSlidePage(projectId, pageId, updates) {
    const response = await apiClient.post(
      `/document/projects/${projectId}/pages/${pageId}`,
      updates
    );
    return normalizeApiResponse(response.data);
  },

  // Sync batch slide pages (cập nhật nhiều slides cùng lúc)
  async syncSlidePages(projectId, pageUpdates) {
    const response = await apiClient.post(
      `/document/projects/${projectId}/pages/sync`,
      pageUpdates
    );
    return normalizeApiResponse(response.data);
  },

  // Lấy AI task logs của project
  async getTaskLogs(projectId) {
    const response = await apiClient.get(`/document/projects/${projectId}/task-logs`);
    return normalizeApiResponse(response.data);
  },

  // Lấy danh sách exports (PDF, PPTX...)
  async getExports(projectId) {
    const response = await apiClient.get(`/document/projects/${projectId}/exports`);
    return normalizeApiResponse(response.data);
  },

  // Lấy tiến độ xử lý của project
  async getProgress(id) {
    const response = await apiClient.get(`/document/projects/${id}/progress`);
    return normalizeApiResponse(response.data);
  },

  // Hủy tác vụ sinh slide
  async cancel(id) {
    const response = await apiClient.post(`/document/projects/${id}/cancel`);
    return normalizeApiResponse(response.data);
  },

  // Chỉnh sửa slide bằng ngôn ngữ tự nhiên (AI Revise)
  async revise(projectId, payload) {
    const response = await apiClient.post(`/document/projects/${projectId}/revise`, payload);
    return normalizeApiResponse(response.data);
  },
};

// ─────────────────────────────────────────────
// SOURCE DOCUMENT SERVICE
// ─────────────────────────────────────────────
export const documentService = {
  // Upload file
  async upload(file) {
    const formData = new FormData();
    formData.append('file', file);

    const response = await apiClient.post(
      '/document/source-documents/upload',
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    );
    return normalizeApiResponse(response.data);
  },

  // Lấy danh sách documents của user
  async getAll(page = 0, size = 10, search = '') {
    const response = await apiClient.get('/document/source-documents', {
      params: { page, size, search },
    });
    return normalizeApiResponse(response.data);
  },

  // Lấy chi tiết document
  async getById(id) {
    const response = await apiClient.get(`/document/source-documents/${id}`);
    return normalizeApiResponse(response.data);
  },

  // Lấy presigned URL để xem file (S3)
  async getViewUrl(id) {
    const response = await apiClient.get(`/document/source-documents/${id}/view`);
    return normalizeApiResponse(response.data);
  },

  async getViewUrlByStorageUrl(url) {
    const response = await apiClient.get('/document/source-documents/view-url', {
      params: { url },
    });
    return normalizeApiResponse(response.data);
  },

  // Xóa nhiều documents
  async deleteMultiple(ids) {
    const response = await apiClient.delete('/document/source-documents', {
      data: ids,
    });
    return normalizeApiResponse(response.data);
  },
};
