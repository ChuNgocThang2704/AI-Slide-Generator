import { useState, useRef, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useProjectStore, useUIStore, useVideoGenStore } from '../../store';
import ElementCanvas from '../../components/slides/ElementCanvas';
import VideoGenerationModal from '../../components/video/VideoGenerationModal';
import VideoLibraryModal from '../../components/video/VideoLibraryModal';
import { projectService } from '../../services/documentService';
import { confirmDialog, promptDialog } from '../../services/dialogService';
import { parseDeckMaster, serializeDeckMaster } from '../../utils/deckMaster';
import { createPageNumberElement, hasPageNumbers, isPageNumber, renumberPages } from '../../utils/pageNumber';
import { newElementId } from '../../utils/selection';
import { countRevealStages } from '../../utils/reveal';
import { explainGenerationError } from '../../utils/generationErrors';
import PresenterView from '../../components/slides/PresenterView';
import SlideTransition from '../../components/slides/SlideTransition';
import { isCustomTemplateId, templateService } from '../../services/templateService';
import { exportSlidesToPptx } from '../../services/pptxExportService';
import { captureSlides, exportSnapshotsToPdf } from '../../services/visualExportService';
import { formatSlideDeck, formatSlidePage, toSlidePageUpdate } from '../../utils/slideMapping';
import { reflowSlideTemplate } from '../../utils/slideElements';
import { suggestVariant } from '../../utils/templateLayouts';
import LayoutPicker from '../../components/slides/LayoutPicker';
import ThemeTuner from '../../components/slides/ThemeTuner';
import { hasOwnOrnaments, themeOrnaments } from '../../utils/themeOrnaments';
import { artToElements, isBackdrop } from '../../utils/templateArt';
import { applyCustomTemplateResult, prepareTemplateContent, restoreBuiltInTemplate } from '../../utils/templateSwitching';
import { recommendTemplateForDeck } from '../../utils/dynamicTemplate';
import { buildGeneratedTheme, codeFromBrief, isGeneratedTheme, makeThemeCode, parseThemeCode, subjectOf } from '../../utils/generatedTheme';
import {
  ChevronLeft, ChevronRight, Download, ArrowLeft,
  LayoutTemplate, Check, Loader2, Maximize2, Minimize2,
  Info, Palette, Save, Sparkles, X, FileText, Play, Presentation, Cloud, CloudOff,
  Undo2, Redo2, Copy, Trash2, GripVertical, Plus, ZoomIn, ZoomOut, Clapperboard, Library, UploadCloud,
  ImagePlus, Scissors, Type, BarChart3, ChevronDown, MonitorPlay, Hash, AlertCircle
} from 'lucide-react';
import './EditorPage.css';

// Template definitions (tạm thời hardcoded)
const TEMPLATES = [
  {
    id: 'auto-topic',
    name: 'Tự động theo chủ đề',
    colors: { primary: '#a78bfa' },
    preview: 'linear-gradient(135deg,#071a3d 0%,#4338ca 48%,#db2777 100%)',
    isLight: false,
    isDynamic: true,
  },
  {
    id: 'gen-topic',
    name: 'Template theo prompt',
    colors: { primary: '#ff6584' },
    preview: 'linear-gradient(135deg,#ff6584 0%,#f9b34a 35%,#3ddc97 65%,#6c63ff 100%)',
    isLight: false,
    isGenerative: true,
  },
  { 
    id: 'soft-blue', 
    name: 'Soft Blue', 
    colors: { primary: '#0f4c81' }, 
    preview: '#ffffff', 
    isLight: true,
    isDefault: true 
  },
  { 
    id: 'royal-purple', 
    name: 'Royal Purple', 
    colors: { primary: '#9948FF' }, 
    preview: 'linear-gradient(135deg,#0b0518,#1a0f30)', 
    isLight: false 
  },
  { 
    id: 'clean-white', 
    name: 'Clean White', 
    colors: { primary: '#4f46e5' }, 
    preview: '#ffffff', 
    isLight: true
  },
  { 
    id: 'modern-dark', 
    name: 'Modern Dark', 
    colors: { primary: '#6c63ff' }, 
    preview: 'linear-gradient(135deg,#0d0d1a,#1c1c3a)', 
    isLight: false 
  },
  { 
    id: 'playful-yellow', 
    name: 'Playful Yellow', 
    colors: { primary: '#f59e0b' }, 
    preview: 'linear-gradient(135deg,#fffbeb,#fef9e7)', 
    isLight: true 
  },
  { 
    id: 'gradient-border', 
    name: 'Gradient Border', 
    colors: { primary: '#6c63ff' }, 
    preview: '#f8fafc', 
    isLight: true 
  },
  { 
    id: 'blue-planet', 
    name: 'Blue Planet', 
    colors: { primary: '#00f2fe' }, 
    preview: 'linear-gradient(145deg,#02001a,#04022a,#0b0754)', 
    isLight: false 
  },
  { 
    id: 'nature-green', 
    name: 'Nature Green', 
    colors: { primary: '#27ae60' }, 
    preview: 'linear-gradient(135deg,#0a2318,#0f3426)', 
    isLight: false 
  },
  { 
    id: 'tech-purple', 
    name: 'Tech Purple', 
    colors: { primary: '#e056fd' }, 
    preview: 'linear-gradient(135deg,#0a0015,#160026)', 
    isLight: false 
  },
  {
    id: 'ocean-teal',
    name: 'Ocean Teal',
    colors: { primary: '#14b8a6' },
    preview: 'linear-gradient(135deg,#ecfeff,#ccfbf1)',
    isLight: true,
  },
  {
    id: 'editorial-paper',
    name: 'Editorial Paper',
    colors: { primary: '#c2410c' },
    preview: 'linear-gradient(135deg,#f9f2e6,#efe4d0)',
    isLight: true,
  },
  {
    id: 'midnight-gold',
    name: 'Midnight Gold',
    colors: { primary: '#f5c542' },
    preview: 'linear-gradient(135deg,#0a0e19,#1c2542)',
    isLight: false,
  },
];

const DEFAULT_LEFT_PANEL_WIDTH = 180;
const DEFAULT_RIGHT_PANEL_WIDTH = 390;
const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
const PEDAGOGICAL_ROLE_LABELS = {
  learning_objectives: 'Mục tiêu học tập',
  concept: 'Kiến thức trọng tâm',
  worked_example: 'Ví dụ có hướng dẫn',
  demonstration: 'Minh họa',
  practice: 'Thực hành',
  knowledge_check: 'Kiểm tra kiến thức',
  summary: 'Tổng kết',
};
const SLIDE_LAYOUTS = [
  { value: 'title', label: 'Tiêu đề' },
  { value: 'content', label: 'Nội dung' },
  { value: 'imageText', label: 'Ảnh + chữ' },
  { value: 'twoColumn', label: 'Hai cột' },
  { value: 'quote', label: 'Trích dẫn' },
  { value: 'table', label: 'Bảng' },
  { value: 'chart', label: 'Biểu đồ' },
  { value: 'thankyou', label: 'Kết thúc' },
];

// A template made from the prompt: its whole look lives in the code itself.
const generatedTemplateOption = (code) => {
  const built = buildGeneratedTheme(code);
  return {
    id: code,
    name: built.name,
    colors: { primary: built.theme.primary },
    preview: built.theme.bgGrad,
    isLight: built.theme.isLight,
    isGenerated: true,
  };
};

const layoutThemeFor = (slide, templateId) => (isCustomTemplateId(templateId)
  ? (slide?.elements?.find((el) => el.templateBaseTheme)?.templateBaseTheme || 'soft-blue')
  : (templateId || 'soft-blue'));

function UnifiedSlideView({ slide, theme, scale = 1, revealStage = null }) {
  return (
    <div style={{ width: 960 * scale, height: 540 * scale, overflow: 'hidden' }}>
      <div style={{ width: 960, height: 540, transform: `scale(${scale})`, transformOrigin: 'top left' }}>
        <ElementCanvas
          slide={slide}
          theme={theme}
          scale={1}
          readonly
          preserveTemplateStyles={isCustomTemplateId(theme)}
          revealStage={revealStage}
        />
      </div>
    </div>
  );
}

async function formatPagesWithTemplate(pages, templateId, force = false, sourceTheme) {
  return Promise.all(pages.map(async (page) => {
    const formatted = page.type ? page : formatSlidePage(page);
    if (!force && formatted.elements?.some((element) => element.templateStyleOnly)) return formatted;
    // A slide opened from a PPTX is already laid out exactly as in the file.
    if (!force && formatted.richText?._imported) return formatted;
    const current = prepareTemplateContent(formatted, sourceTheme);
    const match = await templateService.match(templateId, current);
    return applyCustomTemplateResult(current, match, sourceTheme);
  }));
}

const TEMPLATE_READER_VERSION = 3;

function toCustomTemplateOption(template) {
  return {
    id: template.id,
    name: template.name,
    colors: { primary: template.primaryColor || '#4f46e5' },
    preview: template.backgroundColor || '#ffffff',
    isLight: true,
    isCustom: true,
  };
}

function TemplateCard({ template, selected, disabled, deleting, onSelect, onDelete }) {
  const deletable = template.isCustom || template.isSaved;
  return (
    <div className={`e2-tmpl-card ${selected ? 'selected' : ''} ${deletable ? 'has-delete' : ''} ${disabled ? 'disabled' : ''}`}>
      <button
        type="button"
        className="e2-tmpl-select"
        onClick={() => onSelect(template.id)}
        disabled={disabled}
        aria-pressed={selected}
      >
        {selected && <span className="e2-tmpl-check"><Check size={11} /></span>}
        <span className="e2-tmpl-thumb" style={{ background: template.preview }}>
          <span className="e2-tmpl-th-title" style={{ color: template.isLight ? '#1a1a1a' : 'white' }}>
            {template.name}
          </span>
          <span className="e2-tmpl-th-bar" style={{ background: template.colors.primary }} />
        </span>
        <span className="e2-tmpl-name" title={template.name}>{template.name}</span>
        {template.isDynamic && <span className="e2-tmpl-custom-tag">Linh hoạt</span>}
        {template.isGenerative && <span className="e2-tmpl-custom-tag">Sinh mới</span>}
        {template.isGenerated && <span className="e2-tmpl-custom-tag">Của bài này</span>}
        {template.isSaved && <span className="e2-tmpl-custom-tag">Đã lưu</span>}
        {template.isCustom && <span className="e2-tmpl-custom-tag">PowerPoint</span>}
        {template.isDefault && <span className="e2-tmpl-default-tag">Mặc định</span>}
      </button>
      {deletable && (
        <button
          type="button"
          className="e2-tmpl-delete"
          onClick={() => onDelete(template)}
          disabled={disabled}
          title={`Xóa template ${template.name}`}
          aria-label={`Xóa template ${template.name}`}
        >
          {deleting ? <Loader2 size={13} className="spin" /> : <Trash2 size={13} />}
        </button>
      )}
    </div>
  );
}

