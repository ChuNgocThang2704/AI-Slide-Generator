import { useState, useRef, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useProjectStore, useUIStore } from '../../store';
import ElementCanvas from '../../components/slides/ElementCanvas';
import { projectService } from '../../services/documentService';
import { exportSlidesToPptx } from '../../services/pptxExportService';
import { formatSlidePage, toSlidePageUpdate } from '../../utils/slideMapping';
import {
  ChevronLeft, ChevronRight, Download, ArrowLeft,
  LayoutTemplate, Check, Loader2, Maximize2, Minimize2,
  Info, Palette, Save, Sparkles, X, FileText, Play, Presentation, Cloud, CloudOff,
  Undo2, Redo2, Copy, Trash2, GripVertical, Plus, ZoomIn, ZoomOut
} from 'lucide-react';
import './EditorPage.css';

// Template definitions (tạm thời hardcoded)
const TEMPLATES = [
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
];

const DEFAULT_LEFT_PANEL_WIDTH = 180;
const DEFAULT_RIGHT_PANEL_WIDTH = 390;
const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
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

function UnifiedSlideView({ slide, theme, index = 0, scale = 1 }) {
  return (
    <div style={{ width: 960 * scale, height: 540 * scale, overflow: 'hidden' }}>
      <div style={{ width: 960, height: 540, transform: `scale(${scale})`, transformOrigin: 'top left' }}>
        <ElementCanvas slide={slide} theme={theme} scale={1} readonly />
      </div>
    </div>
  );
}

