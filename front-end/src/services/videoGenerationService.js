import axios from 'axios';

const LECGEN_API_URL = import.meta.env.VITE_LECGEN_API_URL
  || (import.meta.env.DEV ? '/lecgen-api/api/v1' : 'https://lecgen.aitc.vn/api/v1');

const videoApiClient = axios.create({
  baseURL: LECGEN_API_URL,
  timeout: 10 * 60 * 1000,
  headers: {
    Accept: 'application/json, text/plain, */*',
  },
});

function authHeaders() {
  const token = localStorage.getItem('lecgen_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function requestConfig(signal, extra = {}) {
  return {
    ...extra,
    signal,
    headers: {
      ...authHeaders(),
      ...(extra.headers || {}),
    },
  };
}

export function getVideoApiError(error, fallback = 'Không thể kết nối dịch vụ sinh video') {
  if (error?.name === 'CanceledError' || error?.code === 'ERR_CANCELED') {
    return 'Đã dừng quá trình sinh video';
  }
  return error?.response?.data?.detail
    || error?.response?.data?.message
    || error?.message
    || fallback;
}

export const videoGenerationService = {
  hasSession() {
    return Boolean(localStorage.getItem('lecgen_token'));
  },

  async getCurrentUser(signal) {
    const response = await videoApiClient.get('/users/me', requestConfig(signal));
    return response.data;
  },

  async getPresenterVideos(signal) {
    const response = await videoApiClient.get('/media-videos/', requestConfig(signal, {
      params: { video_type: 'sample' },
    }));
    return response.data?.videos || [];
  },

  async getMyVideos(signal) {
    const response = await videoApiClient.get('/videos/my-videos', requestConfig(signal));
    return {
      videos: response.data?.videos || [],
      total: Number(response.data?.total || 0),
    };
  },

  async deleteVideo(videoId, signal) {
    await videoApiClient.delete(`/videos/${videoId}`, requestConfig(signal));
  },

  async uploadPresentation(pptxBlob, fileName, signal) {
    const formData = new FormData();
    formData.append('file', pptxBlob, `${fileName || 'presentation'}.pptx`);
    const response = await videoApiClient.post('/media/upload-pptx2', formData, requestConfig(signal));
    return response.data;
  },

  async extractPresentationText(pptxBlob, fileName, signal) {
    const formData = new FormData();
    formData.append('file', pptxBlob, `${fileName || 'presentation'}.pptx`);
    const response = await videoApiClient.post('/media/extract-pptx-text', formData, requestConfig(signal));
    return response.data;
  },

  async uploadPresenterVideo(file, signal) {
    const formData = new FormData();
    formData.append('file', file);
    const response = await videoApiClient.post('/upload/upload-video', formData, requestConfig(signal));
    return response.data?.video_url;
  },

  async generateSpeech(payload, signal) {
    const response = await videoApiClient.post('/upload/process-tts', payload, requestConfig(signal, {
      headers: { 'Content-Type': 'application/json' },
    }));
    return response.data?.audio_file_url;
  },

  async createLipVideo(audioUrl, presenterVideoUrl, signal) {
    const response = await videoApiClient.post('/upload/process-fakelip', {
      audio_url: audioUrl,
      video_url: presenterVideoUrl,
    }, requestConfig(signal, {
      headers: { 'Content-Type': 'application/json' },
    }));
    return response.data?.result_url;
  },

  async combineSlide(slideImageUrl, lipVideoUrl, signal) {
    const response = await videoApiClient.post('/media/combine-slide', {
      image_url: slideImageUrl,
      video_url: lipVideoUrl,
    }, requestConfig(signal, {
      headers: { 'Content-Type': 'application/json' },
    }));
    return response.data?.result_url;
  },

  async concatVideos(videoUrls, signal) {
    const response = await videoApiClient.post('/media/concat-videos', {
      videos: videoUrls,
    }, requestConfig(signal, {
      headers: { 'Content-Type': 'application/json' },
    }));
    return response.data?.result_url;
  },

  async persistVideo(sourceUrl, currentUser, signal) {
    const sourceResponse = await fetch(sourceUrl, { signal });
    if (!sourceResponse.ok) throw new Error('Không thể tải video kết quả để lưu trữ');

    const videoBlob = await sourceResponse.blob();
    const formData = new FormData();
    formData.append('file', videoBlob, `genslide-${Date.now()}.mp4`);
    const uploadResponse = await videoApiClient.post('/upload/upload-video', formData, requestConfig(signal));
    const persistentUrl = uploadResponse.data?.video_url;
    if (!persistentUrl) throw new Error('Không nhận được URL lưu trữ video');

    await videoApiClient.post('/videos/', {
      video_url: persistentUrl,
      username: currentUser.username,
      user_id: currentUser.id,
    }, requestConfig(signal, {
      headers: { 'Content-Type': 'application/json' },
    }));

    return persistentUrl;
  },
};
