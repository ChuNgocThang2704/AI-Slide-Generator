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
  async create(
    title,
    templateId = 'soft-blue',
    prompt = '',
    fileUrl = null,
    fileName = null,
    fileSize = null,
    sourceDocId = null,
    fastMode = false
  ) {
    const response = await apiClient.post('/document/projects', {
      prompt: prompt || title,
      templateId,
      fastMode,
      sourceDocId,
      fileUrl: sourceDocId ? null : fileUrl,
      fileName: sourceDocId ? null : fileName,
      fileSize: sourceDocId ? null : fileSize,
    });
    return normalizeApiResponse(response.data);
  },

  // Creates a project straight from an already-parsed file (see templateService.importSlides),
  // with no AI generation step — its slides are filled right after via syncSlidePages.
  async createImported(name, templateId) {
    const response = await apiClient.post('/document/projects/import', { name, templateId });
    return normalizeApiResponse(response.data);
  },

  // AI đọc chủ đề và đề xuất màu sắc, phong cách cho template; null nếu AI không phản hồi.
  async themeBrief(subject) {
    try {
      const response = await apiClient.post('/document/theme-brief', { subject }, { timeout: 35000 });
      const data = normalizeApiResponse(response.data);
      return data?.ok ? data.brief : null;
    } catch {
      return null;
    }
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

  async getProjectImage(projectId, url) {
    const response = await apiClient.get(`/document/projects/${projectId}/image-proxy`, {
      params: { url },
      responseType: 'blob',
    });
    return response.data;
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

  async updateVideo(projectId, updates) {
    const response = await apiClient.post(`/document/projects/${projectId}/videos/current`, updates);
    return normalizeApiResponse(response.data);
  },

  async getCurrentVideo(projectId) {
    const response = await apiClient.get(`/document/projects/${projectId}/videos/current`);
    return normalizeApiResponse(response.data);
  },

  async getVideos(projectId) {
    const response = await apiClient.get(`/document/projects/${projectId}/videos`);
    return normalizeApiResponse(response.data);
  },

  async deleteVideo(projectId, videoId) {
    const response = await apiClient.delete(`/document/projects/${projectId}/videos/${videoId}`);
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
