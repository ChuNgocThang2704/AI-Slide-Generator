import apiClient from './apiClient';

const unwrap = (response) => {
  const payload = response?.data;
  if (payload?.code && payload.code !== 200) {
    throw new Error(payload.message || 'Không thể xử lý template');
  }
  return typeof payload?.data === 'undefined' ? payload : payload.data;
};

export const templateService = {
  async getAll() {
    const response = await apiClient.get('/template/get-all', {
      params: { page: 0, size: 100 },
    });
    const page = unwrap(response);
    return page?.items || page?.content || [];
  },

  async uploadCustom(file, name = '') {
    const formData = new FormData();
    formData.append('file', file);
    if (name.trim()) formData.append('name', name.trim());
    const response = await apiClient.post('/template/custom', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return unwrap(response);
  },

  // Saves a prompt-generated template (its whole design is the short code) to the user's library.
  async saveGenerated(name, code) {
    const response = await apiClient.post('/template/custom/generated', { name, code });
    return unwrap(response);
  },

  // Reads the template's original file again with the current reader, so a template uploaded before
  // a fix picks the fix up.
  async reparseCustom(templateId) {
    const response = await apiClient.post(`/template/custom/${templateId}/reparse`);
    return unwrap(response);
  },

  async deleteCustom(templateId) {
    const response = await apiClient.delete(`/template/custom/${templateId}`);
    return unwrap(response);
  },

  // Parses a real .pptx into slides ready to open for editing (not just a reusable style):
  // each returned layout is a faithful 1-to-1 copy of that file's own slide, real text kept.
  async importSlides(file) {
    const formData = new FormData();
    formData.append('file', file);
    const response = await apiClient.post('/template/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return unwrap(response);
  },

  async match(templateId, slide) {
    const response = await apiClient.post(`/template/${templateId}/match`, {
      title: slide.title || '',
      bullets: Array.isArray(slide.bullets) ? slide.bullets : [],
      imageUrl: slide.imageUrl || '',
      layout: slide.layout || slide.type || '',
      chart: slide.chart || null,
      table: slide.table || null,
      pageIndex: slide.pageIndex ?? null,
    });
    return unwrap(response);
  },
};

export const isCustomTemplateId = (value) => (
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(String(value || ''))
);