export default function EditorPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { projects, setProjects, updateProject } = useProjectStore();
  const { addToast } = useUIStore();

  // ── State ──
  const [activeIdx, setActiveIdx] = useState(0);
  const [selectedSlideIndexes, setSelectedSlideIndexes] = useState(() => new Set([0]));
  const [exporting, setExporting] = useState(false);
  const [showPptxMenu, setShowPptxMenu] = useState(false);
  const [saving, setSaving] = useState(false);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [saveState, setSaveState] = useState('saved');
  const [fullscreen, setFullscreen] = useState(false);
  const [presenting, setPresenting] = useState(false);
  const [presentationViewport, setPresentationViewport] = useState({ width: window.innerWidth, height: window.innerHeight });
  const [rightTab, setRightTab] = useState('ai');
  const [slides, setSlides] = useState([]);
  const [revisionPrompt, setRevisionPrompt] = useState('');
  const [revisionScope, setRevisionScope] = useState('slide'); // 'slide' or 'deck'
  const [revising, setRevising] = useState(false);
  const [revisionProgress, setRevisionProgress] = useState(0);
  const [revisionStatus, setRevisionStatus] = useState('');
  const [exportsList, setExportsList] = useState([]);
  const [loadingExports, setLoadingExports] = useState(false);
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
    const fetchSlides = async () => {
      setLoadingSlides(true);
      try {
        let project = projects.find((p) => p.id === id);
        if (!project) {
          project = await projectService.getById(id);
          setProjects([project, ...projects.filter((item) => item.id !== project.id)]);
        }
        const pages = await projectService.getSlidePages(id);
        if (pages && pages.length > 0) {
          const formattedSlides = pages.map(formatSlidePage);
          slidesRef.current = formattedSlides;
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
          hasUnsavedChangesRef.current = false;
          setSlides([]);
        }
      } catch (err) {
        console.error('Không thể tải slides từ API:', err);
        setSlides([]);
        addToast('Không thể mở project: ' + err.message, 'error');
        navigate('/dashboard');
      } finally {
        setLoadingSlides(false);
      }
    };

    fetchSlides();
  }, [id]);

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
    const project = projects.find((p) => p.id === id);
    if (project && (project.status === 1 || project.status === 3 || project.status === 'completed' || project.status === 'DONE')) {
      const fetchExports = async () => {
        setLoadingExports(true);
        try {
          const list = await projectService.getExports(id);
          setExportsList(list || []);
        } catch (err) {
          console.error('Không thể tải danh sách file xuất bản:', err);
        } finally {
          setLoadingExports(false);
        }
      };
      fetchExports();
    }
  }, [id, projects]);

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
          const formattedSlides = pages.map(formatSlidePage);
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

  useEffect(() => {
    if (!presenting) return undefined;

    const nextSlide = () => setActiveIdx((index) => Math.min(slides.length - 1, index + 1));
    const previousSlide = () => setActiveIdx((index) => Math.max(0, index - 1));
    const handleKeyDown = (event) => {
      if (['ArrowRight', 'ArrowDown', 'PageDown', ' '].includes(event.key)) {
        event.preventDefault();
        nextSlide();
      } else if (['ArrowLeft', 'ArrowUp', 'PageUp'].includes(event.key)) {
        event.preventDefault();
        previousSlide();
      } else if (event.key === 'Home') {
        event.preventDefault();
        setActiveIdx(0);
      } else if (event.key === 'End') {
        event.preventDefault();
        setActiveIdx(Math.max(0, slides.length - 1));
      } else if (event.key === 'Escape') {
        setPresenting(false);
      }
    };
    const handleResize = () => setPresentationViewport({ width: window.innerWidth, height: window.innerHeight });
    const handleFullscreenChange = () => {
      if (!document.fullscreenElement) setPresenting(false);
    };

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('resize', handleResize);
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('resize', handleResize);
      document.removeEventListener('fullscreenchange', handleFullscreenChange);
    };
  }, [presenting, slides.length]);

  // ── Handlers ──
  const handleSlideUpdate = useCallback((updatedSlide) => {
    const now = Date.now();
    const startsNewHistoryStep = activeIdx !== lastHistorySlideRef.current || now - lastHistoryAtRef.current > 800;
    if (startsNewHistoryStep) {
      undoStackRef.current.push(slidesRef.current);
      if (undoStackRef.current.length > 50) undoStackRef.current.shift();
    }
    lastHistoryAtRef.current = now;
    lastHistorySlideRef.current = activeIdx;
    redoStackRef.current = [];
    setHistoryVersion((version) => version + 1);
    editVersionRef.current += 1;
    hasUnsavedChangesRef.current = true;
    setHasUnsavedChanges(true);
    setSaveState('pending');
    const newSlides = [...slidesRef.current];
    newSlides[activeIdx] = updatedSlide;
    slidesRef.current = newSlides;
    setSlides(newSlides);
  }, [activeIdx]);

  const applyHistorySnapshot = useCallback((nextSlides) => {
    slidesRef.current = nextSlides;
    setSlides(nextSlides);
    editVersionRef.current += 1;
    hasUnsavedChangesRef.current = true;
    setHasUnsavedChanges(true);
    setSaveState('pending');
    setHistoryVersion((version) => version + 1);
  }, []);

  const handleUndo = useCallback(() => {
    if (!undoStackRef.current.length) return;
    const previous = undoStackRef.current.pop();
    redoStackRef.current.push(slidesRef.current);
    lastHistoryAtRef.current = 0;
    applyHistorySnapshot(previous);
  }, [applyHistorySnapshot]);

  const handleRedo = useCallback(() => {
    if (!redoStackRef.current.length) return;
    const next = redoStackRef.current.pop();
    undoStackRef.current.push(slidesRef.current);
    lastHistoryAtRef.current = 0;
    applyHistorySnapshot(next);
  }, [applyHistorySnapshot]);

  const handleDeckUpdate = useCallback((nextSlides, nextActiveIdx) => {
    undoStackRef.current.push(slidesRef.current);
    if (undoStackRef.current.length > 50) undoStackRef.current.shift();
    redoStackRef.current = [];
    lastHistoryAtRef.current = 0;
    lastHistorySlideRef.current = -1;
    slidesRef.current = nextSlides;
    setSlides(nextSlides);
    setActiveIdx(Math.max(0, Math.min(nextActiveIdx, nextSlides.length - 1)));
    editVersionRef.current += 1;
    hasUnsavedChangesRef.current = true;
    setHasUnsavedChanges(true);
    setSaveState('pending');
    setHistoryVersion((version) => version + 1);
  }, []);

  const duplicateSlide = useCallback((index) => {
    const duplicate = structuredClone(slidesRef.current[index]);
    delete duplicate.id;
    delete duplicate.pageIndex;
    const nextSlides = [...slidesRef.current];
    nextSlides.splice(index + 1, 0, duplicate);
    handleDeckUpdate(nextSlides, index + 1);
    addToast('Đã nhân bản slide', 'success');
  }, [addToast, handleDeckUpdate]);

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
    const nextSlides = [...slidesRef.current];
    nextSlides.splice(insertIndex, 0, blankSlide);
    handleDeckUpdate(nextSlides, insertIndex);
    addToast('Đã thêm slide mới', 'success');
  }, [activeIdx, addToast, handleDeckUpdate]);

  const deleteSlide = useCallback((index) => {
    if (slidesRef.current.length <= 1) {
      addToast('Bài trình chiếu cần ít nhất một slide', 'warning');
      return;
    }
    const nextSlides = slidesRef.current.filter((_, slideIndex) => slideIndex !== index);
    const nextActive = activeIdx > index ? activeIdx - 1 : Math.min(activeIdx, nextSlides.length - 1);
    handleDeckUpdate(nextSlides, nextActive);
    addToast('Đã xóa slide', 'success');
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
      document.activeElement?.blur();
      if (key === 'y' || event.shiftKey) handleRedo();
      else handleUndo();
    };
    window.addEventListener('keydown', handleHistoryShortcut);
    return () => window.removeEventListener('keydown', handleHistoryShortcut);
  }, [handleRedo, handleUndo]);

  const handleTemplateSwitch = (tmplId) => {
    const tmpl = TEMPLATES.find((t) => t.id === tmplId);
    if (!tmpl) return;
    updateProject(id, { templateId: tmplId });
    addToast(`Template đổi sang "${tmpl.name}" ✓`, 'success');
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

    setRevising(true);
    setRevisionProgress(5);
    setRevisionStatus('Đang lưu slides hiện tại...');

    try {
      // 1. Sync slides first so manual changes are saved
      const pageUpdates = slidesRef.current.map(toSlidePageUpdate);

      await projectService.syncSlidePages(id, pageUpdates);
      setRevisionProgress(15);
      setRevisionStatus('Đang gửi yêu cầu chỉnh sửa lên AI...');

      // 2. Trigger AI Revise
      const payload = {
        revisionPrompt: promptToSend.trim(),
        revisionScope: revisionScope,
        slideNumber: revisionScope === 'slide' ? activeIdx + 1 : null
      };

      const reviseRes = await projectService.revise(id, payload);
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
              const formattedSlides = pages.map(formatSlidePage);

              slidesRef.current = formattedSlides;
              undoStackRef.current = [];
              redoStackRef.current = [];
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
            addToast(progressRes.errorMessage || 'Lỗi khi AI thực hiện chỉnh sửa', 'error');
            setRevising(false);
          }
        } catch (pollErr) {
          console.error('Error polling revision progress:', pollErr);
        }
      }, 3000);

    } catch (err) {
      console.error('AI Revise error:', err);
      addToast(err.message || 'Lỗi khi gửi yêu cầu chỉnh sửa slide', 'error');
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
      addToast('✅ Lưu thay đổi thành công!', 'success');
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
      addToast('Đã đổi tên bài trình chiếu', 'success');
    } catch (error) {
      addToast(error.message || 'Không thể đổi tên bài trình chiếu', 'error');
    } finally {
      setSavingTitle(false);
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
    setShowPptxMenu(false);
    setExporting(true);
    addToast('Đang lưu slides trước khi xuất...', 'info');

    try {
      // 1. Sync slides to backend database first to make sure notes, titles, and layout are saved
      const pageUpdates = slidesRef.current.map(toSlidePageUpdate);

      await projectService.syncSlidePages(id, pageUpdates);
      addToast('Đang tạo file PPTX có thể chỉnh sửa...', 'info');

      const projectName = projects.find((p) => p.id === id)?.name || 'presentation';
      const { captureSlides } = await import('../../services/visualExportService');
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

  const handleExportEditablePPTX = async () => {
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
    setExporting(true);
    addToast('Đang tạo file PDF...', 'info');
    try {
      await projectService.syncSlidePages(id, slidesRef.current.map(toSlidePageUpdate));
      const projectName = projects.find((p) => p.id === id)?.name || 'presentation';
      const { captureSlides, exportSnapshotsToPdf } = await import('../../services/visualExportService');
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

  const startPresentation = () => {
    if (!slides.length) return;
    setPresentationViewport({ width: window.innerWidth, height: window.innerHeight });
    setPresenting(true);
    document.documentElement.requestFullscreen?.().catch(() => {});
  };

  const stopPresentation = () => {
    setPresenting(false);
    if (document.fullscreenElement) document.exitFullscreen?.().catch(() => {});
  };

  const getScale = () => Math.max(0.35, Math.min(
    1,
    (centerSize.width - 130) / 960,
    (centerSize.height - 105) / 540,
  ));

  // ── Render ──
  const project = projects.find((p) => p.id === id);
  if (!project) {
    return <div className="editor-loading"><div className="spinner" /></div>;
  }

  const { name: title, templateId = 'clean-white' } = project;
  const activeSlide = slides[activeIdx];
  const fitScale = getScale();
  const scale = fitScale * zoomPercent / 100;

  const pptxExport = exportsList.find(exp => exp.exportType === 'PPTX' || exp.type === 'PPTX');
  const pptxUrl = pptxExport?.s3Url || pptxExport?.url || project.slideUrl || (project.status === 2 ? '#' : null);

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
            <span className="e2-badge">{slides.length} slides</span>
            <span className="e2-template-chip" style={{ color: TEMPLATES.find(t=>t.id===templateId)?.colors?.primary || '#666' }}>
              {TEMPLATES.find((t) => t.id === templateId)?.name || templateId}
            </span>
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
          <button className="btn btn-ghost btn-sm" onClick={startPresentation} disabled={!slides.length}>
            <Play size={14}/> Trình chiếu
          </button>
          <button className="btn btn-ghost btn-sm" onClick={handleSave} disabled={saving || slides.length === 0 || !hasUnsavedChanges}>
            {saving ? <><Loader2 size={14} className="spin"/> Đang lưu...</> : <><Save size={14}/> Lưu thay đổi</>}
          </button>
          <button 
            id="export-pptx-btn" 
            className="btn btn-primary btn-sm flex items-center gap-1" 
            onClick={() => setShowPptxMenu((open) => !open)}
            disabled={exporting || slides.length === 0} 
            style={{ background: '#27ae60', border: '1px solid #219653', color: 'white', height: 32 }}
          >
            {exporting ? <><Loader2 size={14} className="spin"/> Đang xuất...</> : <><Download size={14}/> Xuất PPTX</>}
          </button>
          {showPptxMenu && (
            <div className="e2-export-menu">
              <button type="button" onClick={handleExportEditablePPTX}>
                <strong>Chỉnh sửa được</strong>
                <span>Text, ảnh, bảng và biểu đồ là object</span>
              </button>
              <button type="button" onClick={handleExportPPTX}>
                <strong>Giữ nguyên giao diện</strong>
                <span>Giống editor nhất, mỗi slide là ảnh</span>
              </button>
            </div>
          )}
          <button className="btn btn-ghost btn-sm" onClick={handleExportPDF} disabled={exporting || slides.length === 0}>
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
            <div><LayoutTemplate size={14}/> <span>Slides</span></div>
            <button type="button" onClick={() => addSlide()} title="Thêm slide" aria-label="Thêm slide"><Plus size={14} /></button>
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
                  <UnifiedSlideView slide={sl} theme={templateId} index={i} scale={Math.max(0.1, (leftPanelWidth - 42) / 960)} />
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
                          <strong>Đang tạo slide với AI</strong>
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
                  {rightTab === 'templates' && 'Templates'}
                  {rightTab === 'info' && 'Slide Info'}
                </h3>
                <button className="e2-panel-close-btn" onClick={() => setRightTab(null)}>
                  <X size={16} />
                </button>
              </div>

              <div className="e2-right-body">
                {rightTab === 'ai' && (
                  <div className="e2-ai-panel">
                    <div className="e2-ai-chat-header">
                      <div className="e2-ai-avatar">Charles</div>
                      <div className="e2-ai-greeting">
                        <h4>Hey, I'm Charles your AI Assistant</h4>
                        <p>Tôi có thể giúp bạn chỉnh sửa nội dung, hình ảnh, bảng biểu hoặc thêm/xóa slide bằng ngôn ngữ tự nhiên.</p>
                      </div>
                    </div>

                    <div className="e2-ai-scope-selector">
                      <label className="e2-scope-label">Phạm vi chỉnh sửa:</label>
                      <div className="e2-scope-options">
                        <button 
                          className={`e2-scope-btn ${revisionScope === 'slide' ? 'active' : ''}`}
                          onClick={() => setRevisionScope('slide')}
                        >
                          Slide {activeIdx + 1}
                        </button>
                        <button 
                          className={`e2-scope-btn ${revisionScope === 'deck' ? 'active' : ''}`}
                          onClick={() => setRevisionScope('deck')}
                        >
                          Toàn bộ slide
                        </button>
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
                            Thêm ảnh minh họa
                          </button>
                          <button className="e2-suggest-btn" onClick={() => setRevisionPrompt('Rút gọn nội dung slide này, giữ nguyên các thông tin quan trọng và diễn đạt súc tích, dễ thuyết trình.')}>
                            Rút gọn nội dung
                          </button>
                          <button className="e2-suggest-btn" onClick={() => setRevisionPrompt('Cải thiện tiêu đề slide này để rõ trọng tâm và thu hút hơn, không làm thay đổi ý nghĩa chính.')}>
                            Cải thiện tiêu đề
                          </button>
                          <button className="e2-suggest-btn" onClick={() => setRevisionPrompt('Trình bày nội dung slide này trực quan hơn bằng bảng hoặc biểu đồ phù hợp, giữ nguyên dữ liệu và thông điệp chính.')}>
                            Trình bày trực quan
                          </button>
                        </div>

                        <div className="e2-ai-input-area">
                          <textarea
                            className="e2-ai-textarea"
                            placeholder="Nhập yêu cầu của bạn (ví dụ: 'Đổi tiêu đề thành...', 'Thêm slide mới...')"
                            value={revisionPrompt}
                            onChange={(e) => setRevisionPrompt(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter' && !e.shiftKey) {
                                e.preventDefault();
                                handleAIRevise();
                              }
                            }}
                          />
                          <div className="e2-ai-input-footer">
                            <span className="e2-ai-input-tip">Nhấn Enter để gửi</span>
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
                    <p className="e2-panel-hint">Chọn template để áp dụng ngay cho toàn bộ presentation</p>
                    <div className="e2-template-grid">
                      {TEMPLATES.map((tmpl) => (
                        <div
                          key={tmpl.id}
                          className={`e2-tmpl-card ${templateId === tmpl.id ? 'selected' : ''}`}
                          onClick={() => handleTemplateSwitch(tmpl.id)}
                        >
                          {templateId === tmpl.id && <div className="e2-tmpl-check"><Check size={11}/></div>}
                          <div className="e2-tmpl-thumb" style={{ background: tmpl.preview }}>
                            <div className="e2-tmpl-th-title" style={{ color: tmpl.isLight ? '#1a1a1a' : 'white' }}>
                              {tmpl.name}
                            </div>
                            <div className="e2-tmpl-th-bar" style={{ background: tmpl.colors.primary }} />
                          </div>
                          <div className="e2-tmpl-name">{tmpl.name}</div>
                          {tmpl.isDefault && <div className="e2-tmpl-default-tag">Mặc định</div>}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {rightTab === 'info' && (
                  <div className="e2-info-panel">
                    <InfoRow label="Slide hiện tại" value={`${activeIdx + 1} / ${slides.length}`} />
                    <label className="e2-layout-field">
                      <span>Bố cục</span>
                      <select value={activeSlide?.type || 'content'} onChange={(event) => changeSlideLayout(event.target.value)}>
                        {SLIDE_LAYOUTS.map((layout) => <option key={layout.value} value={layout.value}>{layout.label}</option>)}
                      </select>
                    </label>
                    <InfoRow label="Template" value={TEMPLATES.find(t => t.id === templateId)?.name || templateId} />
                    <InfoRow label="Tiêu đề" value={activeSlide?.title || '—'} />
                    
                    <div style={{ marginTop: 20, borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: 15 }}>
                      <label style={{ display: 'block', fontSize: '0.85rem', color: 'rgba(255,255,255,0.45)', marginBottom: 8, fontWeight: 'bold' }}>Ghi chú diễn giả (Speaker Notes)</label>
                      <textarea
                        style={{
                          width: '100%',
                          height: 120,
                          background: 'rgba(255,255,255,0.05)',
                          border: '1px solid rgba(255,255,255,0.1)',
                          borderRadius: 6,
                          color: 'white',
                          padding: 8,
                          fontSize: '0.85rem',
                          resize: 'none',
                          outline: 'none',
                          transition: 'border-color 0.2s',
                        }}
                        placeholder="Nhập ghi chú hoặc lời thoại cho slide này..."
                        value={activeSlide?.notes || ''}
                        onChange={(e) => {
                          const updated = { ...activeSlide, notes: e.target.value };
                          handleSlideUpdate(updated);
                        }}
                        onFocus={(e) => e.target.style.borderColor = 'rgba(255,255,255,0.25)'}
                        onBlur={(e) => e.target.style.borderColor = 'rgba(255,255,255,0.1)'}
                      />
                    </div>

                    <div className="e2-notes-meta">
                      <span>{activeSlide?.notes?.trim().split(/\s+/).filter(Boolean).length || 0} từ</span>
                      <span>{activeSlide?.notes?.length || 0} ký tự</span>
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
              <span>Slide info</span>
            </button>
          </div>
        </div>
      </div>
      <div ref={exportStageRef} className="e2-export-stage" aria-hidden="true" style={{ position: 'fixed', left: -12000, top: 0, width: 960, pointerEvents: 'none' }}>
        {slides.map((slide, index) => (
          <div key={slide.id || index} data-export-slide style={{ width: 960, height: 540, overflow: 'hidden' }}>
            <UnifiedSlideView slide={slide} theme={templateId} index={index} scale={1} />
          </div>
        ))}
      </div>
      {presenting && activeSlide && (
        <div
          ref={presentationRef}
          className="e2-presentation"
          onClick={(event) => {
            if (event.clientX < window.innerWidth / 2) {
              setActiveIdx(Math.max(0, activeIdx - 1));
            } else {
              setActiveIdx(Math.min(slides.length - 1, activeIdx + 1));
            }
          }}
        >
          <div
            className="e2-presentation-slide"
            style={{
              width: 960 * Math.min(presentationViewport.width / 960, presentationViewport.height / 540),
              height: 540 * Math.min(presentationViewport.width / 960, presentationViewport.height / 540),
            }}
          >
            <UnifiedSlideView
              slide={activeSlide}
              theme={templateId}
              index={activeIdx}
              scale={Math.min(presentationViewport.width / 960, presentationViewport.height / 540)}
            />
          </div>
          <div className="e2-presentation-controls" onClick={(event) => event.stopPropagation()}>
            <button onClick={() => setActiveIdx(Math.max(0, activeIdx - 1))} disabled={activeIdx === 0} title="Slide trước">
              <ChevronLeft size={20}/>
            </button>
            <span><Presentation size={16}/> {activeIdx + 1} / {slides.length}</span>
            <button onClick={() => setActiveIdx(Math.min(slides.length - 1, activeIdx + 1))} disabled={activeIdx === slides.length - 1} title="Slide sau">
              <ChevronRight size={20}/>
            </button>
          </div>
          <button className="e2-presentation-exit" onClick={(event) => { event.stopPropagation(); stopPresentation(); }} title="Thoát trình chiếu">
            <X size={20}/>
          </button>
        </div>
      )}
    </div>
  );
}

function InfoRow({ label, value }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0', borderBottom: '1px solid rgba(255,255,255,0.06)', fontSize: '0.85rem' }}>
      <span style={{ color: 'rgba(255,255,255,0.45)' }}>{label}</span>
      <strong style={{ color: 'white', textTransform: 'capitalize', textAlign: 'right', maxWidth: 140, overflow: 'hidden', textOverflow: 'ellipsis' }}>{value}</strong>
    </div>
  );
}

// Helper sinh mock slides nếu API chưa trả về slide
function getMockSlides(topic) {
  return [
    {
      id: 's1',
      type: 'title',
      title: topic,
      subtitle: 'Tài liệu thuyết trình được khởi tạo tự động bởi AI',
      imagePrompt: 'A beautiful slide layout',
      imageUrl: '',
      pageIndex: 0
    },
    {
      id: 's2',
      type: 'content',
      title: 'Giới thiệu tổng quan',
      bullets: [
        `Khái niệm cơ bản liên quan đến ${topic}`,
        'Các thành phần cốt lõi và nguyên lý hoạt động',
        'Tầm quan trọng trong bối cảnh hiện đại',
        'Mục tiêu và đối tượng hướng đến'
      ],
      imagePrompt: 'An analysis diagram',
      imageUrl: '',
      pageIndex: 1
    },
    {
      id: 's3',
      type: 'twoColumn',
      title: 'Phân tích Chi tiết',
      left: { heading: '✅ Cơ hội & Lợi ích', points: ['Tăng hiệu suất làm việc', 'Tự động hóa quy trình', 'Giảm thiểu sai sót con người'] },
      right: { heading: '⚠️ Thách thức & Rủi ro', points: ['Chi phí triển khai ban đầu cao', 'Yêu cầu bảo mật thông tin nghiêm ngặt', 'Sự phụ thuộc vào công nghệ'] },
      imagePrompt: 'A scale showing balance',
      imageUrl: '',
      pageIndex: 2
    },
    {
      id: 's4',
      type: 'quote',
      title: 'Góc nhìn Chuyên gia',
      quote: `"${topic} không chỉ là một công nghệ mới, nó là một cuộc cách mạng thay đổi cách chúng ta tư duy và làm việc hàng ngày."`,
      author: 'Dr. Alex Rivera',
      role: 'Giám đốc Nghiên cứu AI',
      imagePrompt: 'A professional portrait illustration',
      imageUrl: '',
      pageIndex: 3
    },
    {
      id: 's5',
      type: 'thankyou',
      title: 'Cảm ơn!',
      subtitle: 'Rất mong nhận được câu hỏi và đóng góp ý kiến.',
      contact: 'contact@genslideauto.com',
      imagePrompt: 'A simple thank you card',
      imageUrl: '',
      pageIndex: 4
    }
  ];
}
