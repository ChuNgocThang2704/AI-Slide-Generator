import { useEffect, useRef, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  FileVideo2,
  Loader2,
  Mic2,
  RotateCcw,
  Square,
  Upload,
  UserRound,
  Video,
  X,
} from 'lucide-react';
import { getVideoApiError, videoGenerationService } from '../../services/videoGenerationService';
import './VideoGenerationModal.css';

const DEFAULT_VOICE = {
  gender: 'female',
  area: 'northern',
  group: 'audiobook',
  emotion: 'neutral',
};

export default function VideoGenerationModal({
  open,
  onClose,
  slides,
  projectName,
  onPreparePresentation,
  onNotify,
}) {
  const [phase, setPhase] = useState('setup');
  const [loadingOptions, setLoadingOptions] = useState(false);
  const [presenters, setPresenters] = useState([]);
  const [selectedPresenterUrl, setSelectedPresenterUrl] = useState('');
  const [customPresenter, setCustomPresenter] = useState(null);
  const [currentUser, setCurrentUser] = useState(null);
  const [voice, setVoice] = useState(DEFAULT_VOICE);
  const [error, setError] = useState('');
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState('');
  const [currentSlide, setCurrentSlide] = useState(0);
  const [resultUrl, setResultUrl] = useState('');
  const [temporaryVideoUrl, setTemporaryVideoUrl] = useState('');
  const abortRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;

    const controller = new AbortController();
    const loadTimer = window.setTimeout(() => {
      setError('');
      setLoadingOptions(true);

      if (!videoGenerationService.hasSession()) {
        setError('Phiên đăng nhập Gen Video chưa sẵn sàng. Vui lòng đăng nhập lại GenSlide.');
        setLoadingOptions(false);
        return;
      }

      Promise.all([
        videoGenerationService.getCurrentUser(controller.signal),
        videoGenerationService.getPresenterVideos(controller.signal),
      ])
        .then(([user, presenterList]) => {
          setCurrentUser(user);
          setPresenters(presenterList);
          setSelectedPresenterUrl((current) => current || presenterList[0]?.video_url || '');
        })
        .catch((loadError) => {
          if (loadError?.code !== 'ERR_CANCELED') {
            setError(getVideoApiError(loadError, 'Không tải được cấu hình Gen Video'));
          }
        })
        .finally(() => setLoadingOptions(false));
    }, 0);

    return () => {
      window.clearTimeout(loadTimer);
      controller.abort();
    };
  }, [open]);

  const resetResult = () => {
    setPhase('setup');
    setProgress(0);
    setStatus('');
    setCurrentSlide(0);
    setResultUrl('');
    setTemporaryVideoUrl('');
    setError('');
  };

  const handleClose = () => {
    if (phase === 'processing') return;
    resetResult();
    onClose();
  };

  const stopGeneration = () => {
    abortRef.current?.abort();
  };

  const retryPersistVideo = async () => {
    if (!temporaryVideoUrl || !currentUser) {
      setError('Không còn đường dẫn video tạm để lưu lại.');
      return;
    }

    const controller = new AbortController();
    abortRef.current = controller;
    setPhase('processing');
    setError('');
    setProgress(95);
    setCurrentSlide(slides.length);
    setStatus('Đang thử lưu lại video vào thư viện...');

    try {
      const persistentUrl = await videoGenerationService.persistVideo(
        temporaryVideoUrl,
        currentUser,
        controller.signal,
      );
      setResultUrl(persistentUrl);
      setProgress(100);
      setStatus('Video đã hoàn thành');
      setPhase('result');
      onNotify?.('Đã lưu video vào thư viện!', 'success');
    } catch (persistError) {
      const message = getVideoApiError(persistError, 'Không thể lưu video vào thư viện');
      setError(message);
      setStatus('Video đã tạo xong nhưng chưa được lưu');
      setPhase('save-error');
      onNotify?.(`Video đã tạo xong nhưng chưa lưu: ${message}`, 'error');
    } finally {
      abortRef.current = null;
    }
  };

  const startGeneration = async () => {
    if (!currentUser) {
      setError('Không lấy được thông tin người dùng Gen Video. Vui lòng đăng nhập lại.');
      return;
    }
    if (!selectedPresenterUrl && !customPresenter) {
      setError('Vui lòng chọn hoặc tải lên video người thuyết trình.');
      return;
    }
    const controller = new AbortController();
    abortRef.current = controller;
    setPhase('processing');
    setError('');
    setProgress(2);
    setCurrentSlide(0);
    setResultUrl('');
    setTemporaryVideoUrl('');

    let completedVideoUrl = '';

    try {
      setStatus('Đang lưu và dựng file trình chiếu...');
      const { blob, textBlob, fileName } = await onPreparePresentation();

      setProgress(7);
      setStatus('Đang chuyển slide sang dịch vụ Gen Video...');
      const uploadResult = await videoGenerationService.uploadPresentation(
        blob,
        fileName || projectName,
        controller.signal,
      );
      const renderedSlides = uploadResult?.slides || [];
      if (!uploadResult?.success || !renderedSlides.length) {
        throw new Error('Gen Video không render được file trình chiếu');
      }

      setProgress(10);
      setStatus('Đang phân tích và tạo lời thuyết minh cho từng slide...');
      const textResult = await videoGenerationService.extractPresentationText(
        textBlob || blob,
        fileName || projectName,
        controller.signal,
      );
      const generatedNarrations = textResult?.slides_text || [];
      if (!textResult?.success || !generatedNarrations.length) {
        throw new Error('Gen Video không tạo được lời thuyết minh từ nội dung slide');
      }

      let presenterUrl = selectedPresenterUrl;
      if (customPresenter) {
        setProgress(12);
        setStatus('Đang tải video người thuyết trình...');
        presenterUrl = await videoGenerationService.uploadPresenterVideo(customPresenter, controller.signal);
      }
      if (!presenterUrl) throw new Error('Không nhận được video người thuyết trình');

      const slideJobs = slides.map((_, index) => {
        const generatedText = generatedNarrations.find(
          (item) => Number(item.slide_number) === index,
        ) || generatedNarrations[index];
        const narration = String(
          generatedText?.rewritten_content || generatedText?.content || '',
        ).trim();
        const renderedSlide = renderedSlides.find(
          (item) => Number(item.slide_number) === index,
        ) || renderedSlides[index];

        return { index, narration, renderedSlide };
      }).filter((job) => job.narration && job.renderedSlide?.image_url);

      if (!slideJobs.length) {
        throw new Error('Không có slide hợp lệ để tạo lời thuyết minh');
      }

      const composedUrls = [];
      const totalOperations = slideJobs.length * 3;
      let completedOperations = 0;

      for (const { index, narration, renderedSlide } of slideJobs) {
        setCurrentSlide(index + 1);
        setStatus(`Đang tạo giọng đọc cho slide ${index + 1}/${slides.length}...`);
        const audioUrl = await videoGenerationService.generateSpeech({
          text: narration,
          ...voice,
        }, controller.signal);
        if (!audioUrl) throw new Error(`Không tạo được giọng đọc cho slide ${index + 1}`);
        completedOperations += 1;
        setProgress(14 + Math.round((completedOperations / totalOperations) * 70));

        setStatus(`Đang đồng bộ người thuyết trình ở slide ${index + 1}/${slides.length}...`);
        const lipVideoUrl = await videoGenerationService.createLipVideo(
          audioUrl,
          presenterUrl,
          controller.signal,
        );
        if (!lipVideoUrl) throw new Error(`Không tạo được video thuyết trình cho slide ${index + 1}`);
        completedOperations += 1;
        setProgress(14 + Math.round((completedOperations / totalOperations) * 70));

        setStatus(`Đang ghép hình ảnh slide ${index + 1}/${slides.length}...`);
        const composedUrl = await videoGenerationService.combineSlide(
          renderedSlide.image_url,
          lipVideoUrl,
          controller.signal,
        );
        if (!composedUrl) throw new Error(`Không ghép được slide ${index + 1}`);
        composedUrls.push(composedUrl);
        completedOperations += 1;
        setProgress(14 + Math.round((completedOperations / totalOperations) * 70));
      }

      if (!composedUrls.length) throw new Error('Không có slide hợp lệ để ghép video');

      setProgress(88);
      setStatus('Đang nối các slide thành video hoàn chỉnh...');
      completedVideoUrl = await videoGenerationService.concatVideos(composedUrls, controller.signal);
      if (!completedVideoUrl) throw new Error('Không nối được video hoàn chỉnh');
      setTemporaryVideoUrl(completedVideoUrl);

      setProgress(95);
      setStatus('Đang lưu video vào thư viện...');
      const persistentUrl = await videoGenerationService.persistVideo(
        completedVideoUrl,
        currentUser,
        controller.signal,
      );

      setResultUrl(persistentUrl);
      setProgress(100);
      setStatus('Video đã hoàn thành');
      setPhase('result');
      onNotify?.('Sinh video thành công!', 'success');
    } catch (generationError) {
      const message = getVideoApiError(generationError);
      setError(message);
      if (completedVideoUrl) {
        setStatus('Video đã tạo xong nhưng chưa được lưu');
        setProgress(95);
        setCurrentSlide(slides.length);
        setPhase('save-error');
      } else {
        setPhase('setup');
        setStatus('');
        setProgress(0);
      }
      if (generationError?.code !== 'ERR_CANCELED') {
        onNotify?.(completedVideoUrl ? `Video đã tạo xong nhưng chưa lưu: ${message}` : message, 'error');
      }
    } finally {
      abortRef.current = null;
    }
  };

  if (!open) return null;

  return (
    <div className="video-gen-overlay" role="presentation">
      <section className="video-gen-dialog" role="dialog" aria-modal="true" aria-labelledby="video-gen-title">
        <header className="video-gen-header">
          <div className="video-gen-title-wrap">
            <span className="video-gen-title-icon"><Video size={19} /></span>
            <div>
              <h2 id="video-gen-title">Sinh video thuyết trình</h2>
              <span>{projectName} · {slides.length} slide</span>
            </div>
          </div>
          <button type="button" className="video-gen-icon-btn" onClick={handleClose} disabled={phase === 'processing'} aria-label="Đóng">
            <X size={18} />
          </button>
        </header>

        {phase === 'setup' && (
          <div className="video-gen-body">
            {error && <div className="video-gen-alert"><AlertTriangle size={17} /><span>{error}</span></div>}

            <div className="video-gen-section-heading">
              <UserRound size={17} />
              <div><strong>Người thuyết trình</strong><span>Chọn một video đại diện</span></div>
            </div>

            {loadingOptions ? (
              <div className="video-gen-loading"><Loader2 size={20} className="spin" /> Đang tải lựa chọn...</div>
            ) : (
              <div className="video-gen-presenters">
                {presenters.map((presenter) => (
                  <button
                    key={presenter.id}
                    type="button"
                    className={`video-gen-presenter ${!customPresenter && selectedPresenterUrl === presenter.video_url ? 'selected' : ''}`}
                    onClick={() => { setCustomPresenter(null); setSelectedPresenterUrl(presenter.video_url); }}
                  >
                    <video src={presenter.video_url} muted preload="metadata" />
                    <span>{presenter.name}</span>
                    {!customPresenter && selectedPresenterUrl === presenter.video_url && <CheckCircle2 size={16} />}
                  </button>
                ))}
                <label className={`video-gen-upload ${customPresenter ? 'selected' : ''}`}>
                  <input
                    type="file"
                    accept="video/*"
                    onChange={(event) => {
                      const file = event.target.files?.[0] || null;
                      setCustomPresenter(file);
                      if (file) setSelectedPresenterUrl('');
                    }}
                  />
                  <Upload size={20} />
                  <span>{customPresenter ? customPresenter.name : 'Tải video lên'}</span>
                </label>
              </div>
            )}

            <div className="video-gen-section-heading video-gen-voice-heading">
              <Mic2 size={17} />
              <div><strong>Giọng đọc</strong><span>Lời thuyết minh được tạo tự động từ nội dung slide</span></div>
            </div>

            <div className="video-gen-controls">
              <label>Giới tính
                <select value={voice.gender} onChange={(event) => setVoice({ ...voice, gender: event.target.value })}>
                  <option value="female">Nữ</option>
                  <option value="male">Nam</option>
                </select>
              </label>
              <label>Vùng giọng
                <select value={voice.area} onChange={(event) => setVoice({ ...voice, area: event.target.value })}>
                  <option value="northern">Miền Bắc</option>
                  <option value="southern">Miền Nam</option>
                </select>
              </label>
              <label>Phong cách
                <select value={voice.group} onChange={(event) => setVoice({ ...voice, group: event.target.value })}>
                  <option value="audiobook">Thuyết minh</option>
                  <option value="interview">Phỏng vấn</option>
                </select>
              </label>
              <label>Cảm xúc
                <select value={voice.emotion} onChange={(event) => setVoice({ ...voice, emotion: event.target.value })}>
                  <option value="neutral">Trung tính</option>
                  <option value="serious">Nghiêm túc</option>
                </select>
              </label>
            </div>
          </div>
        )}

        {phase === 'processing' && (
          <div className="video-gen-process">
            <div className="video-gen-process-icon"><Loader2 size={30} className="spin" /></div>
            <h3>Đang sinh video</h3>
            <p>{status}</p>
            <div className="video-gen-progress"><span style={{ width: `${progress}%` }} /></div>
            <div className="video-gen-progress-meta">
              <span>{currentSlide ? `Slide ${currentSlide}/${slides.length}` : 'Đang chuẩn bị'}</span>
              <strong>{progress}%</strong>
            </div>
            <button type="button" className="btn btn-ghost btn-sm" onClick={stopGeneration}><Square size={14} /> Dừng</button>
          </div>
        )}

        {phase === 'result' && (
          <div className="video-gen-result">
            <div className="video-gen-result-title"><CheckCircle2 size={22} /><div><h3>Video đã hoàn thành</h3><span>Đã lưu vào thư viện Gen Video</span></div></div>
            <video src={resultUrl} controls preload="metadata" />
          </div>
        )}

        {phase === 'save-error' && (
          <div className="video-gen-result video-gen-save-error">
            <div className="video-gen-result-title"><AlertTriangle size={22} /><div><h3>Video đã tạo xong</h3><span>Chưa thể lưu vào thư viện Gen Video</span></div></div>
            <div className="video-gen-alert"><AlertTriangle size={17} /><span>{error}</span></div>
            <video src={temporaryVideoUrl} controls preload="metadata" />
            <p className="video-gen-save-hint">Bạn có thể mở video tạm ngay hoặc thử lưu lại mà không cần sinh lại các slide.</p>
          </div>
        )}

        <footer className="video-gen-footer">
          {phase === 'setup' && (
            <>
              <button type="button" className="btn btn-ghost btn-sm" onClick={handleClose}>Hủy</button>
              <button type="button" className="btn btn-primary btn-sm" onClick={startGeneration} disabled={loadingOptions || !currentUser || (!selectedPresenterUrl && !customPresenter)}>
                <FileVideo2 size={15} /> Sinh video
              </button>
            </>
          )}
          {phase === 'result' && (
            <>
              <button type="button" className="btn btn-ghost btn-sm" onClick={resetResult}><RotateCcw size={15} /> Tạo lại</button>
              <a className="btn btn-primary btn-sm" href={resultUrl} target="_blank" rel="noreferrer"><Download size={15} /> Mở video</a>
            </>
          )}
          {phase === 'save-error' && (
            <>
              <button type="button" className="btn btn-ghost btn-sm" onClick={handleClose}>Đóng</button>
              <a className="btn btn-ghost btn-sm" href={temporaryVideoUrl} target="_blank" rel="noreferrer"><Download size={15} /> Mở video tạm</a>
              <button type="button" className="btn btn-primary btn-sm" onClick={retryPersistVideo}><RotateCcw size={15} /> Thử lưu lại</button>
            </>
          )}
        </footer>
      </section>
    </div>
  );
}
