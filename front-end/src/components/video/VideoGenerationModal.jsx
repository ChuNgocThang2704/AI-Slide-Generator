import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';

// Module-level map: persists AbortControllers across modal mount/unmount
const jobControllers = new Map();
const remoteSyncQueues = new Map();
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  FileVideo2,
  ImagePlus,
  LayoutDashboard,
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
import { projectService } from '../../services/documentService';
import { useVideoGenStore } from '../../store';
import './VideoGenerationModal.css';

const DEFAULT_VOICE = {
  gender: 'female',
  area: 'northern',
  group: 'audiobook',
  emotion: 'neutral',
};

function getSlideNoteText(slide) {
  if (!slide) return '';
  const rawNote = slide.notes || slide.speakerNotes || slide.speaker_notes || slide.note;
  if (typeof rawNote === 'string' && rawNote.trim().length > 0) return rawNote.trim();
  if (Array.isArray(rawNote) && rawNote.length > 0) return rawNote.join('. ').trim();
  return '';
}

function getSlideApiItem(items, slideIndex) {
  if (!Array.isArray(items) || slideIndex < 0) return undefined;
  const numberedItems = items.filter((item) => Number.isFinite(Number(item?.slide_number)));
  if (!numberedItems.length) return items[slideIndex];

  // LecGen endpoints are not guaranteed to use the same convention. Detect
  // zero-based responses by the presence of slide_number 0; otherwise treat
  // the response as one-based and map it back to the editor index.
  const isZeroBased = numberedItems.some((item) => Number(item.slide_number) === 0);
  const expectedNumber = isZeroBased ? slideIndex : slideIndex + 1;
  return numberedItems.find((item) => Number(item.slide_number) === expectedNumber)
    || items[slideIndex];
}

function isVietnameseNarration(text) {
  const normalized = ` ${String(text || '').toLocaleLowerCase('vi-VN')} `;
  const diacritics = (normalized.match(/[ăâđêôơưáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ]/g) || []).length;
  const commonWords = (normalized.match(/\b(?:và|là|của|trong|được|với|cho|các|một|những|bài|phần|người|học|này|chúng ta)\b/g) || []).length;
  return diacritics >= 2 || commonWords >= 3;
}

const VIETNAMESE_LETTER_NAMES = {
  A: 'ây', B: 'bi', C: 'xi', D: 'đi', E: 'i', F: 'ép', G: 'gi', H: 'âych',
  I: 'ai', J: 'giây', K: 'cây', L: 'eo', M: 'em', N: 'en', O: 'âu', P: 'pi',
  Q: 'kiu', R: 'a', S: 'ét', T: 'ti', U: 'diu', V: 'vi', W: 'đắp bờ liu',
  X: 'ích', Y: 'oai', Z: 'di',
};

// These abbreviations are commonly pronounced as words. Spelling every
// letter would make the Vietnamese narration less natural.
const SPOKEN_AS_WORD_ACRONYMS = new Set([
  'ASEAN', 'COVID', 'LASER', 'NATO', 'NASA', 'RADAR', 'SCUBA', 'SMART',
  'STEAM', 'STEM', 'SWOT', 'UNESCO', 'UNICEF',
]);

function spellUnknownVietnameseAcronyms(text) {
  return text.replace(/\b[A-Z]{2,6}\b/g, (token) => {
    if (SPOKEN_AS_WORD_ACRONYMS.has(token)) return token;
    return [...token].map((letter) => VIETNAMESE_LETTER_NAMES[letter] || letter).join(' ');
  });
}

const VIETNAMESE_DIGIT_NAMES = ['không', 'một', 'hai', 'ba', 'bốn', 'năm', 'sáu', 'bảy', 'tám', 'chín'];

function normalizeVietnameseDecimals(text) {
  // Scores and versions commonly use one or two decimal digits. Keeping
  // three-digit groups untouched avoids reading 1.000 as "một chấm không...".
  return text.replace(/\b(\d+)[.,](\d{1,2})\b/g, (_, integer, fraction) => {
    const spokenFraction = [...fraction]
      .map((digit) => VIETNAMESE_DIGIT_NAMES[Number(digit)])
      .join(' ');
    return `${integer} chấm ${spokenFraction}`;
  });
}

/**
 * Làm sạch ghi chú slide trước khi gửi cho TTS engine.
 * Loại bỏ Markdown, chuẩn hóa số, viết tắt và dấu câu để AI đọc mượt mà hơn.
 */
