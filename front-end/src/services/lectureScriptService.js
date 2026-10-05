import apiClient from './apiClient';

const unwrap = (response) => {
  const body = response?.data;
  if (!body) throw new Error('Không nhận được phản hồi từ máy chủ');
  if (body.code && body.code !== 200) throw new Error(body.message || 'Yêu cầu thất bại');
  return typeof body.data !== 'undefined' ? body.data : body;
};

const wait = (ms) => new Promise((resolve) => { setTimeout(resolve, ms); });

// Lecture script for an uploaded deck. Nothing is stored on the server: the page keeps the
// script and the slide texts it was written from, and sends them back to rewrite or export.
export const lectureScriptService = {
  async start(file, prompt, firstVideo = false) {
    const form = new FormData();
    form.append('file', file);
    form.append('prompt', prompt || '');
    form.append('firstVideo', firstVideo ? 'true' : 'false');
    return unwrap(await apiClient.post('/document/lecture-script', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120000,
    }));
  },

  async revise({ slides, rows, prompt, filename }) {
    return unwrap(await apiClient.post('/document/lecture-script/revise', { slides, rows, prompt, filename }, { timeout: 60000 }));
  },

  /** English subtitle lines for Vietnamese scripts: [string] -> task; its result is {items: [{i, en}], failed: [i]}. */
  async translate(scripts) {
    return unwrap(await apiClient.post('/document/lecture-script/translate', { scripts }, { timeout: 60000 }));
  },

  /** Resolves with {script, slides} once the task is done; `onProgress` gets 0-100 on the way. */
  async waitFor(taskId, onProgress, isCancelled = () => false) {
    for (let attempt = 0; attempt < 240; attempt += 1) {
      if (isCancelled()) throw new Error('cancelled');
      const state = unwrap(await apiClient.get(`/document/lecture-script/status/${taskId}`, { timeout: 30000 }));
      if (state.status === 'completed') return state.result;
      if (state.status === 'error' || state.status === 'cancelled' || state.status === 'not_found') {
        throw new Error(state.result?.message || 'Không tạo được kịch bản. Hãy thử lại.');
      }
      onProgress?.(Number(state.progress) || 0);
      await wait(1500);
    }
    throw new Error('Quá thời gian chờ. Hãy thử lại.');
  },

  // Saved sets: the scripts of one sitting (a chapter's videos), kept so they can be reopened.
  async listSets() {
    return unwrap(await apiClient.get('/document/lecture-script/sets', { timeout: 30000 }));
  },

  async getSet(id) {
    return unwrap(await apiClient.get(`/document/lecture-script/sets/${id}`, { timeout: 60000 }));
  },

  /** Creates the set when `id` is empty, otherwise replaces it; answers with its list row. */
  async saveSet(id, { name, prompt, items }) {
    const body = { name, prompt, items };
    return unwrap(id
      ? await apiClient.put(`/document/lecture-script/sets/${id}`, body, { timeout: 60000 })
      : await apiClient.post('/document/lecture-script/sets', body, { timeout: 60000 }));
  },

  async deleteSet(id) {
    return unwrap(await apiClient.delete(`/document/lecture-script/sets/${id}`, { timeout: 30000 }));
  },

  /** One workbook with a sheet per script: [{title, sheet, durationMinutes, rows}]. */
  async exportXlsx(sheets) {
    const response = await apiClient.post(
      '/document/lecture-script/export',
      {
        sheets: sheets.map((item) => ({
          title: item.title,
          sheet: item.sheet,
          duration_minutes: item.durationMinutes,
          rows: item.rows.map((row) => ({ ...row, en: item.withEnglish ? (row.en || '') : '' })),
        })),
      },
      { responseType: 'blob', timeout: 90000 },
    );
    return response.data;
  },
};
