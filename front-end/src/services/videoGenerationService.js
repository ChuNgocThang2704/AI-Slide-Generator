import axios from 'axios';
import { useAuthStore } from '../store';
import { lecgenService } from './lecgenService';

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

function isTransientVideoError(error) {
  const status = Number(error?.response?.status || 0);
  return !error?.response || [502, 503, 504].includes(status);
}

function waitBeforeRetry(attempt, signal) {
  return new Promise((resolve, reject) => {
    const timer = window.setTimeout(resolve, 1200 * attempt);
    signal?.addEventListener('abort', () => {
      window.clearTimeout(timer);
      reject(new axios.CanceledError('Đã dừng quá trình sinh video'));
    }, { once: true });
  });
}

async function retryTransient(operation, signal, maxAttempts = 3) {
  let lastError;
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    try {
      return await operation();
    } catch (error) {
      lastError = error;
      if (signal?.aborted || !isTransientVideoError(error) || attempt === maxAttempts) throw error;
      await waitBeforeRetry(attempt, signal);
    }
  }
  throw lastError;
}

export function getVideoApiError(error, fallback = 'Không thể kết nối dịch vụ sinh video') {
  if (error?.name === 'CanceledError' || error?.code === 'ERR_CANCELED') {
    return 'Đã dừng quá trình sinh video';
  }
  const message = error?.response?.data?.detail
    || error?.response?.data?.message
    || error?.message
    || fallback;
  const exposesImplementation = /deep[- ]?live|wav2lip|tts|vllm|qwen|gemini|vertex|flux|cuda|pytorch|traceback|stderr/i.test(String(message));
  return exposesImplementation ? fallback : message;
}

export const videoGenerationService = {
  hasSession() {
    return Boolean(localStorage.getItem('lecgen_token'));
  },

  async ensureSession() {
    let token = localStorage.getItem('lecgen_token');
    if (token) return true;

    const email = useAuthStore.getState()?.user?.email;
    if (!email) return false;

    const defaultPassword = '21122004';
    try {
      console.log('⚡ [GenVideo] Tự động đồng bộ phiên LecGen cho:', email);
      try {
        await lecgenService.loginLecgen(email, defaultPassword);
      } catch {
        try {
          await lecgenService.registerLecgen(email, defaultPassword);
          await lecgenService.loginLecgen(email, defaultPassword);
        } catch (regErr) {
          console.warn('⚠️ [GenVideo Auto-sync Failed]:', regErr);
        }
      }
    } catch (e) {
      console.warn('⚠️ [GenVideo Session Error]:', e);
    }

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

  async uploadFaceImage(file, signal) {
    const formData = new FormData();
    formData.append('file', file);
    const response = await videoApiClient.post(
      '/uploaded-images/upload-source-image',
      formData,
      requestConfig(signal),
    );
    return response.data?.image_url;
  },

  async uploadVoiceSample(file, signal) {
    const formData = new FormData();
    formData.append('file', file);
    const response = await videoApiClient.post(
      '/media/upload-audio',
      formData,
      requestConfig(signal),
    );
    return response.data?.audio_url;
  },

  async createDeepfake(sourceImageUrl, presenterVideoUrl, signal) {
    const response = await videoApiClient.post('/upload/process-deepfake', {
      source_url: sourceImageUrl,
      target_url: presenterVideoUrl,
    }, requestConfig(signal, {
      headers: { 'Content-Type': 'application/json' },
    }));
    return response.data?.job_id;
  },

  async waitForDeepfake(jobId, signal, onStatus) {
    if (!jobId) throw new Error('Không nhận được mã tác vụ ghép mặt');

    const startedAt = Date.now();
    const timeoutMs = 2 * 60 * 60 * 1000;
    while (Date.now() - startedAt < timeoutMs) {
      if (signal?.aborted) throw new axios.CanceledError('Đã dừng quá trình sinh video');

      const response = await videoApiClient.get(
        `/media/deepfake-status/${jobId}`,
        requestConfig(signal),
      );
      const data = response.data || {};
      const status = String(data.status || 'processing').toLowerCase();
      onStatus?.(status);

      if ((status === 'completed' || status === 'done') && data.result_url) {
        return data.result_url;
      }
      if (status === 'error' || status === 'failed') {
        throw new Error(data.message || 'Không thể ghép khuôn mặt vào video');
      }

      await new Promise((resolve, reject) => {
        const timer = window.setTimeout(resolve, 5000);
        signal?.addEventListener('abort', () => {
          window.clearTimeout(timer);
          reject(new axios.CanceledError('Đã dừng quá trình sinh video'));
        }, { once: true });
      });
    }

    throw new Error('Ghép mặt quá thời gian chờ');
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
    const sourceResponse = await retryTransient(async () => {
      const response = await fetch(sourceUrl, { signal });
      if (!response.ok) {
        const error = new Error('Không thể tải video kết quả để lưu trữ');
        error.response = { status: response.status };
        throw error;
      }
      return response;
    }, signal);

    const videoBlob = await sourceResponse.blob();
    const formData = new FormData();
    formData.append('file', videoBlob, `genslide-${Date.now()}.mp4`);
    const uploadResponse = await retryTransient(
      () => videoApiClient.post('/upload/upload-video', formData, requestConfig(signal)),
      signal,
    );
    const persistentUrl = uploadResponse.data?.video_url;
    if (!persistentUrl) throw new Error('Không nhận được URL lưu trữ video');

    await retryTransient(
      () => videoApiClient.post('/videos/', {
        video_url: persistentUrl,
        username: currentUser.username,
        user_id: currentUser.id,
      }, requestConfig(signal, {
        headers: { 'Content-Type': 'application/json' },
      })),
      signal,
    );

    return persistentUrl;
  },
};