function sanitizeNoteForTTS(text, slideIndex = 0) {
  if (!text) return '';
  let t = text;

  // 1. Xóa Markdown formatting
  t = t.replace(/\*\*(.+?)\*\*/g, '$1');   // **bold**
  t = t.replace(/\*(.+?)\*/g, '$1');       // *italic*
  t = t.replace(/__(.+?)__/g, '$1');       // __bold__
  t = t.replace(/_(.+?)_/g, '$1');         // _italic_
  t = t.replace(/#{1,6}\s*/g, '');         // # Headings
  t = t.replace(/^[-*•]\s+/gm, '');       // bullet points
  t = t.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1'); // [link](url)
  t = t.replace(/`([^`]+)`/g, '$1');       // keep text inside `code`

  // 2. Nếu từ slide 2 trở đi (slideIndex > 0), loại bỏ câu chào mở đầu lặp lại
  if (slideIndex > 0) {
    t = t.replace(/^(?:Xin\s+chào|Chào\s+mừng|Chào\s+các\s+bạn|Hello|Welcome)[^.!?]*[.!?]\s*/i, '');
    t = t.replace(/^(?:Trong\s+buổi\s+học\s+hôm\s+nay|Ở\s+bài\s+học\s+này)[^.!?]*[.!?]\s*/i, '');
  }

  // Remove unresolved author/speaker placeholders. Keeping their inner text
  // would make TTS literally read "Tên giảng viên" to the audience.
  t = t.replace(
    /\[(?:tên\s+)?(?:giảng\s+viên|người\s+trình\s+bày|tổ\s+chức|đơn\s+vị|speaker|presenter|organization|author)[^\]]*\]/gi,
    '',
  );

  const vietnamese = isVietnameseNarration(t);

  // Convert complete concepts, not individual foreign letters. This produces
  // natural narration while leaving the visible speaker notes untouched.
  const vietnameseTermMap = [
    [/\b(?:kỳ|bài)\s+thi\s+IELTS\b/gi, 'kỳ thi ai eo'],
    [/\bIELTS\s+Speaking\b/gi, 'kỹ năng nói trong kỳ thi ai eo'],
    [/\bIELTS\b/gi, 'ai eo'],
    [/\bSpeaking\s+Part\s+(?:1|one|một)\b/gi, 'phần một của bài thi nói'],
    [/\bSpeaking\s+Part\s+(?:2|two|hai)\b/gi, 'phần hai của bài thi nói'],
    [/\bSpeaking\s+Part\s+(?:3|three|ba)\b/gi, 'phần ba của bài thi nói'],
    [/\bSpeaking\b/gi, 'kỹ năng nói'],
    [/\bCue\s+Card\b/gi, 'thẻ chủ đề'],
    [/\bMind\s+Map\b/gi, 'sơ đồ tư duy'],
    [/\bFluency\s*(?:&|and|và)\s*Coherence\b/gi, 'độ trôi chảy và tính mạch lạc'],
    [/\bLexical\s+Resource\b/gi, 'vốn từ vựng'],
    [/\bGrammatical\s+Range\s*(?:&|and|và)\s*Accuracy\b/gi, 'độ đa dạng và chính xác ngữ pháp'],
    [/\bPronunciation\b/gi, 'phát âm'],
    [/\bVocabulary\b/gi, 'từ vựng'],
    [/\bGrammar\b/gi, 'ngữ pháp'],
    [/\bFluency\b/gi, 'độ trôi chảy'],
    [/\bCoherence\b/gi, 'tính mạch lạc'],
    [/\bOEEAF\b/gi, 'phương pháp nêu quan điểm, giải thích, ví dụ và góc nhìn thay thế'],
    [/\bWHY\b/g, 'lý do'],
    [/\bHOW\b/g, 'cách thức'],
    [/\bWHEN\b/g, 'thời gian'],
    [/\bWHERE\b/g, 'địa điểm'],
    [/\bFEELINGS?\b/g, 'cảm xúc'],
    [/\bOPINIONS?\b/g, 'quan điểm'],
    [/\bCOMPARE\b/g, 'so sánh'],
    [/\/th\//gi, 'âm thờ'],
    [/\/s\//gi, 'âm sờ'],
    [/\/z\//gi, 'âm zờ'],
    [/\bband\s+4[.,]0\s*(?:-|–|đến|to)\s*5[.,]5\b/gi, 'band bốn chấm không đến năm chấm năm'],
  ];

  const vietnameseAbbreviationMap = [
    [/\bCNTT\b/g, 'Công nghệ thông tin'],
    [/\bAI\b/g, 'trí tuệ nhân tạo'],
    [/\bML\b/g, 'học máy'],
    [/\bUI\b/g, 'giao diện người dùng'],
    [/\bUX\b/g, 'trải nghiệm người dùng'],
    [/\bAPI\b/g, 'giao diện lập trình ứng dụng'],
    [/\bLLM\b/g, 'mô hình ngôn ngữ lớn'],
    [/\bRAG\b/g, 'hệ thống truy xuất kết hợp sinh nội dung'],
    [/\bGPU\b/g, 'gi pi diu'],
    [/\bCPU\b/g, 'xi pi diu'],
    [/\bIoT\b/g, 'ai âu ti'],
    [/\bOCR\b/g, 'âu xi a'],
    [/\bPDF\b/g, 'pi đi ép'],
    [/\bDOCX\b/g, 'đóc ích'],
    [/\bURL\b/g, 'diu a eo'],
    [/\bHTTPS\b/g, 'âych ti ti pi ét'],
    [/\bHTTP\b/g, 'âych ti ti pi'],
    [/\bSQL\b/g, 'ét kiu eo'],
    [/\bJSON\b/g, 'giây son'],
    [/\bHTML\b/g, 'âych ti em eo'],
    [/\bCSS\b/g, 'xi ét ét'],
    [/\bDB\b/g, 'cơ sở dữ liệu'],
    [/\bGDP\b/g, 'tổng sản phẩm quốc nội'],
    [/\bTP\.?HCM\b/gi, 'Thành phố Hồ Chí Minh'],
    [/\bHN\b/g, 'Hà Nội'],
    [/\bVN\b/g, 'Việt Nam'],
    [/\bvd\.?\b/gi, 'ví dụ'],
    [/\bvs\.?\b/gi, 'so với'],
    [/\betc\.?\b/gi, 'và các loại khác'],
    [/\be\.g\.?\b/gi, 'ví dụ'],
    [/\bi\.e\.?\b/gi, 'tức là'],
    [/&/g, 'và'],
  ];

  if (vietnamese) {
    for (const [pattern, replacement] of vietnameseTermMap) {
      t = t.replace(pattern, replacement);
    }
    for (const [pattern, replacement] of vietnameseAbbreviationMap) {
      t = t.replace(pattern, replacement);
    }
    t = spellUnknownVietnameseAcronyms(t);
  } else {
    // Preserve English terminology for an English-capable TTS voice. Only
    // normalize symbols that would otherwise be read as punctuation names.
    t = t.replace(/&/g, ' and ');
  }

  // 4. Normalize numbers only for Vietnamese narration.
  if (vietnamese) {
    t = normalizeVietnameseDecimals(t);
    t = t.replace(/(\d+)%/g, '$1 phần trăm');
    t = t.replace(/(\d+)\s*tỷ/g, '$1 tỷ');
    t = t.replace(/(\d+)\s*tr(?:iệu)?\b/g, '$1 triệu');
    t = t.replace(/(\d+)\s*nghìn\b/g, '$1 nghìn');
  }

  // 5. Loại bỏ ký tự đặc biệt gây nhiễu TTS
  t = t.replace(/[()\[\]{}]/g, '');
  t = t.replace(/[\u2022\u2023\u25E6\u2043\u2013\u2014]/g, ','); // bullets & dashes → comma
  t = t.replace(/\/+/g, vietnamese ? ' hoặc ' : ' or ');
  t = t.replace(/\\n/g, ' ');

  // 6. Chuẩn hóa khoảng trắng và dấu câu
  t = t.replace(/[ \t]+/g, ' ');
  t = t.replace(/\.{2,}/g, '.');
  t = t.replace(/,{2,}/g, ',');
  t = t.replace(/\s+([.,!?])/g, '$1');
  t = t.replace(/([.!?])([^ "\n])/g, '$1 $2'); // đảm bảo cách sau dấu câu

  return t.trim();
}

export default function VideoGenerationModal({
  open,
  onClose,
  slides,
  projectName,
  projectId,
  onPreparePresentation,
  onNotify,
}) {
  const navigate = useNavigate();
  const { activeJobs, updateJob, removeJob } = useVideoGenStore();

  // Use projectId as key, fall back to projectName
  const jobKey = projectId || projectName || 'default';
  const activeJob = activeJobs[jobKey];

  // Local UI state – synced FROM store when modal opens
  const [phase, setPhase] = useState('setup');
  const [loadingOptions, setLoadingOptions] = useState(false);
  const [presenters, setPresenters] = useState([]);
  const [selectedPresenterUrl, setSelectedPresenterUrl] = useState('');
  const [customPresenter, setCustomPresenter] = useState(null);
  const [customFace, setCustomFace] = useState(null);
  const [currentUser, setCurrentUser] = useState(null);
  const [voice, setVoice] = useState(DEFAULT_VOICE);
  const [voiceMode, setVoiceMode] = useState('preset');
  const [voiceSample, setVoiceSample] = useState(null);
  const [voiceSampleDuration, setVoiceSampleDuration] = useState(0);
  const [referenceText, setReferenceText] = useState('');
  const [error, setError] = useState('');
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState('');
  const [currentSlide, setCurrentSlide] = useState(0);
  const [resultUrl, setResultUrl] = useState('');
  const [temporaryVideoUrl, setTemporaryVideoUrl] = useState('');

  // AbortController lives outside React state so it survives re-renders
  const abortRef = useRef(null);
  const resettingRef = useRef(false);

  const facePreviewUrl = useMemo(
    () => (customFace ? URL.createObjectURL(customFace) : ''),
    [customFace],
  );

  useEffect(() => {
    return () => {
      if (facePreviewUrl) URL.revokeObjectURL(facePreviewUrl);
    };
  }, [facePreviewUrl]);

  const handleVoiceSampleChange = (event) => {
    const file = event.target.files?.[0] || null;
    event.target.value = '';
    if (!file) return;

    if (!file.type.startsWith('audio/')) {
      setError('File giọng mẫu phải là định dạng audio.');
      return;
    }

    const previewUrl = URL.createObjectURL(file);
    const audio = new Audio();
    audio.preload = 'metadata';
    audio.onloadedmetadata = () => {
      const duration = Number(audio.duration || 0);
      URL.revokeObjectURL(previewUrl);
      if (!Number.isFinite(duration) || duration <= 0) {
        setError('Không đọc được thời lượng audio mẫu.');
        return;
      }
      if (duration > 15) {
        setVoiceSample(null);
        setVoiceSampleDuration(0);
        setError(`Audio mẫu dài ${duration.toFixed(1)} giây; vui lòng dùng đoạn tối đa 15 giây.`);
        return;
      }
      setVoiceSample(file);
      setVoiceSampleDuration(duration);
      setError('');
    };
    audio.onerror = () => {
      URL.revokeObjectURL(previewUrl);
      setError('Không đọc được file audio mẫu.');
    };
    audio.src = previewUrl;
  };

  // ── Reactively sync from store whenever activeJob changes (background job) ──
  useEffect(() => {
    if (!open || !activeJob) return;
    setPhase(activeJob.phase || 'setup');
    setProgress(activeJob.progress || 0);
    setStatus(activeJob.status || '');
    setCurrentSlide(activeJob.currentSlide || 0);
    setResultUrl(activeJob.resultUrl || '');
    setTemporaryVideoUrl(activeJob.temporaryVideoUrl || '');
    setError(activeJob.error || '');
  }, [open, activeJob]); // re-run whenever store updates

  // The backend is the shared source of truth, so another browser logged into
  // the same account can observe this project's generation progress.
  useEffect(() => {
    if (!open || !projectId) return undefined;
    let disposed = false;
    const refresh = async () => {
      if (jobControllers.has(jobKey) || resettingRef.current) return;
      try {
        const remote = await projectService.getCurrentVideo(projectId);
        if (!disposed && remote) {
          const isIdleHistory = (remote.phase || 'setup') === 'setup' && (remote.progress || 0) === 0;
          updateJob(jobKey, {
            projectId,
            projectName,
            phase: remote.phase || 'setup',
            progress: remote.progress || 0,
            status: remote.status || '',
            currentSlide: remote.currentSlide || 0,
            totalSlides: remote.totalSlides || slides.length,
            resultUrl: remote.videoUrl || '',
            temporaryVideoUrl: remote.temporaryVideoUrl || '',
            error: isIdleHistory ? '' : (remote.error || ''),
          });
        }
      } catch {
        // Local generation remains usable during a transient BE outage.
      }
    };
    refresh();
    const timer = window.setInterval(refresh, 2000);
    return () => { disposed = true; window.clearInterval(timer); };
  }, [open, projectId, jobKey, projectName, slides.length, updateJob]);

  // ── Load presenters when modal opens (setup or restoring) ─────────────────
  useEffect(() => {
    if (!open) return undefined;
    // If there's an active job already, no need to re-load options
    if (activeJob && activeJob.phase !== 'setup') return undefined;

    const controller = new AbortController();
    const loadTimer = window.setTimeout(async () => {
      setError('');
      setLoadingOptions(true);

      const hasSession = await videoGenerationService.ensureSession();
      if (!hasSession) {
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
          setSelectedPresenterUrl((cur) => cur || presenterList[0]?.video_url || '');
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

  // ── Helpers ────────────────────────────────────────────────────────────────
  const sync = (updates) => {
    // Update local state
    if (updates.phase !== undefined) setPhase(updates.phase);
    if (updates.progress !== undefined) setProgress(updates.progress);
    if (updates.status !== undefined) setStatus(updates.status);
    if (updates.currentSlide !== undefined) setCurrentSlide(updates.currentSlide);
    if (updates.resultUrl !== undefined) setResultUrl(updates.resultUrl);
    if (updates.temporaryVideoUrl !== undefined) setTemporaryVideoUrl(updates.temporaryVideoUrl);
    if (updates.error !== undefined) setError(updates.error);
    // Persist to global store so Dashboard can read it
    updateJob(jobKey, { projectId, projectName, ...updates });
    if (projectId) {
      const payload = {
        phase: updates.phase,
        progress: updates.progress,
        status: updates.status,
        currentSlide: updates.currentSlide,
        totalSlides: slides.length,
        videoUrl: updates.resultUrl,
        temporaryVideoUrl: updates.temporaryVideoUrl,
        error: updates.error,
      };
      const previous = remoteSyncQueues.get(jobKey) || Promise.resolve();
      const next = previous
        .catch(() => {})
        .then(() => projectService.updateVideo(projectId, payload));
      remoteSyncQueues.set(jobKey, next);
      next.finally(() => {
        if (remoteSyncQueues.get(jobKey) === next) remoteSyncQueues.delete(jobKey);
      }).catch(() => {});
    }
  };

  const reset = async () => {
    resettingRef.current = true;
    setPhase('setup');
    setProgress(0);
    setStatus('');
    setCurrentSlide(0);
    setResultUrl('');
    setTemporaryVideoUrl('');
    setError('');
    removeJob(jobKey);
    if (projectId) {
      try {
        await (remoteSyncQueues.get(jobKey) || Promise.resolve()).catch(() => {});
        await projectService.updateVideo(projectId, {
          startNew: true,
          phase: 'setup',
          progress: 0,
          status: '',
          currentSlide: 0,
          totalSlides: slides.length,
          videoUrl: '',
          temporaryVideoUrl: '',
          error: '',
        });
      } catch {
        setError('Không thể khởi tạo lại phiên sinh video. Vui lòng thử lại.');
      }
    }
    resettingRef.current = false;
  };

  // ── Navigation: close modal but DO NOT abort the generation ───────────────
  const handleClose = () => {
    onClose();
  };

  const handleGoToDashboard = () => {
    onClose();
    navigate('/dashboard');
  };

  // ── Stop: abort the controller (works even if modal was re-opened) ─────────
  const handleStop = () => {
    // Try both the local ref and the module-level map (for background jobs)
    abortRef.current?.abort();
    jobControllers.get(jobKey)?.abort();
    jobControllers.delete(jobKey);
    reset();
  };

  // ── Retry saving a generated video ────────────────────────────────────────
  const retryPersistVideo = async () => {
    if (!temporaryVideoUrl || !currentUser) {
      setError('Không còn đường dẫn video tạm để lưu lại.');
      return;
    }
    const controller = new AbortController();
    abortRef.current = controller;
    sync({ phase: 'processing', error: '', progress: 95, currentSlide: slides.length, status: 'Đang thử lưu lại video vào thư viện...' });
    try {
      const persistentUrl = await videoGenerationService.persistVideo(temporaryVideoUrl, currentUser, controller.signal);
      sync({ phase: 'result', resultUrl: persistentUrl, progress: 100, status: 'Video đã hoàn thành' });
      onNotify?.('Đã lưu video vào thư viện!', 'success');
    } catch (err) {
      const msg = getVideoApiError(err, 'Không thể lưu video vào thư viện');
      sync({ phase: 'save-error', error: msg, status: 'Video đã tạo xong nhưng chưa được lưu' });
      onNotify?.(`Video đã tạo xong nhưng chưa lưu: ${msg}`, 'error');
    } finally {
      abortRef.current = null;
    }
  };

  // ── Main generation ────────────────────────────────────────────────────────
  const startGeneration = async () => {
    if (!currentUser) { setError('Không lấy được thông tin người dùng Gen Video.'); return; }
    if (!selectedPresenterUrl && !customPresenter) { setError('Vui lòng chọn hoặc tải lên video người thuyết trình.'); return; }
    if (voiceMode === 'clone' && !voiceSample) { setError('Vui lòng tải lên audio giọng mẫu.'); return; }
    if (voiceMode === 'clone' && !referenceText.trim()) { setError('Vui lòng nhập đúng nội dung được nói trong audio mẫu.'); return; }

    if (projectId) {
      try {
        await projectService.updateVideo(projectId, {
          startNew: true,
          phase: 'processing',
          progress: 0,
          status: 'Đang khởi tạo quá trình sinh video...',
          currentSlide: 0,
          totalSlides: slides.length,
          videoUrl: '',
          temporaryVideoUrl: '',
          error: '',
        });
      } catch {
        setError('Không thể đồng bộ tiến trình video với máy chủ. Vui lòng thử lại.');
        return;
      }
    }

    const controller = new AbortController();
    abortRef.current = controller;
    jobControllers.set(jobKey, controller); // store globally so re-opened modal can abort
    sync({ phase: 'processing', error: '', progress: 3, currentSlide: 0, resultUrl: '', temporaryVideoUrl: '', status: 'Đang dựng hình ảnh slide và chuẩn bị tài liệu...' });

    let completedVideoUrl = '';
    let failureStep = 'Khởi tạo video';

    try {
      failureStep = 'Chuẩn bị slide';
      const { blob, textBlob, fileName } = await onPreparePresentation();

      sync({ progress: 8, status: 'Đang tải dữ liệu slide sang dịch vụ Gen Video...' });
      failureStep = 'Tải và dựng hình slide';
      const uploadResult = await videoGenerationService.uploadPresentation(blob, fileName || projectName, controller.signal);
      const renderedSlides = uploadResult?.slides || [];
      if (!uploadResult?.success || !renderedSlides.length) throw new Error('Gen Video không render được file trình chiếu');

      // Decide narration source: speaker notes vs AI extraction
      const hasNotes = slides.some((s) => getSlideNoteText(s).length > 0);
      let narrations = [];

      if (hasNotes) {
        sync({ progress: 12, status: 'Đang dùng Ghi chú diễn giả có sẵn của slide...' });
        narrations = slides.map((s, i) => ({ slide_number: i, content: getSlideNoteText(s), rewritten_content: getSlideNoteText(s) }));
      } else {
        sync({ progress: 10, status: 'Đang phân tích và tạo lời thuyết minh cho từng slide...' });
        failureStep = 'Tạo lời thuyết minh';
        const textResult = await videoGenerationService.extractPresentationText(textBlob || blob, fileName || projectName, controller.signal);
        narrations = textResult?.slides_text || [];
        if (!textResult?.success || !narrations.length) throw new Error('Gen Video không tạo được lời thuyết minh từ nội dung slide');
      }

      let presenterUrl = selectedPresenterUrl;
      if (customPresenter) {
        sync({ progress: 13, status: 'Đang tải video người thuyết trình...' });
        failureStep = 'Tải video người thuyết trình';
        presenterUrl = await videoGenerationService.uploadPresenterVideo(customPresenter, controller.signal);
      }
      if (!presenterUrl) throw new Error('Không nhận được video người thuyết trình');

      if (customFace) {
        sync({ progress: 14, status: 'Đang tải ảnh khuôn mặt...' });
        failureStep = 'Tải ảnh khuôn mặt';
        const sourceImageUrl = await videoGenerationService.uploadFaceImage(customFace, controller.signal);
        if (!sourceImageUrl) throw new Error('Không nhận được URL ảnh khuôn mặt');

        sync({ progress: 16, status: 'Đang khởi tạo tác vụ ghép khuôn mặt...' });
        failureStep = 'Khởi tạo ghép khuôn mặt';
        const deepfakeJobId = await videoGenerationService.createDeepfake(
          sourceImageUrl,
          presenterUrl,
          controller.signal,
        );
        presenterUrl = await videoGenerationService.waitForDeepfake(
          deepfakeJobId,
          controller.signal,
          (deepfakeStatus) => sync({
            status: deepfakeStatus === 'queued'
              ? 'Đang chờ xử lý ghép khuôn mặt...'
              : 'Đang ghép khuôn mặt vào video người thuyết trình...',
          }),
        );
        if (!presenterUrl) throw new Error('Không nhận được video đã ghép khuôn mặt');
      }

      const slideJobs = slides.map((slideObj, index) => {
        const note = getSlideNoteText(slideObj);
        const gen = getSlideApiItem(narrations, index);
        const narration = String(note || gen?.rewritten_content || gen?.content || '').trim();
        const renderedSlide = getSlideApiItem(renderedSlides, index);
        return { index, narration, renderedSlide };
      }).filter((j) => j.narration && j.renderedSlide?.image_url);

      if (!slideJobs.length) throw new Error('Không có slide hợp lệ để tạo lời thuyết minh');

      let referenceAudioUrl = '';
      if (voiceMode === 'clone') {
        sync({ progress: customFace ? 18 : 14, status: 'Đang tải audio giọng mẫu...' });
        failureStep = 'Tải audio giọng mẫu';
        referenceAudioUrl = await videoGenerationService.uploadVoiceSample(voiceSample, controller.signal);
        if (!referenceAudioUrl) throw new Error('Không nhận được URL audio giọng mẫu');
      }

      const composedUrls = [];
      const totalOps = slideJobs.length * 3;
      let doneOps = 0;
      const processingStart = customFace ? 18 : 14;
      const pct = () => processingStart + Math.round((doneOps / totalOps) * (84 - processingStart));

      for (const { index, narration, renderedSlide } of slideJobs) {
        sync({ currentSlide: index + 1, status: `Đang tạo giọng đọc cho slide ${index + 1}/${slides.length}...` });
        failureStep = `Tạo giọng đọc slide ${index + 1}`;
        const ttsPayload = { text: sanitizeNoteForTTS(narration, index), ...voice };
        if (voiceMode === 'clone') {
          ttsPayload.reference_audio_url = referenceAudioUrl;
          ttsPayload.reference_text = referenceText.trim();
        }
        const audioUrl = await videoGenerationService.generateSpeech(ttsPayload, controller.signal);
        if (!audioUrl) throw new Error(`Không tạo được giọng đọc cho slide ${index + 1}`);
        doneOps += 1; sync({ progress: pct(), status: `Đang đồng bộ người thuyết trình ở slide ${index + 1}/${slides.length}...` });

        failureStep = `Đồng bộ người thuyết trình slide ${index + 1}`;
        const lipVideoUrl = await videoGenerationService.createLipVideo(audioUrl, presenterUrl, controller.signal);
        if (!lipVideoUrl) throw new Error(`Không tạo được video thuyết trình cho slide ${index + 1}`);
        doneOps += 1; sync({ progress: pct(), status: `Đang ghép hình ảnh slide ${index + 1}/${slides.length}...` });

        failureStep = `Ghép hình ảnh slide ${index + 1}`;
        const composedUrl = await videoGenerationService.combineSlide(renderedSlide.image_url, lipVideoUrl, controller.signal);
        if (!composedUrl) throw new Error(`Không ghép được slide ${index + 1}`);
        composedUrls.push(composedUrl);
        doneOps += 1; sync({ progress: pct() });
      }

      if (!composedUrls.length) throw new Error('Không có slide hợp lệ để ghép video');

      sync({ progress: 88, status: 'Đang nối các slide thành video hoàn chỉnh...' });
      failureStep = 'Nối video hoàn chỉnh';
      completedVideoUrl = await videoGenerationService.concatVideos(composedUrls, controller.signal);
      if (!completedVideoUrl) throw new Error('Không nối được video hoàn chỉnh');
      sync({ temporaryVideoUrl: completedVideoUrl });

      sync({ progress: 95, status: 'Đang lưu video vào thư viện...' });
      failureStep = 'Lưu video vào thư viện';
      const persistentUrl = await videoGenerationService.persistVideo(completedVideoUrl, currentUser, controller.signal);

      sync({ phase: 'result', resultUrl: persistentUrl, progress: 100, status: 'Video đã hoàn thành' });
      onNotify?.('Sinh video thành công!', 'success');

    } catch (err) {
      const baseMessage = getVideoApiError(err);
      const msg = baseMessage === 'Network Error'
        ? `${failureStep}: không kết nối được dịch vụ sinh video`
        : `${failureStep}: ${baseMessage}`;
      if (err?.code === 'ERR_CANCELED') {
        // Aborted by user – state already reset by handleStop
        return;
      }
      if (completedVideoUrl) {
        sync({ phase: 'save-error', error: msg, status: 'Video đã tạo xong nhưng chưa được lưu', progress: 95, currentSlide: slides.length });
      } else {
        sync({ phase: 'setup', error: msg, status: '', progress: 0 });
      }
      onNotify?.(completedVideoUrl ? `Video đã tạo xong nhưng chưa lưu: ${msg}` : msg, 'error');
    } finally {
      abortRef.current = null;
      jobControllers.delete(jobKey);
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
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {phase !== 'processing' && (
              <button type="button" className="btn btn-ghost btn-sm" onClick={handleGoToDashboard} title="Quay về Dashboard">
                <LayoutDashboard size={15} /> Về Dashboard
              </button>
            )}
            {phase === 'processing' && (
              <button type="button" className="btn btn-ghost btn-sm" onClick={handleGoToDashboard} title="Để tiến trình chạy nền và về Dashboard">
                <LayoutDashboard size={15} /> Chạy nền
              </button>
            )}
            <button type="button" className="video-gen-icon-btn" onClick={handleClose} aria-label="Đóng">
              <X size={18} />
            </button>
          </div>
        </header>

        {/* ── Setup phase ── */}
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
                    onChange={(e) => {
                      const file = e.target.files?.[0] || null;
                      setCustomPresenter(file);
                      if (file) setSelectedPresenterUrl('');
                    }}
                  />
                  <Upload size={20} />
                  <span>{customPresenter ? customPresenter.name : 'Tải video lên'}</span>
                </label>
              </div>
            )}

            <div className="video-gen-section-heading video-gen-face-heading">
              <ImagePlus size={17} />
              <div>
                <strong>Ghép khuôn mặt <em>Tùy chọn</em></strong>
                <span>Tải ảnh chân dung để thay khuôn mặt trong video đại diện đã chọn</span>
              </div>
            </div>

            <div className="video-gen-face-option">
              <label className={`video-gen-face-upload ${customFace ? 'selected' : ''}`}>
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  onChange={(e) => setCustomFace(e.target.files?.[0] || null)}
                />
                {customFace ? (
                  <img src={facePreviewUrl} alt="Khuôn mặt sẽ ghép" />
                ) : (
                  <ImagePlus size={22} />
                )}
                <span>{customFace ? customFace.name : 'Tải ảnh khuôn mặt'}</span>
                {customFace && <CheckCircle2 size={16} className="video-gen-face-check" />}
              </label>
              <div className="video-gen-face-help">
                <strong>{customFace ? 'Sẽ thay khuôn mặt theo ảnh đã chọn' : 'Giữ nguyên khuôn mặt gốc'}</strong>
                <span>{customFace ? 'Ảnh rõ mặt, nhìn thẳng sẽ cho kết quả tốt hơn.' : 'Không tải ảnh nếu bạn muốn dùng video đại diện như hiện tại.'}</span>
                {customFace && (
                  <button type="button" onClick={() => setCustomFace(null)}>Bỏ ảnh</button>
                )}
              </div>
            </div>

            <div className="video-gen-section-heading video-gen-voice-heading">
              <Mic2 size={17} />
              <div><strong>Giọng đọc</strong><span>Lời thuyết minh được tạo tự động từ nội dung slide</span></div>
            </div>

            <div className="video-gen-voice-modes" role="group" aria-label="Chế độ giọng đọc">
              <button type="button" className={voiceMode === 'preset' ? 'active' : ''} onClick={() => setVoiceMode('preset')}>Giọng có sẵn</button>
              <button type="button" className={voiceMode === 'clone' ? 'active' : ''} onClick={() => setVoiceMode('clone')}>Clone giọng</button>
            </div>

            {voiceMode === 'preset' ? (
            <div className="video-gen-controls">
              <label>Giới tính
                <select value={voice.gender} onChange={(e) => setVoice({ ...voice, gender: e.target.value })}>
                  <option value="female">Nữ</option>
                  <option value="male">Nam</option>
                </select>
              </label>
              <label>Vùng giọng
                <select value={voice.area} onChange={(e) => setVoice({ ...voice, area: e.target.value })}>
                  <option value="northern">Miền Bắc</option>
                  <option value="southern">Miền Nam</option>
                </select>
              </label>
              <label>Phong cách
                <select value={voice.group} onChange={(e) => setVoice({ ...voice, group: e.target.value })}>
                  <option value="audiobook">Thuyết minh</option>
                  <option value="interview">Phỏng vấn</option>
                </select>
              </label>
              <label>Cảm xúc
                <select value={voice.emotion} onChange={(e) => setVoice({ ...voice, emotion: e.target.value })}>
                  <option value="neutral">Trung tính</option>
                  <option value="serious">Nghiêm túc</option>
                </select>
              </label>
            </div>
            ) : (
              <div className="video-gen-voice-clone">
                <label className={`video-gen-voice-upload ${voiceSample ? 'selected' : ''}`}>
                  <input type="file" accept="audio/*,.mp3,.wav,.m4a,.ogg" onChange={handleVoiceSampleChange} />
                  <Upload size={19} />
                  <span>{voiceSample ? voiceSample.name : 'Tải audio giọng mẫu'}</span>
                  <small>{voiceSample ? `${voiceSampleDuration.toFixed(1)} giây` : 'MP3, WAV, M4A · tối đa 15 giây'}</small>
                </label>
                <label className="video-gen-reference-text">
                  <span>Nội dung được nói trong audio mẫu</span>
                  <textarea
                    value={referenceText}
                    onChange={(event) => setReferenceText(event.target.value)}
                    placeholder="Nhập chính xác từng câu, từng từ trong đoạn audio..."
                    rows={3}
                  />
                </label>
                <p>AI sẽ học giọng từ đoạn mẫu và dùng giọng đó đọc toàn bộ ghi chú của các slide.</p>
              </div>
            )}
          </div>
        )}

        {/* ── Processing phase ── */}
        {phase === 'processing' && (
          <div className="video-gen-process">
            <div className="video-gen-process-icon"><Loader2 size={32} className="spin" /></div>
            <h3>Đang sinh video thuyết trình</h3>
            <p>{status || 'Hệ thống đang xử lý dữ liệu slide và giọng đọc...'}</p>
            <div className="video-gen-progress"><span style={{ width: `${progress}%` }} /></div>
            <div className="video-gen-progress-meta">
              <span>{currentSlide ? `Đang xử lý Slide ${currentSlide}/${slides.length}` : 'Đang khởi tạo kịch bản...'}</span>
              <strong>{progress}%</strong>
            </div>
            <button type="button" className="btn btn-ghost btn-sm" onClick={handleStop}><Square size={14} /> Dừng hẳn</button>
          </div>
        )}

        {/* ── Result phase ── */}
        {phase === 'result' && (
          <div className="video-gen-result">
            <div className="video-gen-result-title"><CheckCircle2 size={22} /><div><h3>Video đã hoàn thành</h3><span>Đã lưu vào thư viện Gen Video</span></div></div>
            <video src={resultUrl} controls preload="metadata" />
          </div>
        )}

        {/* ── Save-error phase ── */}
        {phase === 'save-error' && (
          <div className="video-gen-result video-gen-save-error">
            <div className="video-gen-result-title"><AlertTriangle size={22} /><div><h3>Video đã tạo xong</h3><span>Chưa thể lưu vào thư viện</span></div></div>
            <div className="video-gen-alert"><AlertTriangle size={17} /><span>{error}</span></div>
            <video src={temporaryVideoUrl} controls preload="metadata" />
            <p className="video-gen-save-hint">Bạn có thể mở video tạm ngay hoặc thử lưu lại.</p>
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
              <button type="button" className="btn btn-ghost btn-sm" onClick={handleGoToDashboard}><LayoutDashboard size={15} /> Về Dashboard</button>
              <button type="button" className="btn btn-ghost btn-sm" onClick={reset}><RotateCcw size={15} /> Tạo lại</button>
              <a className="btn btn-primary btn-sm" href={resultUrl} target="_blank" rel="noreferrer"><Download size={15} /> Mở video</a>
            </>
          )}
          {phase === 'save-error' && (
            <>
              <button type="button" className="btn btn-ghost btn-sm" onClick={handleGoToDashboard}><LayoutDashboard size={15} /> Về Dashboard</button>
              <a className="btn btn-ghost btn-sm" href={temporaryVideoUrl} target="_blank" rel="noreferrer"><Download size={15} /> Mở video tạm</a>
              <button type="button" className="btn btn-primary btn-sm" onClick={retryPersistVideo}><RotateCcw size={15} /> Thử lưu lại</button>
            </>
          )}
        </footer>
      </section>
    </div>
  );
}