export default function EditorPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { projects, setProjects, updateProject } = useProjectStore();
  const { addToast } = useUIStore();
  const { activeJobs } = useVideoGenStore();
  const activeVideoJob = activeJobs[id];

  // ── State ──
  const [activeIdx, setActiveIdx] = useState(0);
  const [selectedSlideIndexes, setSelectedSlideIndexes] = useState(() => new Set([0]));
  const [exporting, setExporting] = useState(false);
  const [showPptxMenu, setShowPptxMenu] = useState(false);
  const [showVideoModal, setShowVideoModal] = useState(false);
  const [showVideoLibrary, setShowVideoLibrary] = useState(false);
  const [saving, setSaving] = useState(false);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [saveState, setSaveState] = useState('saved');
  const [fullscreen, setFullscreen] = useState(false);
  const [presenting, setPresenting] = useState(false);
  const [presentationViewport, setPresentationViewport] = useState({ width: window.innerWidth, height: window.innerHeight });
  const [revealStage, setRevealStage] = useState(0);
  const activeIdxRef = useRef(0);
  const revealStageRef = useRef(0);
  const presentChannelRef = useRef(null);
  const [presenterMode, setPresenterMode] = useState(false);
  const [audienceOpen, setAudienceOpen] = useState(false);
  const revealEnabledRef = useRef(false);
  const [rightTab, setRightTab] = useState('ai');
  const [slides, setSlides] = useState([]);
  const [customTemplates, setCustomTemplates] = useState([]);
  const [savedThemes, setSavedThemes] = useState([]);
  const [generatingTheme, setGeneratingTheme] = useState(false);
  const [tunerOpen, setTunerOpen] = useState(false);
  const genOriginRef = useRef({ projectId: null, code: null });
  const briefRef = useRef({ subject: null, brief: null });
  const lastBriefLabelRef = useRef('');
  const [applyingTemplate, setApplyingTemplate] = useState(false);
  const [templateMode, setTemplateMode] = useState('default');
  const [templateUploading, setTemplateUploading] = useState(false);
  const [templateDeletingId, setTemplateDeletingId] = useState(null);
  const [revisionPrompt, setRevisionPrompt] = useState('');
  const [revising, setRevising] = useState(false);
  const [revisionProgress, setRevisionProgress] = useState(0);
  const [revisionStatus, setRevisionStatus] = useState('');
  const [revisionError, setRevisionError] = useState(null);
  const [loadingSlides, setLoadingSlides] = useState(true);
  const [generationProgress, setGenerationProgress] = useState({ active: false, value: 0, status: 'Đang tạo slide...' });
  const [leftPanelWidth, setLeftPanelWidth] = useState(() => Number(localStorage.getItem('editor-left-panel-width')) || DEFAULT_LEFT_PANEL_WIDTH);
  const [rightPanelWidth, setRightPanelWidth] = useState(() => Number(localStorage.getItem('editor-right-panel-width')) || DEFAULT_RIGHT_PANEL_WIDTH);
  const [resizingPanel, setResizingPanel] = useState(null);
  const [draggedSlideIndex, setDraggedSlideIndex] = useState(null);
  const [centerSize, setCenterSize] = useState({ width: 900, height: 600 });
  const [zoomPercent, setZoomPercent] = useState(100);
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState('');
  const [savingTitle, setSavingTitle] = useState(false);
  const slideRef = useRef(null);
  const exportStageRef = useRef(null);
  const centerRef = useRef(null);
  const thumbsRef = useRef(null);
  const slideSelectionAnchorRef = useRef(0);
  const presentationRef = useRef(null);
  const editVersionRef = useRef(0);
  const slidesRef = useRef([]);
  const loadedProjectIdRef = useRef(null);
  const hasUnsavedChangesRef = useRef(false);
  const undoStackRef = useRef([]);
  const redoStackRef = useRef([]);
  const lastHistoryAtRef = useRef(0);
  const lastHistorySlideRef = useRef(-1);
  const saveInFlightRef = useRef(false);
  const wheelAccumulatorRef = useRef(0);
  const wheelResetRef = useRef(null);
  const wheelLockedUntilRef = useRef(0);
  const titleSaveCancelledRef = useRef(false);
  const [historyVersion, setHistoryVersion] = useState(0);

  // ── Effects ──
  useEffect(() => {
    let cancelled = false;
    loadedProjectIdRef.current = null;
    slidesRef.current = [];
    setSlides([]);
    setActiveIdx(0);
    setSelectedSlideIndexes(new Set());
    setLoadingSlides(true);

    const fetchSlides = async () => {
      try {
        const project = await projectService.getById(id);
        if (cancelled) return;
        setProjects([project, ...projects.filter((item) => item.id !== project.id)]);
        const pages = await projectService.getSlidePages(id);
        if (cancelled) return;
        if (pages && pages.length > 0) {
          const formattedSlides = isCustomTemplateId(project.templateId)
            ? await formatPagesWithTemplate(
                formatSlideDeck(pages, project.presentationMode),
                project.templateId,
              )
            : formatSlideDeck(pages, project.presentationMode, project.templateId);
          slidesRef.current = formattedSlides;
          loadedProjectIdRef.current = id;
          undoStackRef.current = [];
          redoStackRef.current = [];
          setHistoryVersion((version) => version + 1);
          hasUnsavedChangesRef.current = false;
          setSlides(formattedSlides);
          setSelectedSlideIndexes(new Set(formattedSlides.length ? [0] : []));
          setHasUnsavedChanges(false);
          setSaveState('saved');
          if (project.status !== 1) {
            updateProject(id, { ...project, status: 1 });
          }
        } else {
          slidesRef.current = [];
          loadedProjectIdRef.current = id;
          hasUnsavedChangesRef.current = false;
          setSlides([]);
        }
      } catch (err) {
        if (cancelled) return;
        console.error('Không thể tải slides từ API:', err);
        setSlides([]);
        addToast('Không thể mở project: ' + err.message, 'error');
        navigate('/dashboard');
      } finally {
        if (!cancelled) setLoadingSlides(false);
      }
    };

    fetchSlides();
    return () => {
      cancelled = true;
    };
  }, [id]);

  useEffect(() => {
    let active = true;
    templateService.getAll()
      .then((templates) => {
        if (active) {
          setCustomTemplates(templates.filter((template) => template.sourceType === 'CUSTOM_PPTX'));
          setSavedThemes(templates.filter((template) => template.sourceType === 'GENERATED_THEME'));
        }
      })
      .catch(() => {
        // The editor can continue with built-in templates.
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    const center = centerRef.current;
    if (!center) return undefined;

    const handleWheel = (event) => {
      if (event.ctrlKey || event.metaKey) {
        event.preventDefault();
        setZoomPercent((value) => clamp(value + (event.deltaY < 0 ? 10 : -10), 50, 150));
        return;
      }
      if (document.activeElement?.isContentEditable) return;
      if (Math.abs(event.deltaX) > Math.abs(event.deltaY)) return;
      event.preventDefault();

      const now = Date.now();
      if (now < wheelLockedUntilRef.current) return;
      wheelAccumulatorRef.current += event.deltaY;
      window.clearTimeout(wheelResetRef.current);
      wheelResetRef.current = window.setTimeout(() => {
        wheelAccumulatorRef.current = 0;
      }, 180);

      if (Math.abs(wheelAccumulatorRef.current) < 55) return;
      const direction = wheelAccumulatorRef.current > 0 ? 1 : -1;
      wheelAccumulatorRef.current = 0;
      wheelLockedUntilRef.current = now + 420;
      setActiveIdx((index) => clamp(index + direction, 0, Math.max(0, slides.length - 1)));
    };

    center.addEventListener('wheel', handleWheel, { passive: false });
    return () => {
      center.removeEventListener('wheel', handleWheel);
      window.clearTimeout(wheelResetRef.current);
    };
  }, [slides.length]);

  useEffect(() => {
    const project = projects.find((item) => item.id === id);
    const status = typeof project?.status === 'string' ? project.status.toUpperCase() : project?.status;
    const stillProcessing = status === 0 || status === 'CREATE' || status === 'PROCESSING';
    if (!project || (!stillProcessing && slides.length > 0)) {
      setGenerationProgress((current) => current.active ? { ...current, active: false } : current);
      return undefined;
    }

    let disposed = false;
    const poll = async () => {
      try {
        const progress = await projectService.getProgress(id);
        if (disposed) return;
        const value = Math.max(0, Math.min(100, Number(progress?.progress) || 0));
        setGenerationProgress({
          active: true,
          value,
          status: progress?.errorMessage || progress?.aiStatus || 'AI đang tạo nội dung và hình ảnh...',
        });
        const done = progress?.projectStatus === 1 || progress?.aiStatus === 'completed' || value >= 100;
        if (done) {
          const pages = await projectService.getSlidePages(id);
          if (disposed || !Array.isArray(pages) || !pages.length) return;
          const formattedSlides = formatSlideDeck(
            pages,
            project.presentationMode,
            isCustomTemplateId(project.templateId) ? undefined : project.templateId,
          );
          slidesRef.current = formattedSlides;
          setSlides(formattedSlides);
          setSelectedSlideIndexes(new Set([0]));
          setGenerationProgress({ active: false, value: 100, status: 'Hoàn thành' });
          updateProject(id, { ...project, status: 1 });
        }
      } catch (error) {
        if (!disposed) {
          setGenerationProgress((current) => ({ ...current, active: true, status: error.message || 'Đang chờ máy chủ xử lý...' }));
        }
      }
    };
    poll();
    const intervalId = window.setInterval(poll, 2500);
    return () => {
      disposed = true;
      window.clearInterval(intervalId);
    };
  }, [id, projects, slides.length, updateProject]);

  useEffect(() => {
    if (!centerRef.current || typeof ResizeObserver === 'undefined') return undefined;
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      setCenterSize({ width, height });
    });
    observer.observe(centerRef.current);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!resizingPanel) return undefined;

    const handlePointerMove = (event) => {
      if (resizingPanel === 'left') {
        setLeftPanelWidth(clamp(event.clientX, 140, 320));
      } else {
        setRightPanelWidth(clamp(window.innerWidth - event.clientX, 300, 560));
      }
    };
    const handlePointerUp = () => {
      setResizingPanel(null);
      document.body.classList.remove('editor-panel-resizing');
    };

    window.addEventListener('pointermove', handlePointerMove);
    window.addEventListener('pointerup', handlePointerUp, { once: true });
    return () => {
      window.removeEventListener('pointermove', handlePointerMove);
      window.removeEventListener('pointerup', handlePointerUp);
      document.body.classList.remove('editor-panel-resizing');
    };
  }, [resizingPanel]);

  useEffect(() => {
    localStorage.setItem('editor-left-panel-width', String(leftPanelWidth));
  }, [leftPanelWidth]);

  useEffect(() => {
    localStorage.setItem('editor-right-panel-width', String(rightPanelWidth));
  }, [rightPanelWidth]);

  useEffect(() => { activeIdxRef.current = activeIdx; }, [activeIdx]);
  useEffect(() => { revealStageRef.current = revealStage; }, [revealStage]);
  useEffect(() => {
    revealEnabledRef.current = Boolean(parseDeckMaster(projects.find((item) => item.id === id)?.deckMaster).revealBullets);
  }, [projects, id]);

  // Tells a presenter-view popup window (if one is open) what's on screen now, so its
  // notes/next-slide preview stay in lockstep with whichever side actually moved.
  const broadcastPresentState = (index, stage) => {
    presentChannelRef.current?.postMessage({
      type: 'goto', index, stage, total: slidesRef.current.length, reveal: revealEnabledRef.current,
    });
  };

  // Advancing "next" during a presentation first steps through the current slide's bullets
  // (see utils/reveal.js) and only moves to the next slide once they're all shown.
  const presentNext = () => {
    const idx = activeIdxRef.current;
    const stage = revealStageRef.current;
    const stages = revealEnabledRef.current ? countRevealStages(slidesRef.current[idx]) : 0;
    if (stage < stages) {
      setRevealStage(stage + 1);
      broadcastPresentState(idx, stage + 1);
      return;
    }
    if (idx >= slidesRef.current.length - 1) return;
    setActiveIdx(idx + 1);
    setRevealStage(0);
    broadcastPresentState(idx + 1, 0);
  };

  const presentPrev = () => {
    const idx = activeIdxRef.current;
    const stage = revealStageRef.current;
    if (stage > 0) {
      setRevealStage(stage - 1);
      broadcastPresentState(idx, stage - 1);
      return;
    }
    if (idx <= 0) return;
    // Stepping back onto the previous slide shows it fully built, not bullet-by-bullet again.
    const targetStage = revealEnabledRef.current ? countRevealStages(slidesRef.current[idx - 1]) : 0;
    setActiveIdx(idx - 1);
    setRevealStage(targetStage);
    broadcastPresentState(idx - 1, targetStage);
  };

  const presentGoto = (targetIdx) => {
    const clamped = Math.max(0, Math.min(slidesRef.current.length - 1, targetIdx));
    setActiveIdx(clamped);
    setRevealStage(0);
    broadcastPresentState(clamped, 0);
  };

  useEffect(() => {
    if (!presenting) return undefined;

    const handleKeyDown = (event) => {
      if (['ArrowRight', 'ArrowDown', 'PageDown', ' '].includes(event.key)) {
        event.preventDefault();
        presentNext();
      } else if (['ArrowLeft', 'ArrowUp', 'PageUp'].includes(event.key)) {
        event.preventDefault();
        presentPrev();
      } else if (event.key === 'Home') {
        event.preventDefault();
        presentGoto(0);
      } else if (event.key === 'End') {
        event.preventDefault();
        presentGoto(slidesRef.current.length - 1);
      } else if (event.key === 'Escape') {
        setPresenting(false);
      }
    };
    const handleResize = () => setPresentationViewport({ width: window.innerWidth, height: window.innerHeight });
    const handleFullscreenChange = () => {
      if (!document.fullscreenElement) setPresenting(false);
    };

    // A presenter-view popup (see startPresenterView) is a second, independent tab: it
    // can't share React state, so it asks for the current slide/stage and issues next/prev
    // the same way local controls do, over a BroadcastChannel scoped to this project.
    const channel = new BroadcastChannel(`lecgen-present-${id}`);
    presentChannelRef.current = channel;
    channel.onmessage = (event) => {
      const message = event.data || {};
      if (message.type === 'next') presentNext();
      else if (message.type === 'prev') presentPrev();
      else if (message.type === 'request-state') broadcastPresentState(activeIdxRef.current, revealStageRef.current);
    };

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('resize', handleResize);
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('resize', handleResize);
      document.removeEventListener('fullscreenchange', handleFullscreenChange);
      channel.close();
      presentChannelRef.current = null;
    };
  }, [presenting, id]);

  // ── Handlers ──
  const historyBusyRef = useRef(false);
  const historySnapshot = useCallback(() => ({
    slides: slidesRef.current,
    templateId: projects.find((item) => item.id === id)?.templateId,
  }), [id, projects]);

  const handleSlideUpdate = useCallback((updatedSlide, meta) => {
    // An automatic layout correction is saved like any change, but it is not something the user
    // did: counting it as a history step made every undo re-create the step it had just undone
    // (undo never ran out) and cleared the redo list.
    if (!meta?.silent) {
      const now = Date.now();
      const startsNewHistoryStep = activeIdx !== lastHistorySlideRef.current || now - lastHistoryAtRef.current > 800;
      if (startsNewHistoryStep) {
        undoStackRef.current.push(historySnapshot());
        if (undoStackRef.current.length > 50) undoStackRef.current.shift();
      }
      lastHistoryAtRef.current = now;
      lastHistorySlideRef.current = activeIdx;
      redoStackRef.current = [];
      setHistoryVersion((version) => version + 1);
    }
    editVersionRef.current += 1;
    hasUnsavedChangesRef.current = true;
    setHasUnsavedChanges(true);
    setSaveState('pending');
    const newSlides = [...slidesRef.current];
    newSlides[activeIdx] = updatedSlide;
    slidesRef.current = newSlides;
    setSlides(newSlides);
  }, [activeIdx, historySnapshot]);

  const applyHistorySnapshot = useCallback((nextSlides) => {
    slidesRef.current = nextSlides;
    setSlides(nextSlides);
    setActiveIdx((index) => Math.max(0, Math.min(index, nextSlides.length - 1)));
    editVersionRef.current += 1;
    hasUnsavedChangesRef.current = true;
    setHasUnsavedChanges(true);
    setSaveState('pending');
    setHistoryVersion((version) => version + 1);
  }, []);

  const restoreHistory = useCallback(async (from, to) => {
    if (!from.current.length || historyBusyRef.current || applyingTemplate) return;
    const target = from.current[from.current.length - 1];
    const current = historySnapshot();
    historyBusyRef.current = true;
    try {
      if (target.templateId !== current.templateId) {
        setApplyingTemplate(true);
        await projectService.update(id, { templateId: target.templateId });
        updateProject(id, { templateId: target.templateId });
      }
      from.current.pop();
      to.current.push(current);
      lastHistoryAtRef.current = 0;
      applyHistorySnapshot(target.slides);
    } catch (error) {
      addToast(error.message || 'Không thể khôi phục template', 'error');
    } finally {
      historyBusyRef.current = false;
      setApplyingTemplate(false);
    }
  }, [addToast, applyingTemplate, applyHistorySnapshot, historySnapshot, id, updateProject]);

  const handleUndo = useCallback(() => restoreHistory(undoStackRef, redoStackRef), [restoreHistory]);
  const handleRedo = useCallback(() => restoreHistory(redoStackRef, undoStackRef), [restoreHistory]);

  const handleDeckUpdate = useCallback((nextSlides, nextActiveIdx) => {
    undoStackRef.current.push(historySnapshot());
    if (undoStackRef.current.length > 50) undoStackRef.current.shift();
    redoStackRef.current = [];
    lastHistoryAtRef.current = 0;
    lastHistorySlideRef.current = -1;
    const numbered = renumberPages(nextSlides);
    slidesRef.current = numbered;
    setSlides(numbered);
    setActiveIdx(Math.max(0, Math.min(nextActiveIdx, numbered.length - 1)));
    editVersionRef.current += 1;
    hasUnsavedChangesRef.current = true;
    setHasUnsavedChanges(true);
    setSaveState('pending');
    setHistoryVersion((version) => version + 1);
  }, [historySnapshot]);

  const duplicateSlide = useCallback((index) => {
    const duplicate = structuredClone(slidesRef.current[index]);
    delete duplicate.id;
    delete duplicate.pageIndex;
    const nextSlides = [...slidesRef.current];
    nextSlides.splice(index + 1, 0, duplicate);
    handleDeckUpdate(nextSlides, index + 1);
  }, [handleDeckUpdate]);

  const addSlide = useCallback((afterIndex = activeIdx) => {
    const blankSlide = {
      type: 'content',
      title: '',
      bullets: [],
      notes: '',
      imageUrl: '',
      chart: null,
      table: null,
      richText: {},
      elements: [],
      primaryVisual: '',
      likelyMultiPptxSlides: false,
    };
    const insertIndex = Math.max(0, Math.min(afterIndex + 1, slidesRef.current.length));
    // A deck that already numbers its slides numbers the new one too (renumbering fixes the digit).
    if (hasPageNumbers(slidesRef.current)) blankSlide.elements = [createPageNumberElement(insertIndex)];
    const nextSlides = [...slidesRef.current];
    nextSlides.splice(insertIndex, 0, blankSlide);
    handleDeckUpdate(nextSlides, insertIndex);
  }, [activeIdx, handleDeckUpdate]);

  const deleteSlide = useCallback((index) => {
    if (slidesRef.current.length <= 1) {
      addToast('Bài trình chiếu cần ít nhất một slide', 'warning');
      return;
    }
    const nextSlides = slidesRef.current.filter((_, slideIndex) => slideIndex !== index);
    const nextActive = activeIdx > index ? activeIdx - 1 : Math.min(activeIdx, nextSlides.length - 1);
    handleDeckUpdate(nextSlides, nextActive);
  }, [activeIdx, addToast, handleDeckUpdate]);

  const reorderSlides = useCallback((fromIndex, toIndex) => {
    if (fromIndex === toIndex || fromIndex < 0 || toIndex < 0) return;
    const nextSlides = [...slidesRef.current];
    const [moved] = nextSlides.splice(fromIndex, 1);
    nextSlides.splice(toIndex, 0, moved);
    let nextActive = activeIdx;
    if (activeIdx === fromIndex) nextActive = toIndex;
    else if (fromIndex < activeIdx && toIndex >= activeIdx) nextActive = activeIdx - 1;
    else if (fromIndex > activeIdx && toIndex <= activeIdx) nextActive = activeIdx + 1;
    handleDeckUpdate(nextSlides, nextActive);
  }, [activeIdx, handleDeckUpdate]);

  const changeSlideLayout = useCallback((nextType) => {
    const slide = slidesRef.current[activeIdx];
    if (!slide || slide.type === nextType) return;
    const sourceLines = Array.isArray(slide.bullets) && slide.bullets.length
      ? slide.bullets
      : String(slide.text || slide.subtitle || slide.quote || '')
        .split(/\r?\n+/)
        .map((line) => line.trim())
        .filter(Boolean);
    const splitAt = Math.max(1, Math.ceil(sourceLines.length / 2));
    const richText = {
      ...(slide.richText || {}),
      ...(slide.table ? { _savedTable: slide.table } : {}),
      ...(slide.chart ? { _savedChart: slide.chart } : {}),
      ...(slide.imageUrl ? { _savedImageUrl: slide.imageUrl } : {}),
    };
    const defaultTable = {
      headers: ['Tiêu chí', 'Giá trị 1', 'Giá trị 2'],
      rows: [['Nội dung', '', '']],
    };
    const defaultChart = {
      type: 'bar',
      labels: ['Mục 1', 'Mục 2', 'Mục 3'],
      series: [{ name: 'Giá trị', values: [0, 0, 0] }],
    };
    const nextSlide = {
      ...slide,
      type: nextType,
      richText,
      table: nextType === 'table' ? slide.table || richText._savedTable || defaultTable : null,
      chart: nextType === 'chart' ? slide.chart || richText._savedChart || defaultChart : null,
      imageUrl: nextType === 'imageText' ? slide.imageUrl || richText._savedImageUrl || '' : '',
      text: slide.text || sourceLines.join('\n'),
      subtitle: slide.subtitle || sourceLines[0] || '',
      quote: slide.quote || sourceLines[0] || slide.title || '',
      left: slide.left || { heading: 'Nội dung 1', points: sourceLines.slice(0, splitAt) },
      right: slide.right || { heading: 'Nội dung 2', points: sourceLines.slice(splitAt) },
      primaryVisual: nextType === 'table' ? 'table' : nextType === 'chart' ? 'chart' : nextType === 'imageText' ? 'image' : '',
      elements: [],
    };
    handleSlideUpdate(nextSlide);
  }, [activeIdx, handleSlideUpdate]);

  // Changing the content type rebuilds the slide's frames from scratch, so warn
  // when the slide carries manual position/size edits that would be lost.
  const requestSlideTypeChange = useCallback(async (nextType) => {
    const slide = slidesRef.current[activeIdx];
    if (!slide || slide.type === nextType) return;
    const theme = layoutThemeFor(slide, projects.find((item) => item.id === id)?.templateId);
    const fresh = reflowSlideTemplate({ ...slide, elements: [] }, theme).elements;
    const current = Array.isArray(slide.elements) ? slide.elements : [];
    const edited = current.length > 0 && (current.length !== fresh.length || current.some((element, index) => (
      !fresh[index] || ['x', 'y', 'width'].some((key) => Math.abs((element[key] || 0) - (fresh[index][key] || 0)) > 3)
    )));
    if (edited && !(await confirmDialog({ title: 'Đổi loại nội dung', message: 'Đổi loại nội dung sẽ dựng lại các khung của slide này và mất chỉnh sửa vị trí, kích thước đã làm. Tiếp tục?', confirmLabel: 'Tiếp tục', danger: true }))) return;
    changeSlideLayout(nextType);
  }, [activeIdx, changeSlideLayout, id, projects]);

  const currentTemplateId = useCallback(
    () => projects.find((item) => item.id === id)?.templateId || 'soft-blue',
    [projects, id],
  );

  // A layout only re-arranges the frames; text, tables, charts, images and
  // notes are carried over untouched, and every frame stays freely editable.
  const changeSlideVariant = useCallback((variantId) => {
    const slide = slidesRef.current[activeIdx];
    if (!slide) return;
    const theme = layoutThemeFor(slide, currentTemplateId());
    handleSlideUpdate(reflowSlideTemplate({ ...slide, richText: { ...(slide.richText || {}), _layoutVariant: variantId } }, theme));
  }, [activeIdx, currentTemplateId, handleSlideUpdate]);

  const autoMixLayouts = useCallback(() => {
    const templateIdNow = currentTemplateId();
    const next = slidesRef.current.map((slide, index) => {
      const theme = layoutThemeFor(slide, templateIdNow);
      const variant = suggestVariant(slide, index, theme);
      if (!variant) return slide;
      return reflowSlideTemplate({ ...slide, richText: { ...(slide.richText || {}), _layoutVariant: variant } }, theme);
    });
    handleDeckUpdate(next, activeIdx);
  }, [activeIdx, currentTemplateId, handleDeckUpdate]);

  const resetAllLayouts = useCallback(() => {
    const templateIdNow = currentTemplateId();
    const next = slidesRef.current.map((slide) => {
      const theme = layoutThemeFor(slide, templateIdNow);
      const { _layoutVariant: dropped, ...richText } = slide.richText || {};
      void dropped;
      return reflowSlideTemplate({ ...slide, richText }, theme);
    });
    handleDeckUpdate(next, activeIdx);
  }, [activeIdx, currentTemplateId, handleDeckUpdate]);

  useEffect(() => {
    const handleDeckShortcut = (event) => {
      if (!(event.ctrlKey || event.metaKey)) return;
      if (event.target.closest?.('input, textarea, [contenteditable="true"]')) return;
      const key = event.key.toLowerCase();
      if (key === 'd') {
        event.preventDefault();
        duplicateSlide(activeIdx);
      } else if (key === '=' || key === '+') {
        event.preventDefault();
        setZoomPercent((value) => Math.min(150, value + 10));
      } else if (key === '-') {
        event.preventDefault();
        setZoomPercent((value) => Math.max(50, value - 10));
      } else if (key === '0') {
        event.preventDefault();
        setZoomPercent(100);
      }
    };
    window.addEventListener('keydown', handleDeckShortcut);
    return () => window.removeEventListener('keydown', handleDeckShortcut);
  }, [activeIdx, duplicateSlide]);

  const applySyncResult = useCallback((savedPages, savingVersion) => {
    if (Array.isArray(savedPages) && savedPages.length) {
      let changed = false;
      const reconciled = slidesRef.current.map((slide, index) => {
        const savedPage = savedPages.find((page) => page.pageIndex === index) || savedPages[index];
        if (!savedPage?.id || slide.id === savedPage.id) return slide;
        changed = true;
        return { ...slide, id: savedPage.id, pageIndex: savedPage.pageIndex ?? index };
      });
      if (changed) {
        slidesRef.current = reconciled;
        setSlides(reconciled);
      }
    }

    if (editVersionRef.current === savingVersion) {
      hasUnsavedChangesRef.current = false;
      setHasUnsavedChanges(false);
      setSaveState('saved');
    }
  }, []);

  useEffect(() => {
    const handleHistoryShortcut = (event) => {
      if (!(event.ctrlKey || event.metaKey)) return;
      const key = event.key.toLowerCase();
      if (key !== 'z' && key !== 'y') return;
      event.preventDefault();
      const wantsRedo = key === 'y' || event.shiftKey;
      // Blurring a focused text box commits its pending edit via onSave,
      // which itself pushes/updates undo-stack state. Reading history in the
      // very same synchronous call can race that commit; deferring to the
      // next tick lets the commit fully land first, so undo/redo always
      // acts on the latest state instead of occasionally being a no-op.
      document.activeElement?.blur();
      window.setTimeout(() => {
        if (wantsRedo) handleRedo();
        else handleUndo();
      }, 0);
    };
    // Capture phase: a focused contentEditable text box has its own native
    // Ctrl+Z undo behavior that otherwise wins over this global shortcut.
    window.addEventListener('keydown', handleHistoryShortcut, true);
    return () => window.removeEventListener('keydown', handleHistoryShortcut, true);
  }, [handleRedo, handleUndo]);

  const applyTemplate = async (tmpl, successMessage, { mixLayouts = false, clearBoundaryVariants = false, keepOrnaments = false } = {}) => {
    if (applyingTemplate || historyBusyRef.current) return false;
    const previousTemplateId = projects.find((item) => item.id === id)?.templateId;
    setApplyingTemplate(true);
    try {
      const customSlides = tmpl.isCustom
        ? await formatPagesWithTemplate(slidesRef.current, tmpl.id, true, previousTemplateId)
        : null;
      const previousSlides = slidesRef.current;
      // A built-in or generated template needs no server round trip before it can show, so the
      // change appears at once and is saved afterwards (see below); an uploaded one is matched first.
      if (tmpl.isCustom) await projectService.update(id, { templateId: tmpl.id });
      // A cover/closing style chosen in the tuner must show, so their remembered composition is dropped first.
      // Ornaments turned into elements belong to the template they came from, so a different
      // template starts with its own (the tuner adjusts the same template and keeps them).
      const sourceSlides = slidesRef.current.map((slide) => {
        let next = slide;
        if (!keepOrnaments && hasOwnOrnaments(next)) {
          const { _noOrnaments: hidden, ...richText } = next.richText || {};
          void hidden;
          next = { ...next, richText, elements: (next.elements || []).filter((element) => !element.ornament) };
        }
        if (clearBoundaryVariants && ['title', 'thankyou'].includes(next.type)) {
          const { _layoutVariant: dropped, ...richText } = next.richText || {};
          void dropped;
          next = { ...next, richText };
        }
        return next;
      });
      let matchedSlides = customSlides || sourceSlides.map((slide) => isCustomTemplateId(previousTemplateId)
        ? restoreBuiltInTemplate(slide, tmpl.id) : reflowSlideTemplate(slide, tmpl.id));
      if (mixLayouts && !customSlides) {
        // Theme and composition are chosen together so the deck is varied from the start.
        matchedSlides = matchedSlides.map((slide, index) => {
          const variant = suggestVariant(slide, index, tmpl.id);
          if (!variant) return slide;
          return reflowSlideTemplate({ ...slide, richText: { ...(slide.richText || {}), _layoutVariant: variant } }, tmpl.id);
        });
      }
      handleDeckUpdate(matchedSlides, activeIdx);
      updateProject(id, { templateId: tmpl.id });
      if (!tmpl.isCustom) {
        try {
          await projectService.update(id, { templateId: tmpl.id });
        } catch (error) {
          // It already looked applied; take it back if the server refused it.
          handleDeckUpdate(previousSlides, activeIdx);
          updateProject(id, { templateId: previousTemplateId });
          throw error;
        }
      }
      const denseSlides = matchedSlides.flatMap((slide, index) => slide.elements?.some((element) =>
        (element.type === 'table' && ((element.data?.rows?.length || 0) > 10 || (element.data?.headers?.length || 0) > 6))
        || (element.type === 'text' && element.role === 'body' && String(element.content || '').length > 1600)
      ) ? [index + 1] : []);
      if (denseSlides.length) addToast(`Slide ${denseSlides.join(', ')} có nhiều dữ liệu. Nên tách slide nếu chữ quá nhỏ.`, 'info');
      return true;
    } catch (error) {
      addToast(error.message || 'Không thể lưu template', 'error');
      return false;
    } finally {
      setApplyingTemplate(false);
    }
  };

  const genRollRef = useRef(0);

  const savedThemeOption = (saved) => ({
    ...generatedTemplateOption(saved.description),
    id: saved.description,
    name: saved.name,
    isGenerated: false,
    isSaved: true,
    savedId: saved.id,
  });

  // While the colour slider is dragged the slide is only tinted (a GPU filter, no re-render), which
  // keeps the drag smooth; the real theme is applied once, on release.
  const previewHue = useCallback((delta) => {
    const frame = document.querySelector('.e2-canvas-frame');
    if (!frame) return;
    frame.style.filter = delta ? `hue-rotate(${delta}deg)` : '';
    frame.style.willChange = delta ? 'filter' : '';
  }, []);

  // ── Template ornaments: hide them, or turn them into shapes the user can edit ──
  const ornamentsAdopted = slides.some((slide) => slide.elements?.some((element) => element.ornament));

  // Clicking a decoration on the slide turns the template's art into real shapes and
  // selects nothing else — from then on it behaves like any other shape: drag, restyle, delete.
  const adoptArtAt = () => {
    adoptOrnaments();
  };

  const adoptOrnaments = () => {
    const code = projects.find((item) => item.id === id)?.templateId;
    const next = slidesRef.current.map((slide) => {
      if (hasOwnOrnaments(slide) && slide.elements?.some((element) => element.ornament)) return slide;
      const decor = slide.richText?._decor;
      const fromArt = Array.isArray(decor) ? artToElements(decor) : [];
      const fromTheme = isGeneratedTheme(code) ? themeOrnaments(code) : [];
      const ornaments = [...fromTheme, ...fromArt];
      if (!ornaments.length) return slide;
      const richText = { ...(slide.richText || {}), _noOrnaments: true };
      if (Array.isArray(decor)) richText._decor = decor.filter(isBackdrop);
      return { ...slide, richText, elements: [...ornaments, ...(slide.elements || [])] };
    });
    handleDeckUpdate(next, activeIdx);
  };

  const restoreOrnaments = () => {
    const code = projects.find((item) => item.id === id)?.templateId;
    if (!isGeneratedTheme(code)) return;
    const next = slidesRef.current.map((slide) => {
      const { _noOrnaments: dropped, ...richText } = slide.richText || {};
      void dropped;
      return { ...slide, richText, elements: (slide.elements || []).filter((element) => !element.ornament) };
    });
    handleDeckUpdate(next, activeIdx);
  };

  // "Put this on every slide": the plain way to repeat a logo, a footer line or a watermark,
  // instead of a separate deck-master layer — each copy is then an ordinary box on its slide.
  const copyElementToAllSlides = (element) => {
    if (!element) return;
    const source = slidesRef.current[activeIdx];
    const next = slidesRef.current.map((slide, index) => {
      if (slide === source) return slide;
      const copy = { ...element, id: newElementId(), style: element.style ? { ...element.style } : undefined };
      void index;
      return { ...slide, elements: [...(slide.elements || []), copy] };
    });
    handleDeckUpdate(next, activeIdx);
  };

  const togglePageNumbers = () => {
    const on = !hasPageNumbers(slidesRef.current);
    const next = slidesRef.current.map((slide, index) => {
      const elements = (slide.elements || []).filter((element) => !isPageNumber(element));
      if (!on) return { ...slide, elements };
      return { ...slide, elements: [...elements, createPageNumberElement(index)] };
    });
    handleDeckUpdate(next, activeIdx);
  };

  const tuneTheme = async (nextCode) => {
    const current = projects.find((item) => item.id === id)?.templateId;
    if (!isGeneratedTheme(current) || nextCode === current) return;
    if (genOriginRef.current.projectId !== id) genOriginRef.current = { projectId: id, code: current };
    const before = parseThemeCode(current);
    const after = parseThemeCode(nextCode);
    try {
      await applyTemplate(
        generatedTemplateOption(nextCode),
        'Đã cập nhật template ✓',
        { clearBoundaryVariants: before?.cover !== after?.cover || before?.closing !== after?.closing, keepOrnaments: true },
      );
    } finally {
      previewHue(null);
    }
  };

  const resetTunedTheme = async () => {
    const origin = genOriginRef.current;
    if (origin.projectId !== id || !origin.code) return;
    await applyTemplate(generatedTemplateOption(origin.code), 'Đã quay về template ban đầu ✓', { clearBoundaryVariants: true });
  };

  const saveCurrentTheme = async () => {
    const code = projects.find((item) => item.id === id)?.templateId;
    if (!isGeneratedTheme(code)) return;
    const suggested = lastBriefLabelRef.current || generatedTemplateOption(code).name;
    const name = await promptDialog({ title: 'Lưu template', message: 'Đặt tên để tìm lại trong thư viện của bạn.', defaultValue: suggested, confirmLabel: 'Lưu' });
    if (name === null) return;
    try {
      const saved = await templateService.saveGenerated(name.trim() || suggested, code);
      setSavedThemes((current) => [saved, ...current.filter((item) => item.id !== saved.id)]);
    } catch (error) {
      addToast(error.message || 'Không thể lưu template', 'error');
    }
  };

  const deleteSavedTheme = async (template) => {
    if (!(await confirmDialog({ title: 'Xóa template đã lưu', message: `Xóa "${template.name}"? Bài đang dùng nó vẫn giữ nguyên giao diện.`, confirmLabel: 'Xóa', danger: true }))) return;
    try {
      await templateService.deleteCustom(template.savedId);
      setSavedThemes((current) => current.filter((item) => item.id !== template.savedId));
    } catch (error) {
      addToast(error.message || 'Không thể xóa template', 'error');
    }
  };
  const handleTemplateSwitch = async (tmplId) => {
    const customOptions = customTemplates.map(toCustomTemplateOption);
    if (tmplId === 'auto-topic') {
      const project = projects.find((item) => item.id === id);
      const recommendation = recommendTemplateForDeck(project, slidesRef.current);
      const recommendedTemplate = TEMPLATES.find((item) => item.id === recommendation.themeId);
      if (recommendedTemplate) {
        await applyTemplate(
          recommendedTemplate,
          `Chủ đề “${recommendation.label}”: áp dụng ${recommendedTemplate.name} và đa dạng hóa bố cục ✓`,
          { mixLayouts: true },
        );
      }
      return;
    }
    if (isGeneratedTheme(tmplId)) {
      // A template saved earlier (or picked from the library) is just its code.
      await applyTemplate(generatedTemplateOption(tmplId), 'Đã áp dụng template đã lưu ✓', { mixLayouts: true });
      return;
    }
    if (tmplId === 'gen-topic') {
      // One new template per prompt. The AI reads the subject once; pressing again re-rolls the
      // ornament and composition locally, so later presses are instant.
      const project = projects.find((item) => item.id === id);
      const subject = subjectOf(project, slidesRef.current);
      if (generatingTheme) return;
      setGeneratingTheme(true);
      try {
        if (briefRef.current.subject !== subject) {
          addToast('AI đang đọc chủ đề để chọn màu sắc và phong cách…', 'info');
          briefRef.current = { subject, brief: await projectService.themeBrief(subject) };
        }
        const { brief } = briefRef.current;
        const build = (roll) => (brief ? codeFromBrief(brief, subject, roll) : makeThemeCode(subject, roll));
        let roll = genRollRef.current;
        let code = build(roll);
        if (code === project?.templateId) { roll += 1; code = build(roll); }
        genRollRef.current = roll + 1;
        lastBriefLabelRef.current = brief?.label || '';
        genOriginRef.current = { projectId: id, code };
        await applyTemplate(
          generatedTemplateOption(code),
          brief
            ? 'AI đã thiết kế template theo chủ đề. Bấm lần nữa để thử phong cách khác ✓'
            : 'Đã tạo template mới theo chủ đề của bài (AI chưa phản hồi nên dùng bộ nhận diện từ khoá) ✓',
          { mixLayouts: true },
        );
      } finally {
        setGeneratingTheme(false);
      }
      return;
    }
    const tmpl = [...TEMPLATES, ...customOptions].find((item) => item.id === tmplId);
    if (tmpl?.isCustom) {
      // A template uploaded before a reader fix is read again once (it takes a while), so the fix
      // reaches it; later presses apply at once. Bump TEMPLATE_READER_VERSION when the reader changes.
      const readKey = `tplRead:${TEMPLATE_READER_VERSION}:${tmpl.id}`;
      let alreadyRead = false;
      try { alreadyRead = Boolean(localStorage.getItem(readKey)); } catch { /* storage unavailable */ }
      if (!alreadyRead) {
        try {
          setApplyingTemplate(true);
          addToast('Đang đọc lại template để cập nhật cách hiển thị (khoảng 20 giây)…', 'info');
          await templateService.reparseCustom(tmpl.id);
          try { localStorage.setItem(readKey, '1'); } catch { /* storage unavailable */ }
        } catch {
          // The stored analysis still works; apply it as it is.
        } finally {
          setApplyingTemplate(false);
        }
      }
    }
    if (tmpl) await applyTemplate(tmpl);
  };

  const handleTemplateUpload = async (event) => {
    const selectedFile = event.target.files?.[0];
    event.target.value = '';
    if (!selectedFile) return;

    const extension = selectedFile.name.slice(selectedFile.name.lastIndexOf('.')).toLowerCase();
    if (!['.pptx', '.potx'].includes(extension)) {
      addToast('Chỉ hỗ trợ template PowerPoint định dạng PPTX hoặc POTX', 'error');
      return;
    }
    if (selectedFile.size > 50 * 1024 * 1024) {
      addToast('Dung lượng template tối đa là 50MB', 'error');
      return;
    }

    setTemplateUploading(true);
    try {
      const template = await templateService.uploadCustom(selectedFile);
      setCustomTemplates((current) => [template, ...current.filter((item) => item.id !== template.id)]);
      setTemplateMode('custom');
      await applyTemplate(
        toCustomTemplateOption(template),
        `Đã upload và áp dụng template "${template.name}"`,
      );
    } catch (error) {
      addToast(error.message || 'Không thể phân tích template PowerPoint', 'error');
    } finally {
      setTemplateUploading(false);
    }
  };

  const handleTemplateDelete = async (template) => {
    const isActive = projects.find((item) => item.id === id)?.templateId === template.id;
    const warning = isActive
      ? `Template "${template.name}" đang được sử dụng. Bài trình chiếu sẽ chuyển về Soft Blue trước khi xóa. Tiếp tục?`
      : `Bạn có chắc muốn xóa template "${template.name}"?`;
    if (!(await confirmDialog({ title: 'Xóa template', message: warning, confirmLabel: 'Xóa', danger: true }))) return;

    setTemplateDeletingId(template.id);
    try {
      if (isActive) {
        const switched = await applyTemplate(TEMPLATES[0], 'Đã chuyển bài trình chiếu về Soft Blue');
        if (!switched) return;
      }
      await templateService.deleteCustom(template.id);
      setCustomTemplates((current) => current.filter((item) => item.id !== template.id));
    } catch (error) {
      addToast(error.message || 'Không thể xóa template', 'error');
    } finally {
      setTemplateDeletingId(null);
    }
  };

  const selectThumbnail = useCallback((event, index) => {
    thumbsRef.current?.focus({ preventScroll: true });
    setActiveIdx(index);
    if (event.shiftKey) {
      const start = Math.min(slideSelectionAnchorRef.current, index);
      const end = Math.max(slideSelectionAnchorRef.current, index);
      setSelectedSlideIndexes(new Set(Array.from({ length: end - start + 1 }, (_, offset) => start + offset)));
    } else if (event.ctrlKey || event.metaKey) {
      setSelectedSlideIndexes((current) => {
        const next = new Set(current);
        if (next.has(index) && next.size > 1) next.delete(index);
        else next.add(index);
        return next;
      });
      slideSelectionAnchorRef.current = index;
    } else {
      setSelectedSlideIndexes(new Set([index]));
      slideSelectionAnchorRef.current = index;
    }
  }, []);

  const handleTabClick = (tabId) => {
    if (rightTab === tabId) {
      setRightTab(null);
    } else {
      if (tabId === 'templates') {
        const selectedTemplateId = projects.find((item) => item.id === id)?.templateId;
        setTemplateMode(isCustomTemplateId(selectedTemplateId) ? 'custom' : 'default');
      }
      setRightTab(tabId);
    }
  };

  const handleCancelRevision = async () => {
    try {
      await projectService.cancel(id);
      addToast('Đã gửi yêu cầu hủy tác vụ', 'info');
    } catch (e) {
      addToast('Không thể hủy tác vụ: ' + e.message, 'error');
    }
  };

  const handleAIRevise = async (customPrompt) => {
    const promptToSend = customPrompt || revisionPrompt;
    if (!promptToSend || !promptToSend.trim()) {
      addToast('Vui lòng nhập yêu cầu chỉnh sửa', 'warning');
      return;
    }

    // Treat one AI revision as one atomic history action. Keep an immutable
    // snapshot because the request may finish after further async state work.
    const beforeRevision = structuredClone(slidesRef.current);

    setRevisionError(null);
    setRevising(true);
    setRevisionProgress(5);
    setRevisionStatus('Đang lưu slides hiện tại...');

    try {
      // 1. Sync slides first so manual changes are saved
      const pageUpdates = slidesRef.current.map(toSlidePageUpdate);

      await projectService.syncSlidePages(id, pageUpdates);
      setRevisionProgress(15);
      setRevisionStatus('Đang gửi yêu cầu chỉnh sửa...');

      // 2. Trigger AI Revise
      const payload = {
        revisionPrompt: promptToSend.trim(),
        revisionScope: 'auto',
        contextSlideNumber: activeIdx + 1
      };

      await projectService.revise(id, payload);
      setRevisionProgress(30);
      setRevisionStatus('AI đang tiếp nhận yêu cầu...');

      // 3. Poll progress
      let pollCount = 0;
      const pollInterval = setInterval(async () => {
        pollCount++;
        try {
          const progressRes = await projectService.getProgress(id);
          const prog = progressRes.progress || 0;
          const status = progressRes.aiStatus;

          setRevisionProgress(Math.min(95, 30 + Math.floor(prog * 0.65)));
          setRevisionStatus(progressRes.errorMessage || 'AI đang phân tích và dựng slide...');
          
          if (progressRes.result && progressRes.result.images) {
            const imgDone = progressRes.result.images.done || 0;
            const imgTotal = progressRes.result.images.total || 0;
            if (imgTotal > 0) {
              setRevisionStatus(`Đang sinh ảnh minh họa (${imgDone}/${imgTotal})...`);
            }
          }

          const isDone = (status === 'completed' || prog >= 100) && progressRes.projectStatus === 1;
          if (isDone) {
            clearInterval(pollInterval);
            setRevisionProgress(100);
            setRevisionStatus('Đang nạp slide mới...');
            
            // Fetch pages again
            const pages = await projectService.getSlidePages(id);
            if (pages && pages.length > 0) {
              const revisedProject = projects.find((item) => item.id === id);
              const formattedSlides = formatSlideDeck(
                pages,
                revisedProject?.presentationMode,
                isCustomTemplateId(revisedProject?.templateId) ? undefined : revisedProject?.templateId,
              );

              undoStackRef.current.push(beforeRevision);
              if (undoStackRef.current.length > 50) undoStackRef.current.shift();
              redoStackRef.current = [];
              lastHistoryAtRef.current = 0;
              lastHistorySlideRef.current = -1;
              slidesRef.current = formattedSlides;
              setHistoryVersion((version) => version + 1);
              hasUnsavedChangesRef.current = false;
              setSlides(formattedSlides);
              setHasUnsavedChanges(false);
              setSaveState('saved');
              
              if (activeIdx >= formattedSlides.length) {
                setActiveIdx(Math.max(0, formattedSlides.length - 1));
              }
            }

            addToast('🎉 Chỉnh sửa slide thành công!', 'success');
            setRevising(false);
            setRevisionPrompt('');
          } else if (status === 'failed' || pollCount > 120) {
            clearInterval(pollInterval);
            // The reason is shown beside the prompt (it stays until dismissed), not in a toast.
            setRevisionError(pollCount > 120 && status !== 'failed'
              ? { title: 'AI phản hồi quá lâu', detail: 'Yêu cầu chưa hoàn thành sau nhiều phút. Hãy thử lại, hoặc chia nhỏ yêu cầu.', action: 'retry' }
              : explainGenerationError(progressRes.errorMessage));
            setRevising(false);
          }
        } catch (pollErr) {
          console.error('Error polling revision progress:', pollErr);
        }
      }, 3000);

    } catch (err) {
      console.error('AI Revise error:', err);
      setRevisionError(explainGenerationError(err.message, { status: err.status }));
      setRevising(false);
    }
  };

  const handleSave = async () => {
    const savingVersion = editVersionRef.current;
    setSaving(true);
    setSaveState('saving');
    addToast('Đang lưu thay đổi...', 'info');
    try {
      const pageUpdates = slidesRef.current.map(toSlidePageUpdate);
      const savedPages = await projectService.syncSlidePages(id, pageUpdates);
      applySyncResult(savedPages, savingVersion);
    } catch (err) {
      setSaveState('error');
      addToast(err.message || 'Lỗi khi lưu slides lên máy chủ', 'error');
    } finally {
      setSaving(false);
    }
  };

  const saveProjectTitle = async () => {
    if (titleSaveCancelledRef.current) {
      titleSaveCancelledRef.current = false;
      setEditingTitle(false);
      return;
    }
    const nextTitle = titleDraft.trim();
    const currentProject = projects.find((item) => item.id === id);
    if (!nextTitle || nextTitle === currentProject?.name) {
      setTitleDraft(currentProject?.name || '');
      setEditingTitle(false);
      return;
    }
    setSavingTitle(true);
    try {
      const updated = await projectService.update(id, { name: nextTitle });
      updateProject(id, { name: updated?.name || nextTitle });
      setEditingTitle(false);
    } catch (error) {
      addToast(error.message || 'Không thể đổi tên bài trình chiếu', 'error');
    } finally {
      setSavingTitle(false);
    }
  };

  // Logo/slide-number/footer that repeat across the whole deck — a small JSON blob on the
  // project itself, not on any one slide, patched and persisted the same way `templateId` is.
  const updateDeckMaster = async (patch) => {
    const current = parseDeckMaster(projects.find((item) => item.id === id)?.deckMaster);
    const next = { ...current, ...patch };
    const serialized = serializeDeckMaster(next);
    updateProject(id, { deckMaster: serialized });
    try {
      await projectService.update(id, { deckMaster: serialized });
    } catch (error) {
      updateProject(id, { deckMaster: serializeDeckMaster(current) });
      addToast(error.message || 'Không thể lưu thiết lập logo/footer', 'error');
    }
  };

  const handleBackDashboard = async () => {
    if (!hasUnsavedChangesRef.current || !slidesRef.current.length) {
      navigate('/dashboard');
      return;
    }
    setSaving(true);
    setSaveState('saving');
    try {
      await projectService.syncSlidePages(id, slidesRef.current.map(toSlidePageUpdate));
      hasUnsavedChangesRef.current = false;
      setHasUnsavedChanges(false);
      setSaveState('saved');
      navigate('/dashboard');
    } catch (error) {
      setSaveState('error');
      addToast(error.message || 'Không thể lưu trước khi rời editor', 'error');
    } finally {
      setSaving(false);
    }
  };

  useEffect(() => {
    const handleEditorShortcut = (event) => {
      const targetIsEditable = event.target.closest?.('input, textarea, [contenteditable="true"]');
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
        event.preventDefault();
        if (!saving && hasUnsavedChangesRef.current) handleSave();
        return;
      }
      if (targetIsEditable || event.ctrlKey || event.metaKey || event.altKey) return;
      if (event.key === 'PageDown') {
        event.preventDefault();
        setActiveIdx((index) => clamp(index + 1, 0, Math.max(0, slidesRef.current.length - 1)));
      } else if (event.key === 'PageUp') {
        event.preventDefault();
        setActiveIdx((index) => clamp(index - 1, 0, Math.max(0, slidesRef.current.length - 1)));
      } else if (event.key === 'Home') {
        event.preventDefault();
        setActiveIdx(0);
      } else if (event.key === 'End') {
        event.preventDefault();
        setActiveIdx(Math.max(0, slidesRef.current.length - 1));
      }
    };
    window.addEventListener('keydown', handleEditorShortcut);
    return () => window.removeEventListener('keydown', handleEditorShortcut);
  }, [saving]);

  useEffect(() => {
    if (!hasUnsavedChanges || revising || exporting || saving || saveInFlightRef.current || !slides.length) return undefined;

    const timeout = window.setTimeout(async () => {
      const savingVersion = editVersionRef.current;
      saveInFlightRef.current = true;
      setSaving(true);
      setSaveState('saving');
      try {
        const savedPages = await projectService.syncSlidePages(id, slidesRef.current.map(toSlidePageUpdate));
        applySyncResult(savedPages, savingVersion);
      } catch (error) {
        console.error('Auto-save failed:', error);
        setSaveState('error');
      } finally {
        saveInFlightRef.current = false;
        setSaving(false);
      }
    }, 1500);

    return () => window.clearTimeout(timeout);
  }, [applySyncResult, exporting, hasUnsavedChanges, id, revising, saving, slides]);

  useEffect(() => () => {
    if (hasUnsavedChangesRef.current && slidesRef.current.length) {
      projectService.syncSlidePages(id, slidesRef.current.map(toSlidePageUpdate))
        .catch((error) => console.error('Save on editor exit failed:', error));
    }
  }, [id]);

  useEffect(() => {
    const warnBeforeUnload = (event) => {
      if (!hasUnsavedChangesRef.current) return;
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', warnBeforeUnload);
    return () => window.removeEventListener('beforeunload', warnBeforeUnload);
  }, []);

  const handleExportPPTX = async () => {
    if (loadingSlides || loadedProjectIdRef.current !== id || !slidesRef.current.length) {
      addToast('Slide chưa tải xong, vui lòng chờ trong giây lát', 'warning');
      return;
    }
    setShowPptxMenu(false);
    setExporting(true);
    addToast('Đang lưu slides trước khi xuất...', 'info');

    try {
      // 1. Sync slides to backend database first to make sure notes, titles, and layout are saved
      const pageUpdates = slidesRef.current.map(toSlidePageUpdate);

      await projectService.syncSlidePages(id, pageUpdates);
      addToast('Đang tạo file PPTX có thể chỉnh sửa...', 'info');

      const projectName = projects.find((p) => p.id === id)?.name || 'presentation';
      const slideSnapshots = await captureSlides(exportStageRef.current, { projectId: id });
      await exportSlidesToPptx({
        slides: slidesRef.current,
        theme: templateId,
        fileName: projectName,
        slideSnapshots,
      });

      addToast('✅ Xuất PPTX thành công!', 'success');
    } catch (e) {
      console.error('PPTX export error:', e);
      addToast('Lỗi khi xuất PPTX, vui lòng thử lại', 'error');
    } finally {
      setExporting(false);
    }
  };

  const preparePresentationForVideo = async () => {
    const currentSlides = slidesRef.current;
    if (!currentSlides.length) throw new Error('Bài trình chiếu chưa có slide');

    await projectService.syncSlidePages(id, currentSlides.map(toSlidePageUpdate));
    const projectName = projects.find((item) => item.id === id)?.name || 'presentation';
    const slideSnapshots = await captureSlides(exportStageRef.current, { projectId: id });
    const blob = await exportSlidesToPptx({
      slides: currentSlides,
      theme: projects.find((item) => item.id === id)?.templateId || 'soft-blue',
      fileName: projectName,
      slideSnapshots,
      download: false,
    });

    return { blob, textBlob: blob, fileName: projectName };
  };

  const handleExportEditablePPTX = async () => {
    if (loadingSlides || loadedProjectIdRef.current !== id || !slidesRef.current.length) {
      addToast('Slide chưa tải xong, vui lòng chờ trong giây lát', 'warning');
      return;
    }
    setShowPptxMenu(false);
    setExporting(true);
    addToast('Đang tạo PPTX có thể chỉnh sửa...', 'info');
    try {
      await projectService.syncSlidePages(id, slidesRef.current.map(toSlidePageUpdate));
      const projectName = projects.find((p) => p.id === id)?.name || 'presentation';
      const { exportEditablePptx } = await import('../../services/editablePptxExportService');
      await exportEditablePptx({
        slides: slidesRef.current,
        theme: templateId,
        fileName: projectName,
        projectId: id,
      });
      addToast('Xuất PPTX chỉnh sửa được thành công!', 'success');
    } catch (error) {
      console.error('Editable PPTX export error:', error);
      addToast(error.message || 'Không thể xuất PPTX chỉnh sửa được', 'error');
    } finally {
      setExporting(false);
    }
  };

  const handleExportPDF = async () => {
    if (loadingSlides || loadedProjectIdRef.current !== id || !slidesRef.current.length) {
      addToast('Slide chưa tải xong, vui lòng chờ trong giây lát', 'warning');
      return;
    }
    setExporting(true);
    addToast('Đang tạo file PDF...', 'info');
    try {
      await projectService.syncSlidePages(id, slidesRef.current.map(toSlidePageUpdate));
      const projectName = projects.find((p) => p.id === id)?.name || 'presentation';
      const slideSnapshots = await captureSlides(exportStageRef.current, { projectId: id });
      await exportSnapshotsToPdf(slideSnapshots, projectName);
      addToast('Xuất PDF thành công!', 'success');
    } catch (error) {
      console.error('PDF export error:', error);
      addToast(error.message || 'Lỗi khi xuất PDF, vui lòng thử lại', 'error');
    } finally {
      setExporting(false);
    }
  };


  const startPanelResize = (panel, event) => {
    event.preventDefault();
    setResizingPanel(panel);
    document.body.classList.add('editor-panel-resizing');
  };

  const startPresentation = ({ presenter = false } = {}) => {
    if (!slides.length) return;
    setPresentationViewport({ width: window.innerWidth, height: window.innerHeight });
    setRevealStage(0);
    setPresenterMode(presenter);
    setAudienceOpen(false);
    setPresenting(true);
    // The presenter view is a working screen (notes, clock, a second window to open), so it
    // stays in the normal browser window; only the plain slideshow goes full screen.
    if (!presenter) document.documentElement.requestFullscreen?.().catch(() => {});
  };

  const stopPresentation = () => {
    setPresenting(false);
    setPresenterMode(false);
    if (document.fullscreenElement) document.exitFullscreen?.().catch(() => {});
  };

  // Like PowerPoint's Presenter View: this window becomes the speaker's screen (current
  // slide, next slide, notes, clock) and a second, audience-only window is opened on demand
  // (drag it to the projector). Both stay in step over the BroadcastChannel set up in the
  // presenting effect above.
  const startPresenterView = () => startPresentation({ presenter: true });

  const openAudienceWindow = () => {
    window.open(`/present/${id}`, `lecgen-audience-${id}`, 'width=1280,height=720');
    setAudienceOpen(true);
  };

  // On phones the prev/next arrows overlay the slide instead of sitting beside
  // it, so the slide can use nearly the full width.
  const getScale = () => {
    const narrow = centerSize.width > 0 && centerSize.width < 640;
    return Math.max(narrow ? 0.2 : 0.35, Math.min(
      1,
      (centerSize.width - (narrow ? 32 : 130)) / 960,
      (centerSize.height - 105) / 540,
    ));
  };

  // ── Render ──
  const project = projects.find((p) => p.id === id);
  if (!project) {
    return <div className="editor-loading"><div className="spinner" /></div>;
  }

  const { name: title, templateId = 'soft-blue' } = project;
  const deckMaster = parseDeckMaster(project.deckMaster);
  const pageNumbersOn = hasPageNumbers(slides);
  const customTemplateOptions = customTemplates.map(toCustomTemplateOption);
  const generatedOption = isGeneratedTheme(templateId) ? generatedTemplateOption(templateId) : null;
  const availableTemplates = [...(generatedOption ? [generatedOption] : []), ...TEMPLATES, ...customTemplateOptions];
  const activeTemplate = availableTemplates.find((template) => template.id === templateId);
  const activeSlide = slides[activeIdx];
  const fitScale = getScale();
  const scale = fitScale * zoomPercent / 100;


  return (
    <div className={`editor2-page ${fullscreen ? 'fullscreen' : ''}`}>
      {/* ── TOPBAR ── */}
      <div className="editor2-topbar">
        <div className="e2-top-left">
          <button className="btn btn-ghost btn-sm" onClick={handleBackDashboard}>
            <ArrowLeft size={15} /> Dashboard
          </button>
          <div className="e2-breadcrumb">
            {editingTitle ? (
              <input
                className="e2-pres-title-input"
                value={titleDraft}
                autoFocus
                maxLength={160}
                disabled={savingTitle}
                onChange={(event) => setTitleDraft(event.target.value)}
                onBlur={saveProjectTitle}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') {
                    event.preventDefault();
                    event.currentTarget.blur();
                  } else if (event.key === 'Escape') {
                    titleSaveCancelledRef.current = true;
                    setTitleDraft(title);
                    setEditingTitle(false);
                  }
                }}
              />
            ) : (
              <button
                type="button"
                className="e2-pres-title"
                title="Đổi tên bài trình chiếu"
                onClick={() => {
                  titleSaveCancelledRef.current = false;
                  setTitleDraft(title);
                  setEditingTitle(true);
                }}
              >
                {title}
              </button>
            )}
          </div>
        </div>
        <div className="e2-top-right">
          <div className="e2-history-actions" data-history-version={historyVersion}>
            <button className="e2-icon-action" onClick={handleUndo} disabled={!undoStackRef.current.length} title="Hoàn tác (Ctrl+Z)" aria-label="Hoàn tác">
              <Undo2 size={16} />
            </button>
            <button className="e2-icon-action" onClick={handleRedo} disabled={!redoStackRef.current.length} title="Làm lại (Ctrl+Shift+Z)" aria-label="Làm lại">
              <Redo2 size={16} />
            </button>
          </div>
          <div className={`e2-save-state ${saveState}`} title={saveState === 'error' ? 'Không thể tự động lưu' : 'Trạng thái lưu'}>
            {saveState === 'saving' && <><Loader2 size={13} className="spin"/> Đang lưu</>}
            {saveState === 'pending' && <><Cloud size={13}/> Chưa lưu</>}
            {saveState === 'saved' && <><Cloud size={13}/> Đã lưu</>}
            {saveState === 'error' && <><CloudOff size={13}/> Lưu lỗi</>}
          </div>
          <button className="btn btn-ghost btn-sm" onClick={() => setFullscreen(!fullscreen)}>
            {fullscreen ? <><Minimize2 size={14}/> Thu nhỏ editor</> : <><Maximize2 size={14}/> Mở rộng editor</>}
          </button>
          <button className="btn btn-ghost btn-sm" onClick={() => startPresentation()} disabled={!slides.length}>
            <Play size={14}/> Trình chiếu
          </button>
          <button className="btn btn-ghost btn-sm" onClick={startPresenterView} disabled={!slides.length} title="Mở cửa sổ ghi chú, slide kế tiếp và đồng hồ cho người thuyết trình">
            <MonitorPlay size={14}/> Chế độ diễn giả
          </button>
          <button
            type="button"
            className="btn btn-ghost btn-sm e2-video-action"
            onClick={() => setShowVideoModal(true)}
            disabled={!slides.length}
            style={activeVideoJob?.phase === 'processing' ? { color: '#a89fff', border: '1px solid rgba(108,99,255,0.5)' } : {}}
          >
            {activeVideoJob?.phase === 'processing' ? (
              <><Loader2 size={14} className="spin" /> Sinh video ({activeVideoJob.progress || 0}%)</>
            ) : (
              <><Clapperboard size={14} /> Sinh video</>
            )}
          </button>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => setShowVideoLibrary(true)}
          >
            <Library size={14}/> Video của tôi
          </button>
          <button className="btn btn-ghost btn-sm" onClick={handleSave} disabled={saving || slides.length === 0 || !hasUnsavedChanges}>
            {saving ? <><Loader2 size={14} className="spin"/> Đang lưu...</> : <><Save size={14}/> Lưu thay đổi</>}
          </button>
          <button 
            id="export-pptx-btn" 
            className="btn btn-primary btn-sm flex items-center gap-1" 
            onClick={() => setShowPptxMenu((open) => !open)}
            disabled={exporting || loadingSlides || loadedProjectIdRef.current !== id || slides.length === 0}
            style={{ background: '#27ae60', border: '1px solid #219653', color: 'white', height: 32 }}
          >
            {exporting ? <><Loader2 size={14} className="spin"/> Đang xuất...</> : <><Download size={14}/> Xuất PPTX</>}
          </button>
          {showPptxMenu && (
            <div className="e2-export-menu">
              <button type="button" onClick={handleExportEditablePPTX}>
                <strong>Chỉnh sửa được</strong>
                <span>Chữ, ảnh, bảng, biểu đồ và hình khối là object; biểu tượng là ảnh</span>
              </button>
              <button type="button" onClick={handleExportPPTX}>
                <strong>Giữ nguyên giao diện</strong>
                <span>Giống editor nhất, mỗi slide là ảnh</span>
              </button>
            </div>
          )}
          <button className="btn btn-ghost btn-sm" onClick={handleExportPDF} disabled={exporting || loadingSlides || loadedProjectIdRef.current !== id || slides.length === 0}>
            <FileText size={14}/> Xuất PDF
          </button>
        </div>
      </div>

      <div
        className="e2-formatbar"
        style={{
          left: leftPanelWidth + 6,
          right: rightPanelWidth + (rightTab ? 6 : 0),
        }}
      >
        <div id="editor-format-toolbar-host" />
      </div>

      <div className="editor2-body">
        {/* ── LEFT: Slide thumbnails ── */}
        <div className="editor2-thumbs" style={{ width: leftPanelWidth }}>
          <div className="thumbs-header">
            <div className="thumbs-header-row">
              <div className="thumbs-header-title">
                <LayoutTemplate size={15} />
                <span>Slides</span>
                <span className="thumbs-header-count">{slides.length}</span>
              </div>
              <button type="button" className="thumbs-add" onClick={() => addSlide()} title="Thêm slide mới" aria-label="Thêm slide">
                <Plus size={15} strokeWidth={2.4} />
                <span>Thêm</span>
              </button>
            </div>
            <button
              type="button"
              className="thumbs-theme"
              onClick={() => handleTabClick('templates')}
              title={`Template: ${activeTemplate?.name || (isCustomTemplateId(templateId) ? 'Từ file PPTX' : templateId)} — bấm để đổi`}
            >
              <i style={{ background: activeTemplate?.colors?.primary || '#888' }} />
              <span>{activeTemplate?.name || (isCustomTemplateId(templateId) ? 'Từ file PPTX' : templateId)}</span>
            </button>
          </div>
          <div
            className="thumbs-scroll"
            ref={thumbsRef}
            tabIndex={0}
            aria-label="Danh sách slide"
            onKeyDown={(event) => {
              if (!(event.ctrlKey || event.metaKey) || event.key.toLowerCase() !== 'a') return;
              event.preventDefault();
              setSelectedSlideIndexes(new Set(slides.map((_, index) => index)));
            }}
          >
            {slides.map((sl, i) => (
              <div
                key={`${sl.id || 'new'}-${i}`}
                className={`thumb2 ${i === activeIdx ? 'active' : ''} ${selectedSlideIndexes.has(i) ? 'selected' : ''} ${i === draggedSlideIndex ? 'dragging' : ''}`}
                draggable
                onDragStart={(event) => {
                  setDraggedSlideIndex(i);
                  event.dataTransfer.effectAllowed = 'move';
                  event.dataTransfer.setData('text/plain', String(i));
                }}
                onDragOver={(event) => {
                  event.preventDefault();
                  event.dataTransfer.dropEffect = 'move';
                }}
                onDrop={(event) => {
                  event.preventDefault();
                  const fromIndex = Number(event.dataTransfer.getData('text/plain'));
                  if (Number.isInteger(fromIndex)) reorderSlides(fromIndex, i);
                  setDraggedSlideIndex(null);
                }}
                onDragEnd={() => setDraggedSlideIndex(null)}
                onClick={(event) => selectThumbnail(event, i)}
              >
                <span className="thumb2-num">{i + 1}</span>
                <div className="thumb2-preview">
                  <UnifiedSlideView slide={sl} theme={templateId} scale={Math.max(0.1, (leftPanelWidth - 42) / 960)} />
                  <div className="thumb2-actions">
                    <button type="button" title="Kéo để đổi thứ tự" aria-label="Kéo để đổi thứ tự"><GripVertical size={12} /></button>
                    <button type="button" title="Nhân bản slide" aria-label="Nhân bản slide" onClick={(event) => { event.stopPropagation(); duplicateSlide(i); }}><Copy size={12} /></button>
                    <button type="button" title="Xóa slide" aria-label="Xóa slide" onClick={(event) => { event.stopPropagation(); deleteSlide(i); }}><Trash2 size={12} /></button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div
          className={`e2-resizer ${resizingPanel === 'left' ? 'active' : ''}`}
          role="separator"
          aria-label="Thay đổi chiều rộng danh sách slide"
          aria-orientation="vertical"
          onPointerDown={(event) => startPanelResize('left', event)}
          onDoubleClick={() => setLeftPanelWidth(DEFAULT_LEFT_PANEL_WIDTH)}
        />

        {/* ── CENTER: Editable slide ── */}
        <div className="editor2-center" ref={centerRef}>
          <div className="e2-slide-nav">
            <button className="e2-nav-btn" onClick={() => setActiveIdx(Math.max(0, activeIdx - 1))} disabled={activeIdx === 0 || slides.length === 0}>
              <ChevronLeft size={20}/>
            </button>

            <div className="e2-stage" style={{ width: 960 * scale }}>
              <div className="e2-canvas-frame" style={{ width: 960 * scale, height: 540 * scale }}>
                <div style={{ width: 960, height: 540, transform: `scale(${scale})`, transformOrigin: 'top left' }}>
                  <div ref={slideRef} style={{ width: 960, height: 540 }}>
                  {loadingSlides ? (
                    <div style={{
                      width: '100%',
                      height: '100%',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      background: 'linear-gradient(135deg,#0d0d1a,#1c1c3a)',
                      color: '#999',
                      fontSize: '18px',
                      fontWeight: 'bold',
                      flexDirection: 'column',
                      gap: '15px'
                    }}>
                      <div className="spinner" style={{ width: '40px', height: '40px', borderWidth: '3px' }} />
                      <span style={{ fontSize: '14px', color: '#888', fontWeight: '500' }}>Đang tải nội dung slide...</span>
                    </div>
                  ) : slides.length === 0 ? (
                    <div style={{
                      width: '100%',
                      height: '100%',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      background: 'linear-gradient(135deg,#0d0d1a,#1c1c3a)',
                      color: '#999',
                      fontSize: '18px',
                      fontWeight: 'bold',
                      flexDirection: 'column',
                      gap: '10px'
                    }}>
                      {generationProgress.active ? (
                        <div className="e2-generation-wait">
                          <Loader2 size={34} className="spin"/>
                          <strong>Đang tạo bài trình chiếu</strong>
                          <div className="e2-generation-track"><span style={{ width: `${generationProgress.value}%` }}/></div>
                          <span>{generationProgress.value}%</span>
                          <small>{generationProgress.status}</small>
                        </div>
                      ) : (
                        <>
                          <span>Chưa có slides</span>
                          <span style={{ fontSize: '14px', color: '#666' }}>Slides sẽ hiển thị khi hoàn tất tạo</span>
                        </>
                      )}
                    </div>
                  ) : (
                    <ElementCanvas
                      slide={activeSlide}
                      theme={templateId}
                      scale={scale}
                      onUpdate={handleSlideUpdate}
                      onNotify={addToast}
                      readonly={applyingTemplate}
                      preserveTemplateStyles={isCustomTemplateId(templateId)}
                      onAdoptArt={adoptArtAt}
                      onCopyToAllSlides={copyElementToAllSlides}
                    />
                  )}
                  </div>
                </div>
              </div>

              {/* Slide indicator */}
              <div className="e2-slide-info">
                <span className="e2-slide-counter">{activeIdx + 1} / {slides.length || 0}</span>
                <div className="e2-zoom-controls">
                  <button type="button" onClick={() => setZoomPercent((value) => Math.max(50, value - 10))} disabled={zoomPercent <= 50} title="Thu nhỏ" aria-label="Thu nhỏ"><ZoomOut size={14} /></button>
                  <button type="button" className="e2-zoom-value" onClick={() => setZoomPercent(100)} title="Vừa màn hình">{zoomPercent}%</button>
                  <button type="button" onClick={() => setZoomPercent((value) => Math.min(150, value + 10))} disabled={zoomPercent >= 150} title="Phóng to" aria-label="Phóng to"><ZoomIn size={14} /></button>
                </div>
              </div>
            </div>

            <button className="e2-nav-btn" onClick={() => setActiveIdx(Math.min(slides.length - 1, activeIdx + 1))} disabled={activeIdx === slides.length - 1 || slides.length === 0}>
              <ChevronRight size={20}/>
            </button>
          </div>

          {/* Dot navigation */}
          <div className="e2-dots">
            {slides.map((_, i) => (
              <div key={i} className={`e2-dot ${i === activeIdx ? 'active' : ''}`} onClick={() => setActiveIdx(i)} />
            ))}
          </div>
        </div>

        {rightTab && (
          <div
            className={`e2-resizer ${resizingPanel === 'right' ? 'active' : ''}`}
            role="separator"
            aria-label="Thay đổi chiều rộng bảng công cụ"
            aria-orientation="vertical"
            onPointerDown={(event) => startPanelResize('right', event)}
            onDoubleClick={() => setRightPanelWidth(DEFAULT_RIGHT_PANEL_WIDTH)}
          />
        )}

        {/* ── RIGHT: Collapsible Sidebar Panel & Vertical Tabbar ── */}
        <div
          className={`editor2-right ${rightTab ? 'expanded' : 'collapsed'} ${resizingPanel === 'right' ? 'resizing' : ''}`}
          style={rightTab ? { width: rightPanelWidth } : undefined}
        >
          {rightTab && (
            <div className="e2-right-panel-content" style={{ width: Math.max(230, rightPanelWidth - 70) }}>
              <div className="e2-panel-header">
                <h3>
                  {rightTab === 'ai' && 'AI Assistant'}
                  {rightTab === 'templates' && 'Template giao diện'}
                  {rightTab === 'info' && 'Thông tin slide'}
                </h3>
                <button className="e2-panel-close-btn" onClick={() => setRightTab(null)}>
                  <X size={16} />
                </button>
              </div>

              <div className="e2-right-body">
                {rightTab === 'ai' && (
                  <div className="e2-ai-panel">
                    <div className="e2-ai-chat-header">
                      <div className="e2-ai-avatar"><Sparkles size={18} /></div>
                      <div className="e2-ai-greeting">
                        <h4>Trợ lý chỉnh sửa AI</h4>
                        <p>Mô tả điều bạn muốn đổi: nội dung, hình ảnh, bảng biểu, hoặc thêm/xóa slide.</p>
                      </div>
                    </div>

                    {revising ? (
                      <div className="e2-ai-loading-box">
                        <Loader2 size={24} className="spin" style={{ color: '#a89fff', marginBottom: 10 }} />
                        <span className="e2-ai-loading-status">{revisionStatus}</span>
                        <div className="e2-ai-progress-bar">
                          <div className="e2-ai-progress-fill" style={{ width: `${revisionProgress}%` }} />
                        </div>
                        <span className="e2-ai-progress-text">{revisionProgress}%</span>
                        <button className="btn btn-ghost btn-xs text-error mt-2" onClick={handleCancelRevision}>
                          Hủy tác vụ
                        </button>
                      </div>
                    ) : (
                      <>
                        <div className="e2-ai-suggestions">
                          <button className="e2-suggest-btn" onClick={() => setRevisionPrompt('Thêm một ảnh minh họa phù hợp, bám sát nội dung và phong cách của slide này.')}>
                            <ImagePlus size={15} /> Thêm ảnh minh họa
                          </button>
                          <button className="e2-suggest-btn" onClick={() => setRevisionPrompt('Rút gọn nội dung slide này, giữ nguyên các thông tin quan trọng và diễn đạt súc tích, dễ thuyết trình.')}>
                            <Scissors size={15} /> Rút gọn nội dung
                          </button>
                          <button className="e2-suggest-btn" onClick={() => setRevisionPrompt('Cải thiện tiêu đề slide này để rõ trọng tâm và thu hút hơn, không làm thay đổi ý nghĩa chính.')}>
                            <Type size={15} /> Cải thiện tiêu đề
                          </button>
                          <button className="e2-suggest-btn" onClick={() => setRevisionPrompt('Trình bày nội dung slide này trực quan hơn bằng bảng hoặc biểu đồ phù hợp, giữ nguyên dữ liệu và thông điệp chính.')}>
                            <BarChart3 size={15} /> Trình bày trực quan
                          </button>
                        </div>

                        {revisionError && (
                          <div className="e2-ai-error" role="alert">
                            <AlertCircle size={15} aria-hidden="true" />
                            <div>
                              <strong>{revisionError.title}</strong>
                              <span>{revisionError.detail}</span>
                              <div className="e2-ai-error-actions">
                                {revisionError.action === 'upgrade' && <button type="button" className="primary" onClick={() => navigate('/pricing')}>Nâng cấp gói</button>}
                                <button type="button" onClick={() => setRevisionError(null)}>Đóng</button>
                              </div>
                            </div>
                          </div>
                        )}
                        <div className="e2-ai-input-area">
                          <textarea
                            className="e2-ai-textarea"
                            placeholder="Nhập yêu cầu của bạn (ví dụ: 'Đổi tiêu đề thành...', 'Thêm slide mới...')"
                            value={revisionPrompt}
                            onChange={(e) => { setRevisionPrompt(e.target.value); if (revisionError) setRevisionError(null); }}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter' && !e.shiftKey) {
                                e.preventDefault();
                                handleAIRevise();
                              }
                            }}
                          />
                          <div className="e2-ai-input-footer">
                            <span className="e2-ai-input-tip">Áp dụng cho <strong>slide {activeIdx + 1}</strong> · Enter để gửi</span>
                            <button className="e2-ai-send-btn" onClick={() => handleAIRevise()} disabled={!revisionPrompt.trim()}>
                              <ChevronRight size={16} />
                            </button>
                          </div>
                        </div>
                      </>
                    )}
                  </div>
                )}

                {rightTab === 'templates' && (
                  <div className="e2-template-panel">
                    <div className="e2-template-tabs" role="tablist" aria-label="Nguồn template">
                      <button
                        type="button"
                        role="tab"
                        aria-selected={templateMode === 'default'}
                        className={templateMode === 'default' ? 'active' : ''}
                        onClick={() => setTemplateMode('default')}
                      >
                        Mặc định
                      </button>
                      <button
                        type="button"
                        role="tab"
                        aria-selected={templateMode === 'custom'}
                        className={templateMode === 'custom' ? 'active' : ''}
                        onClick={() => setTemplateMode('custom')}
                      >
                        Tùy chỉnh
                      </button>
                    </div>

                    <div className="e2-settings">
                      <div className="e2-set-row">
                        <span><Hash size={15} /> Số trang</span>
                        <button
                          type="button"
                          role="switch"
                          aria-checked={pageNumbersOn}
                          aria-label="Số trang"
                          className={`e2-switch${pageNumbersOn ? ' on' : ''}`}
                          onClick={togglePageNumbers}
                          title="Thêm hoặc bỏ số trang ở mọi slide"
                        />
                      </div>
                      <div className="e2-set-row">
                        <span><Sparkles size={15} /> Hiện từng ý khi trình chiếu</span>
                        <button
                          type="button"
                          role="switch"
                          aria-checked={deckMaster.revealBullets}
                          aria-label="Hiện từng ý khi trình chiếu"
                          className={`e2-switch${deckMaster.revealBullets ? ' on' : ''}`}
                          onClick={() => updateDeckMaster({ revealBullets: !deckMaster.revealBullets })}
                        />
                      </div>
                      <div className="e2-set-block">
                        <span className="e2-set-label">Chuyển trang</span>
                        <div className="e2-seg" role="radiogroup" aria-label="Hiệu ứng chuyển trang">
                          {[['none', 'Không'], ['fade', 'Mờ'], ['push', 'Trượt'], ['zoom', 'Phóng']].map(([value, label]) => (
                            <button
                              key={value}
                              type="button"
                              role="radio"
                              aria-checked={deckMaster.transition === value}
                              className={deckMaster.transition === value ? 'active' : ''}
                              onClick={() => updateDeckMaster({ transition: value })}
                            >
                              {label}
                            </button>
                          ))}
                        </div>
                      </div>
                    </div>

                    {templateMode === 'default' ? (
                      <>
                        {ornamentsAdopted && isGeneratedTheme(templateId) && (
                          <button type="button" className="e2-save-theme-btn" style={{ marginTop: 0, marginBottom: 12 }} onClick={restoreOrnaments}>
                            Khôi phục trang trí của template
                          </button>
                        )}
                        <div className="e2-template-grid">
                          {[...(generatedOption ? [generatedOption] : []), ...TEMPLATES].map((tmpl) => (
                            <TemplateCard
                              key={tmpl.id}
                              template={tmpl}
                              selected={templateId === tmpl.id}
                              disabled={applyingTemplate || generatingTheme || templateUploading || Boolean(templateDeletingId)}
                              onSelect={handleTemplateSwitch}
                            />
                          ))}
                        </div>
                        {generatedOption && (
                          <>
                            <button type="button" className="e2-save-theme-btn e2-tune-toggle" onClick={() => setTunerOpen((open) => !open)} aria-expanded={tunerOpen}>
                              {tunerOpen ? 'Ẩn tuỳ chỉnh' : 'Tuỳ chỉnh màu, chữ, trang trí…'}
                            </button>
                            {tunerOpen && (
                              <ThemeTuner
                                code={templateId}
                                disabled={applyingTemplate || generatingTheme}
                                onChange={tuneTheme}
                                onPreviewHue={previewHue}
                                onReset={genOriginRef.current.projectId === id && genOriginRef.current.code && genOriginRef.current.code !== templateId ? resetTunedTheme : undefined}
                              />
                            )}
                          </>
                        )}
                        {generatedOption && !savedThemes.some((item) => item.description === templateId) && (
                          <button type="button" className="e2-save-theme-btn" onClick={saveCurrentTheme}>
                            <Save size={14} /> Lưu template này vào thư viện
                          </button>
                        )}
                        {savedThemes.length > 0 && (
                          <>
                            <p className="e2-panel-hint">Template đã lưu của bạn</p>
                            <div className="e2-template-grid">
                              {savedThemes.map((saved) => savedThemeOption(saved)).map((tmpl) => (
                                <TemplateCard
                                  key={tmpl.savedId}
                                  template={tmpl}
                                  selected={templateId === tmpl.id}
                                  disabled={applyingTemplate || generatingTheme || templateUploading || Boolean(templateDeletingId)}
                                  onSelect={handleTemplateSwitch}
                                  onDelete={deleteSavedTheme}
                                />
                              ))}
                            </div>
                          </>
                        )}
                      </>
                    ) : (
                      <>
                        <div className="e2-template-custom-head">
                          <p className="e2-panel-hint">Template PowerPoint của bạn</p>
                          <label className={`e2-template-upload-btn ${(templateUploading || applyingTemplate) ? 'disabled' : ''}`}>
                            {templateUploading ? <Loader2 size={15} className="spin" /> : <UploadCloud size={15} />}
                            {templateUploading ? 'Đang xử lý...' : 'Upload'}
                            <input
                              type="file"
                              accept=".pptx,.potx,application/vnd.openxmlformats-officedocument.presentationml.presentation"
                              onChange={handleTemplateUpload}
                              disabled={templateUploading || applyingTemplate}
                              hidden
                            />
                          </label>
                        </div>

                        {customTemplateOptions.length ? (
                          <div className="e2-template-grid">
                            {customTemplateOptions.map((tmpl) => (
                              <TemplateCard
                                key={tmpl.id}
                                template={tmpl}
                                selected={templateId === tmpl.id}
                                disabled={applyingTemplate || templateUploading || Boolean(templateDeletingId)}
                                deleting={templateDeletingId === tmpl.id}
                                onSelect={handleTemplateSwitch}
                                onDelete={handleTemplateDelete}
                              />
                            ))}
                          </div>
                        ) : (
                          <div className="e2-template-empty">
                            <div className="e2-template-empty-icon"><Presentation size={30} /></div>
                            <h4>Chưa có template tùy chỉnh</h4>
                            <p>Upload file PPTX hoặc POTX để áp dụng thiết kế cho bài trình chiếu.</p>
                            <label className={`e2-template-upload-primary ${templateUploading ? 'disabled' : ''}`}>
                              {templateUploading ? <Loader2 size={16} className="spin" /> : <UploadCloud size={16} />}
                              {templateUploading ? 'Đang phân tích...' : 'Upload template'}
                              <input
                                type="file"
                                accept=".pptx,.potx,application/vnd.openxmlformats-officedocument.presentationml.presentation"
                                onChange={handleTemplateUpload}
                                disabled={templateUploading}
                                hidden
                              />
                            </label>
                          </div>
                        )}
                      </>
                    )}
                  </div>
                )}

                {rightTab === 'info' && (
                  <div className="e2-info-panel">
                    <InfoRow label="Slide hiện tại" value={`${activeIdx + 1} / ${slides.length}`} />
                    <label className="e2-layout-field">
                      <span>Loại nội dung</span>
                      <span className="e2-select-wrap">
                      <select
                        value={activeSlide?.type || 'content'}
                        title="Đổi loại nội dung sẽ dựng lại khung của slide này"
                        onChange={(event) => requestSlideTypeChange(event.target.value)}
                      >
                        {SLIDE_LAYOUTS
                          .filter((layout) => layout.value !== 'twoColumn' || activeSlide?.type === 'twoColumn')
                          .map((layout) => <option key={layout.value} value={layout.value}>{layout.label}</option>)}
                      </select>
                      <ChevronDown size={14} />
                      </span>
                    </label>
                    <LayoutPicker
                      slide={activeSlide}
                      theme={layoutThemeFor(activeSlide, templateId)}
                      disabled={applyingTemplate}
                      onPick={changeSlideVariant}
                      onAutoMix={autoMixLayouts}
                      onResetAll={resetAllLayouts}
                    />
                    <InfoRow label="Template" value={activeTemplate?.name || (isCustomTemplateId(templateId) ? 'Từ file PPTX' : templateId)} />
                    <InfoRow label="Tiêu đề" value={activeSlide?.title || '—'} stacked />
                    {activeSlide?.pedagogicalRole && (
                      <InfoRow
                        label="Vai trò bài giảng"
                        value={PEDAGOGICAL_ROLE_LABELS[activeSlide.pedagogicalRole] || activeSlide.pedagogicalRole}
                      />
                    )}
                    {activeSlide?.sourcePages?.length > 0 && (
                      <InfoRow label="Trang nguồn" value={activeSlide.sourcePages.join(', ')} />
                    )}
                    
                    <div className="e2-notes-section">
                      <label className="e2-notes-label" htmlFor="speaker-notes">
                        Ghi chú diễn giả
                        <span>Speaker notes</span>
                      </label>
                      <textarea
                        id="speaker-notes"
                        className="e2-notes-textarea"
                        placeholder="Nhập ghi chú hoặc lời thoại cho slide này..."
                        value={activeSlide?.notes || ''}
                        onChange={(e) => {
                          const updated = { ...activeSlide, notes: e.target.value };
                          handleSlideUpdate(updated);
                        }}
                      />
                      <div className="e2-notes-meta">
                        <span>{activeSlide?.notes?.trim().split(/\s+/).filter(Boolean).length || 0} từ</span>
                        <span>{activeSlide?.notes?.length || 0} ký tự</span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          <div className="e2-vertical-tabbar">
            <button className={`e2-vtab-btn ${rightTab === 'ai' ? 'active' : ''}`} onClick={() => handleTabClick('ai')}>
              <Sparkles size={18} />
              <span>AI Assistant</span>
            </button>
            <button className={`e2-vtab-btn ${rightTab === 'templates' ? 'active' : ''}`} onClick={() => handleTabClick('templates')}>
              <Palette size={18} />
              <span>Template</span>
            </button>
            <button className={`e2-vtab-btn ${rightTab === 'info' ? 'active' : ''}`} onClick={() => handleTabClick('info')}>
              <Info size={18} />
              <span>Thông tin</span>
            </button>
          </div>
        </div>
      </div>
      <VideoGenerationModal
        open={showVideoModal}
        onClose={() => setShowVideoModal(false)}
        slides={slides}
        projectName={title}
        projectId={id}
        onPreparePresentation={preparePresentationForVideo}
        onNotify={addToast}
      />
      <VideoLibraryModal
        open={showVideoLibrary}
        onClose={() => setShowVideoLibrary(false)}
        onNotify={addToast}
        projectId={id}
      />

      <div ref={exportStageRef} className="e2-export-stage" aria-hidden="true" style={{ position: 'fixed', left: -12000, top: 0, width: 960, pointerEvents: 'none' }}>
        {slides.map((slide, index) => (
          <div key={slide.id || index} data-export-slide style={{ width: 960, height: 540, overflow: 'hidden' }}>
            <UnifiedSlideView slide={slide} theme={templateId} scale={1} />
          </div>
        ))}
      </div>
      {presenting && activeSlide && (
        <div
          ref={presentationRef}
          className="e2-presentation"
          onClick={(event) => {
            if (event.clientX < window.innerWidth / 2) presentPrev();
            else presentNext();
          }}
        >
          {presenterMode ? (
            <PresenterView
              slides={slides}
              activeIdx={activeIdx}
              revealStage={revealStage}
              revealEnabled={deckMaster.revealBullets}
              revealTotal={countRevealStages(activeSlide)}
              theme={templateId}
              audienceOpen={audienceOpen}
              onNext={presentNext}
              onPrev={presentPrev}
              onOpenAudience={openAudienceWindow}
              onExit={stopPresentation}
            />
          ) : (
          <div
            className="e2-presentation-slide"
            style={{
              width: 960 * Math.min(presentationViewport.width / 960, presentationViewport.height / 540),
              height: 540 * Math.min(presentationViewport.width / 960, presentationViewport.height / 540),
            }}
          >
            <SlideTransition slideKey={activeIdx} transition={deckMaster.transition}>
              <UnifiedSlideView
                slide={activeSlide}
                theme={templateId}
                scale={Math.min(presentationViewport.width / 960, presentationViewport.height / 540)}
                revealStage={deckMaster.revealBullets ? revealStage : null}
              />
            </SlideTransition>
          </div>
          )}
          {!presenterMode && <div className="e2-presentation-controls" onClick={(event) => event.stopPropagation()}>
            <button onClick={presentPrev} disabled={activeIdx === 0 && revealStage === 0} title="Lùi (ý trước / slide trước)">
              <ChevronLeft size={20}/>
            </button>
            <span><Presentation size={16}/> {activeIdx + 1} / {slides.length}</span>
            <button onClick={presentNext} disabled={activeIdx === slides.length - 1 && (!deckMaster.revealBullets || revealStage >= countRevealStages(activeSlide))} title="Tiếp (ý kế / slide sau)">
              <ChevronRight size={20}/>
            </button>
          </div>}
          {!presenterMode && <button className="e2-presentation-exit" onClick={(event) => { event.stopPropagation(); stopPresentation(); }} title="Thoát trình chiếu">
            <X size={20}/>
          </button>}
        </div>
      )}
    </div>
  );
}

function InfoRow({ label, value, stacked = false }) {
  return (
    <div className={`e2-info-row ${stacked ? 'stacked' : ''}`}>
      <span className="e2-info-label">{label}</span>
      <strong className="e2-info-value" title={String(value)}>{value}</strong>
    </div>
  );
}
