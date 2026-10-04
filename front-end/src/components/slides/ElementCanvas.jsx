import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { AlignHorizontalJustifyCenter, ArrowDownToLine, ArrowUpToLine, ClipboardPaste, Copy, CopyPlus, Crop, GripHorizontal, ImagePlus, Loader2, Lock, Palette, Plus, Scan, Shapes, Trash2, Unlock, RotateCw, RotateCcw, ZoomIn, ZoomOut } from 'lucide-react';
import { GraphicInspector, ShapePicker } from './GraphicTools';
import { ArtGlyph, IconGlyph, ShapeGlyph } from './ElementGlyphs';
import { createIconElement, createShapeElement } from '../../utils/shapeLibrary';
import {
  alignPatches, applyPatches, boundsOf, cloneSelection, distributePatches, expandToGroups, groupElements, hasGroup,
  marqueeSelect, moveWithinSlide, newElementId, reorderLayers, selectable, snapBox, toggleInSelection, ungroupElements,
} from '../../utils/selection';
import SelectionTools from './SelectionTools';
import { getClipboard, setClipboard } from '../../utils/elementClipboard';
import { createElementsFromSlide, createTextElement } from '../../utils/slideElements';
import { normalizeBoundaryElements, normalizeTableElements } from '../../utils/templateLayouts';
import { resolveAssetUrl } from '../../utils/assetUrl';
import { isBackdrop, isDarkColor } from '../../utils/templateArt';
import { isGeneratedTheme, buildGeneratedTheme } from '../../utils/generatedTheme';
import EditableSlide, { THEMES } from './EditableSlide';
import { TiptapInlineEditor } from './TiptapEditor';
import { ChartVisual, TableVisual } from './StructuredVisual';
import { documentService } from '../../services/documentService';
import AssetImage from './AssetImage';
import { BgDecorations } from './SlideRenderer';
import { fitTextToBox } from '../../utils/textFit';
import { inferImageFit } from '../../utils/imageFit';
import { paintReveal } from '../../utils/reveal';
import './ElementCanvas.css';

const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
const SNAP_DISTANCE = 6;
const normalizeColor = (value) => String(value || '').replace(/\s+/g, '').toLowerCase();
const isFormEditingTarget = (target) => {
  const element = target instanceof Element ? target : document.activeElement;
  return Boolean(element?.closest?.('input, textarea, select, [contenteditable="true"], [role="textbox"]'));
};
const DEFAULT_THEME_TEXT_COLORS = new Set(
  Object.values(THEMES)
    .flatMap((item) => [item.text, item.textSub])
    .filter(Boolean)
    .map(normalizeColor),
);

const adaptiveCanvasFontSize = (element) => {
  const savedSize = Number(element?.style?.fontSize);
  const content = String(element?.content || '');
  // A size set by dragging a resize handle (see startPointerAction) is a
  // deliberate, Canva-style scale — it must stick exactly, not get
  // silently recalculated back to whatever size best "fits" the box.
  if (element?.style?.fontSizeLocked && savedSize) return savedSize;
  if (/font-size\s*:/i.test(content)) return savedSize || (element?.role === 'title' ? 34 : 16);

  const isTitle = element?.role === 'title';
  const itemCount = Math.max(
    1,
    (content.match(/<li\b/gi) || []).length
      || content.split(/<br\s*\/?>|\n/gi).filter(Boolean).length,
  );
  return fitTextToBox(content, {
    width: Number(element?.width) || (isTitle ? 832 : 430),
    height: Number(element?.height) || (isTitle ? 66 : 344),
    min: isTitle ? 20 : 10,
    max: isTitle ? 38 : 24,
    lineHeight: Number(element?.style?.lineHeight) || (isTitle ? 1.2 : 1.5),
    itemCount,
    padding: isTitle ? 0 : 10,
  });
};

// Background and pictures of an uploaded template's sample slide, drawn under the content.
// The uploaded template's own art. It is not part of the slide's elements, so clicking a
// piece hands it to the editor, which turns the decoration into real, editable shapes
// (see adoptArtAt in EditorPage) — no "edit the decorations" switch to find first.
// A backdrop, or a piece covering a good part of the slide (a panel, a tinted sheet), is the page
// itself: a click on it belongs to the canvas, so it clears the selection or starts a marquee
// instead of being swallowed here.
const isPageSizedArt = (item) => isBackdrop(item) || item.width * item.height >= 0.25 * 960 * 540;

function TemplateArt({ art, onPick }) {
  return (
    <div className={`element-canvas-art${onPick ? ' pickable' : ''}`} aria-hidden="true">
      {art.map((item) => (
        <div
          key={item.id}
          onPointerDown={onPick && !isPageSizedArt(item) ? (event) => { event.stopPropagation(); onPick(item); } : undefined}
          title={onPick && !isPageSizedArt(item) ? 'Bấm để tách trang trí thành hình có thể sửa' : undefined}
          style={{
            ...(isPageSizedArt(item) ? { pointerEvents: 'none' } : null),
            position: 'absolute',
            left: item.x,
            top: item.y,
            width: item.width,
            height: item.height,
            transform: item.rotation ? `rotate(${item.rotation}deg)` : undefined,
          }}
        >
          <ArtGlyph item={item} />
        </div>
      ))}
    </div>
  );
}

export default function ElementCanvas({
  slide,
  theme,
  scale = 1,
  onUpdate,
  onNotify,
  readonly = false,
  preserveTemplate = false,
  preserveTemplateStyles = false,
  revealStage = null,
  onAdoptArt,
  onCopyToAllSlides,
}) {
  const imageInputRef = useRef(null);
  const canvasRootRef = useRef(null);
  const themeData = useMemo(() => {
    const importedTheme = preserveTemplateStyles
      ? slide.elements?.find((element) => element.templateTheme)?.templateTheme
      : null;
    const baseThemeData = THEMES[theme] || THEMES['clean-white'];
    return importedTheme ? {
      ...baseThemeData,
      primary: importedTheme.primary || baseThemeData.primary,
      text: importedTheme.text || baseThemeData.text,
      textSub: importedTheme.textSub || baseThemeData.textSub,
      fontTitle: importedTheme.fontTitle || baseThemeData.fontTitle,
      fontBody: importedTheme.fontBody || baseThemeData.fontBody,
    } : baseThemeData;
  }, [slide.elements, theme, preserveTemplateStyles]);
  const fallbackElements = useMemo(() => createElementsFromSlide(slide, theme), [slide, theme]);
  const elements = useMemo(() => {
    const source = Array.isArray(slide.elements) && (slide.elements.length || preserveTemplate)
      ? slide.elements
      : fallbackElements;
    return normalizeBoundaryElements(normalizeTableElements(source), slide.type, theme).map((element) => {
      const style = element.style || {};
      const legacyTitle = element.role === 'title' && Number(style.fontSize) === 36 && element.x === 64 && element.y === 48;
      const legacyBody = element.role === 'body' && Number(style.fontSize) === 20 && element.y === 140;
      const isThemeDefaultColor = !preserveTemplateStyles
        && (!style.color || DEFAULT_THEME_TEXT_COLORS.has(normalizeColor(style.color)));
      const themedStyle = element.role === 'title'
        ? {
            ...style,
            fontFamily: style.fontFamily || themeData.fontTitle,
            color: isThemeDefaultColor ? themeData.text : style.color,
          }
        : element.role === 'body'
          ? {
              ...style,
              fontFamily: style.fontFamily || themeData.fontBody,
              color: isThemeDefaultColor ? themeData.textSub : style.color,
            }
          : element.role === 'pageNumber'
            ? { ...style, fontFamily: style.fontFamily || themeData.fontBody, color: style.color || themeData.textSub }
          : element.role === 'custom' && element.type === 'text'
            ? {
                ...style,
                fontFamily: style.fontFamily || themeData.fontBody,
                color: isThemeDefaultColor ? themeData.text : style.color,
              }
          : style;

      if (legacyTitle) {
        return {
          ...element, y: 44, height: 58,
          style: { ...themedStyle, fontFamily: themeData.fontTitle, fontSize: 34, lineHeight: 1.2 },
        };
      }
      if (legacyBody) {
        return {
          ...element, x: 64, y: 112, width: slide.imageUrl ? 430 : 832, height: 350,
          style: { ...themedStyle, fontFamily: themeData.fontBody, fontSize: 16.5, lineHeight: 1.55 },
        };
      }
      return themedStyle === style ? element : { ...element, style: themedStyle };
    });
  }, [fallbackElements, preserveTemplate, preserveTemplateStyles, slide.elements, slide.imageUrl, slide.type, theme, themeData]);
  // Presenting can "build" a slide's bullets in one at a time; painted on the real DOM
  // after Tiptap has rendered them (see utils/reveal.js for why it can't be baked into the
  // HTML each bullet is rendered from). Everywhere else revealStage is null, so this is a
  // no-op and every bullet just shows as normal.
  useEffect(() => {
    if (revealStage == null) return;
    paintReveal(canvasRootRef.current, revealStage);
  }, [revealStage, elements]);
  // The theme's fixed accent bar belongs next to a top-left title; once a layout
  // (or the user) moves the title elsewhere the bar hides instead of floating.
  const titleElement = elements.find((item) => item.type === 'text' && item.role === 'title');
  const titleAtTopLeft = !titleElement || (titleElement.x <= 96 && titleElement.y <= 70 && !titleElement.rotation);
  const [selectedId, setSelectedId] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [hasClipboard, setHasClipboard] = useState(Boolean(getClipboard()));
  const [guides, setGuides] = useState({ x: null, y: null });
  const [pickerOpen, setPickerOpen] = useState(false);
  const [formatOpen, setFormatOpen] = useState(false);
  const [alignOpen, setAlignOpen] = useState(false);
  const [multi, setMulti] = useState([]);
  const [marquee, setMarquee] = useState(null);
  const [uploadingImage, setUploadingImage] = useState(false);
  const [croppingId, setCroppingId] = useState(null);
  const [resizingId, setResizingId] = useState(null);
  const multiIds = multi.filter((mid) => elements.some((item) => item.id === mid));
  const isMulti = multiIds.length > 1;
  // With several elements selected there is no single "selected element": the per-element
  // controls (resize handles, image tools, format panel) step aside for the group tools.
  const selectedElement = isMulti ? null : (elements.find((item) => item.id === selectedId) || null);
  const selectionIds = isMulti ? multiIds : (selectedElement ? [selectedElement.id] : []);
  const selectionBounds = isMulti ? boundsOf(elements, multiIds) : null;

  // Two updates can land in the same tick (a text box saving its content on
  // blur while its auto-resize reports a new height). Each must build on the
  // result of the one before it, not on the render they both closed over —
  // otherwise the later one silently reverts the earlier one (lost formatting).
  const latest = useRef({ slide, elements });
  useLayoutEffect(() => {
    latest.current = { slide, elements };
  });
  // `meta.silent` marks an automatic layout correction (a box re-measuring its own height), as
  // opposed to something the user did: it must not become an undo step or wipe the redo list.
  const commit = (next, slidePatch = {}, meta) => {
    // Read-only views (thumbnails, presenter, audience) have no onUpdate; their text boxes
    // still report a blur/height change now and then, which must simply be ignored.
    if (!onUpdate) return;
    const updated = { ...latest.current.slide, ...slidePatch, elements: next };
    latest.current = { slide: updated, elements: next };
    onUpdate(updated, meta);
  };
  const syncElementLayout = (elementId, patch) => {
    commit(latest.current.elements.map((item) => item.id === elementId ? { ...item, ...patch } : item), {}, { silent: true });
  };
  const updateElement = (elementId, patch) => {
    commit(latest.current.elements.map((item) => item.id === elementId ? { ...item, ...patch } : item));
  };

  const updateStructuredElement = (elementId, type, data) => {
    commit(
      latest.current.elements.map((item) => item.id === elementId ? { ...item, data } : item),
      { [type]: data },
    );
  };

  const addText = () => {
    const element = createTextElement();
    commit([...latest.current.elements, element]);
    setSelectedId(element.id);
  };

  const accentColor = themeData.accent || themeData.primary || '#6c63ff';

  const addShape = (shape) => {
    const element = createShapeElement(shape, { accent: accentColor });
    commit([...latest.current.elements, element]);
    setSelectedId(element.id);
    setPickerOpen(false);
  };

  const addIcon = (icon) => {
    const element = createIconElement(icon, { accent: accentColor });
    commit([...latest.current.elements, element]);
    setSelectedId(element.id);
    setPickerOpen(false);
  };

  const cloneElementList = (list) => list.map((item) => ({ ...item, style: item.style ? { ...item.style } : undefined }));

  // One place decides what is selected: several ids, one id, or nothing.
  const selectMany = (ids, primary) => {
    if (ids.length > 1) {
      setMulti(ids);
      setSelectedId(primary ?? ids[ids.length - 1]);
    } else {
      setMulti([]);
      setSelectedId(ids[0] ?? null);
    }
    setEditingId(null);
    setCroppingId(null);
  };

  const removeSelected = () => {
    const doomed = selectionIds.filter((sid) => selectable(latest.current.elements.find((item) => item.id === sid)));
    if (!doomed.length) return;
    commit(latest.current.elements.filter((item) => !doomed.includes(item.id)));
    selectMany([]);
  };

  const copySelected = () => {
    const picked = latest.current.elements.filter((item) => selectionIds.includes(item.id));
    if (!picked.length) return;
    setClipboard(cloneElementList(picked));
    setHasClipboard(true);
  };

  const pasteElement = () => {
    const buffer = getClipboard();
    if (!buffer?.length) return;
    const copies = cloneSelection(buffer, buffer.map((item) => item.id));
    commit([...latest.current.elements, ...copies]);
    selectMany(copies.map((item) => item.id));
    setClipboard(cloneElementList(copies));
    setHasClipboard(true);
  };

  const duplicateSelected = () => {
    if (!selectionIds.length) return;
    const copies = cloneSelection(latest.current.elements, selectionIds);
    commit([...latest.current.elements, ...copies]);
    selectMany(copies.map((item) => item.id));
  };

  const moveLayer = (direction) => {
    if (!selectionIds.length) return;
    commit(reorderLayers(latest.current.elements, selectionIds, direction));
  };

  const toggleLock = () => {
    if (!selectionIds.length) return;
    const picked = latest.current.elements.filter((item) => selectionIds.includes(item.id));
    const lock = !picked.every((item) => item.locked);
    commit(latest.current.elements.map((item) => (selectionIds.includes(item.id) ? { ...item, locked: lock } : item)));
    setEditingId(null);
    setCroppingId(null);
  };

  const alignSelection = (mode) => {
    const patches = alignPatches(latest.current.elements, selectionIds, mode);
    if (Object.keys(patches).length) commit(applyPatches(latest.current.elements, patches));
  };

  const distributeSelection = (axis) => {
    const patches = distributePatches(latest.current.elements, selectionIds, axis);
    if (Object.keys(patches).length) commit(applyPatches(latest.current.elements, patches));
  };

  const groupSelection = () => {
    const next = groupElements(latest.current.elements, selectionIds);
    if (next === latest.current.elements) return;
    commit(next);
    selectMany(expandToGroups(next, selectionIds));
  };

  const ungroupSelection = () => {
    commit(ungroupElements(latest.current.elements, selectionIds));
  };

  // Dragging one member of a multi-selection or of a group moves all of them together.
  const startGroupMove = (event, ids, anchor, deferUntilMove) => {
    // Always cancel the default press: otherwise the browser starts a native drag and the pointer stream stops.
    event.preventDefault();
    event.stopPropagation();
    const items = latest.current.elements.filter((item) => ids.includes(item.id) && selectable(item));
    if (!items.length) return;
    const starts = Object.fromEntries(items.map((item) => [item.id, { x: item.x, y: item.y }]));
    const bounds = boundsOf(items, items.map((item) => item.id));
    const others = latest.current.elements.filter((item) => !starts[item.id]);
    const origin = { x: event.clientX, y: event.clientY };
    let moving = !deferUntilMove;
    let moved = false;
    const move = (pointerEvent) => {
      const dx = (pointerEvent.clientX - origin.x) / scale;
      const dy = (pointerEvent.clientY - origin.y) / scale;
      if (!moving && Math.hypot(dx, dy) < 3) return;
      moving = true;
      moved = true;
      pointerEvent.preventDefault();
      const first = moveWithinSlide(starts, bounds, dx, dy);
      const snap = snapBox({ x: bounds.x + first.dx, y: bounds.y + first.dy, width: bounds.width, height: bounds.height }, others, SNAP_DISTANCE);
      const final = moveWithinSlide(starts, bounds, first.dx + snap.fixX, first.dy + snap.fixY);
      setGuides({ x: snap.guideX, y: snap.guideY });
      commit(applyPatches(latest.current.elements, final.patches));
    };
    const up = () => {
      setGuides({ x: null, y: null });
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
      // A plain click on one member of a loose selection narrows it to that element.
      if (!moved && !anchor.groupId) selectMany([anchor.id]);
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up, { once: true });
  };

  // Dragging on empty canvas draws a selection rectangle.
  const startMarquee = (event) => {
    setPickerOpen(false);
    setFormatOpen(false);
    setAlignOpen(false);
    if (event.button !== undefined && event.button !== 0) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const toSlide = (clientX, clientY) => ({ x: (clientX - rect.left) / scale, y: (clientY - rect.top) / scale });
    const origin = toSlide(event.clientX, event.clientY);
    const base = event.shiftKey ? selectionIds : [];
    if (!event.shiftKey) selectMany([]);
    let dragging = false;
    const move = (pointerEvent) => {
      const point = toSlide(pointerEvent.clientX, pointerEvent.clientY);
      if (!dragging && Math.hypot(point.x - origin.x, point.y - origin.y) < 4) return;
      dragging = true;
      pointerEvent.preventDefault();
      const area = { x0: origin.x, y0: origin.y, x1: point.x, y1: point.y };
      setMarquee(area);
      selectMany(expandToGroups(latest.current.elements, [...base, ...marqueeSelect(latest.current.elements, area)]));
    };
    const up = () => {
      setMarquee(null);
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up, { once: true });
  };

  const startImageCrop = (event, element) => {
    event.preventDefault();
    event.stopPropagation();
    const start = {
      x: event.clientX,
      y: event.clientY,
      positionX: Number(element.objectPositionX ?? 50),
      positionY: Number(element.objectPositionY ?? 50),
    };
    const move = (pointerEvent) => {
      const dx = (pointerEvent.clientX - start.x) / (element.width * scale) * 100;
      const dy = (pointerEvent.clientY - start.y) / (element.height * scale) * 100;
      updateElement(element.id, {
        objectFit: 'cover',
        fitExplicit: true,
        objectPositionX: clamp(start.positionX - dx, 0, 100),
        objectPositionY: clamp(start.positionY - dy, 0, 100),
      });
    };
    const up = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up, { once: true });
  };

  const handleImageLoaded = (event, element) => {
    const image = event.currentTarget;
    const naturalWidth = Number(image.naturalWidth || 0);
    const naturalHeight = Number(image.naturalHeight || 0);
    if (!naturalWidth || !naturalHeight) return;
    const ratio = naturalWidth / naturalHeight;
    const shouldContain = ratio >= 1.8 || ratio <= 0.62;
    const currentFit = element.objectFit || 'cover';
    const nextFit = element.fitExplicit
      ? currentFit
      : (shouldContain ? 'contain' : inferImageFit(element.src));
    const currentScale = Number(element.imageScale || 1);
    const normalizedScale = nextFit === 'contain' ? Math.max(1, currentScale) : currentScale;
    if (currentFit === nextFit && currentScale === normalizedScale) return;
    updateElement(element.id, {
      objectFit: nextFit,
      imageScale: currentFit === nextFit ? normalizedScale : 1,
      objectPositionX: currentFit === nextFit ? Number(element.objectPositionX ?? 50) : 50,
      objectPositionY: currentFit === nextFit ? Number(element.objectPositionY ?? 50) : 50,
    });
  };

  const uploadImageFile = async (file) => {
    if (!file) return;
    if (!file.type.startsWith('image/')) {
      onNotify?.('Vui lòng chọn tệp ảnh PNG, JPEG, WebP hoặc GIF', 'warning');
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      onNotify?.('Ảnh không được vượt quá 10 MB', 'warning');
      return;
    }

    setUploadingImage(true);
    try {
      const uploaded = await documentService.upload(file);
      const src = uploaded?.viewUrl || uploaded?.url;
      if (!src) throw new Error('Máy chủ không trả về URL ảnh');
      if (selectedElement?.type === 'image' && !selectedElement.locked) {
        updateElement(selectedElement.id, {
          src, storageUrl: uploaded.url, assetId: uploaded.id,
          imageScale: 1, objectPositionX: 50, objectPositionY: 50,
        });
      } else {
        const image = {
          id: newElementId(),
          type: 'image',
          role: 'image',
          x: 280,
          y: 120,
          width: 400,
          height: 300,
          rotation: 0,
          objectFit: 'cover',
          imageScale: 1,
          src,
          storageUrl: uploaded.url,
          assetId: uploaded.id,
        };
        commit([...elements, image]);
        setSelectedId(image.id);
      }
    } catch (error) {
      onNotify?.(error.message || 'Không thể tải ảnh lên', 'error');
    } finally {
      setUploadingImage(false);
    }
  };
  const handleImageUpload = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    await uploadImageFile(file);
  };

  useEffect(() => {
    if (readonly) return undefined;
    const onPaste = (event) => {
      if (event.defaultPrevented || isFormEditingTarget(event.target)) return;
      const imageItem = [...(event.clipboardData?.items || [])].find((item) => item.type.startsWith('image/'));
      if (imageItem) {
        const file = imageItem.getAsFile();
        if (!file) return;
        event.preventDefault();
        uploadImageFile(file);
        return;
      }
      const text = event.clipboardData?.getData('text/plain') || '';
      if (!text.trim()) return;
      event.preventDefault();
      const element = createTextElement();
      const escaped = text
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replace(/\r?\n/g, '<br>');
      element.content = escaped;
      commit([...elements, element]);
      setSelectedId(element.id);
    };
    window.addEventListener('paste', onPaste);
    return () => window.removeEventListener('paste', onPaste);
  }, [readonly, elements, selectedElement]);

  useEffect(() => {
    if (readonly) return undefined;
    const onKeyDown = (event) => {
      if (isFormEditingTarget(event.target)) return;
      const command = event.ctrlKey || event.metaKey;
      const key = event.key.toLowerCase();

      const arrows = ['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'];
      if (command && key === 'a') {
        event.preventDefault();
        selectMany(latest.current.elements.filter(selectable).map((item) => item.id));
      } else if (command && key === 'g' && selectionIds.length > 1) {
        event.preventDefault();
        if (event.shiftKey) ungroupSelection(); else groupSelection();
      } else if (event.key === 'Escape' && selectionIds.length) {
        selectMany([]);
      } else if (isMulti && arrows.includes(event.key)) {
        event.preventDefault();
        const step = event.shiftKey ? 10 : 1;
        const items = latest.current.elements.filter((item) => multiIds.includes(item.id) && selectable(item));
        const bounds = boundsOf(items, items.map((item) => item.id));
        const starts = Object.fromEntries(items.map((item) => [item.id, { x: item.x, y: item.y }]));
        const dx = event.key === 'ArrowLeft' ? -step : event.key === 'ArrowRight' ? step : 0;
        const dy = event.key === 'ArrowUp' ? -step : event.key === 'ArrowDown' ? step : 0;
        if (bounds) commit(applyPatches(latest.current.elements, moveWithinSlide(starts, bounds, dx, dy).patches));
      } else if (command && key === 'd' && selectedId) {
        event.preventDefault();
        event.stopPropagation();
        duplicateSelected();
      } else if (command && key === 'c' && selectedId) {
        event.preventDefault();
        copySelected();
      } else if (command && key === 'v' && getClipboard()) {
        event.preventDefault();
        pasteElement();
      } else if ((event.key === 'Delete' || event.key === 'Backspace') && selectedId) {
        if (selectedElement?.locked) return;
        event.preventDefault();
        removeSelected();
      } else if (event.key === 'Enter' && selectedId) {
        const selected = elements.find((item) => item.id === selectedId);
        if (selected?.type === 'text' && !selected.locked) {
          event.preventDefault();
          setEditingId(selectedId);
        }
      } else if (selectedId && ['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) {
        if (selectedElement?.locked) return;
        event.preventDefault();
        const selected = elements.find((item) => item.id === selectedId);
        if (!selected) return;
        const step = event.shiftKey ? 10 : 1;
        const dx = event.key === 'ArrowLeft' ? -step : event.key === 'ArrowRight' ? step : 0;
        const dy = event.key === 'ArrowUp' ? -step : event.key === 'ArrowDown' ? step : 0;
        updateElement(selectedId, {
          x: clamp(selected.x + dx, 0, 960 - selected.width),
          y: clamp(selected.y + dy, 0, 540 - selected.height),
        });
      }
    };

    window.addEventListener('keydown', onKeyDown, true);
    return () => window.removeEventListener('keydown', onKeyDown, true);
  }, [readonly, selectedId, selectedElement, elements, multi]);

  const startPointerAction = (event, element, mode, deferUntilMove = false) => {
    if (element.locked) {
      event.stopPropagation();
      setSelectedId(element.id);
      return;
    }
    if (mode === 'move') {
      if (event.shiftKey) {
        event.stopPropagation();
        selectMany(toggleInSelection(latest.current.elements, selectionIds, element.id), element.id);
        return;
      }
      const family = expandToGroups(latest.current.elements, [element.id]);
      const inSelection = isMulti && multiIds.includes(element.id);
      const members = inSelection ? multiIds : family;
      if (members.length > 1) {
        if (!inSelection) selectMany(members, element.id);
        startGroupMove(event, members, element, deferUntilMove);
        return;
      }
      if (isMulti) setMulti([]);
    }
    if (!deferUntilMove) event.preventDefault();
    event.stopPropagation();
    setSelectedId(element.id);
    const start = { x: event.clientX, y: event.clientY, element };
    let moving = !deferUntilMove;

    const move = (pointerEvent) => {
      const dx = (pointerEvent.clientX - start.x) / scale;
      const dy = (pointerEvent.clientY - start.y) / scale;
      if (!moving && Math.hypot(dx, dy) < 3) return;
      moving = true;
      pointerEvent.preventDefault();
      if (mode === 'move') {
        let nextX = clamp(start.element.x + dx, 0, 960 - element.width);
        let nextY = clamp(start.element.y + dy, 0, 540 - element.height);
        // Snap to the canvas edges/center and to every other element's own
        // edges/center, so dragging one box lines it up with another one
        // already on the slide — not just with the slide bounds.
        const others = elements.filter((item) => item.id !== element.id);
        const verticalTargets = [0, 480, 960, ...others.flatMap((item) => [
          item.x, item.x + (item.width || 0) / 2, item.x + (item.width || 0),
        ])];
        const horizontalTargets = [0, 270, 540, ...others.flatMap((item) => [
          item.y, item.y + (item.height || 0) / 2, item.y + (item.height || 0),
        ])];
        const elementXPoints = [nextX, nextX + element.width / 2, nextX + element.width];
        const elementYPoints = [nextY, nextY + element.height / 2, nextY + element.height];
        let guideX = null;
        let guideY = null;

        verticalTargets.some((target) => elementXPoints.some((point, pointIndex) => {
          if (Math.abs(point - target) > SNAP_DISTANCE) return false;
          nextX = target - [0, element.width / 2, element.width][pointIndex];
          guideX = target;
          return true;
        }));
        horizontalTargets.some((target) => elementYPoints.some((point, pointIndex) => {
          if (Math.abs(point - target) > SNAP_DISTANCE) return false;
          nextY = target - [0, element.height / 2, element.height][pointIndex];
          guideY = target;
          return true;
        }));
        setGuides({ x: guideX, y: guideY });
        updateElement(element.id, {
          x: clamp(nextX, 0, 960 - element.width),
          y: clamp(nextY, 0, 540 - element.height),
        });
      } else if (mode.startsWith('resize-')) {
        const direction = mode.slice(7);
        const minWidth = 40;
        const minHeight = 30;
        let nextX = start.element.x;
        let nextY = start.element.y;
        let nextWidth = start.element.width;
        let nextHeight = start.element.height;

        if (direction.includes('e')) nextWidth = clamp(start.element.width + dx, minWidth, 960 - start.element.x);
        if (direction.includes('s')) nextHeight = clamp(start.element.height + dy, minHeight, 540 - start.element.y);
        if (direction.includes('w')) {
          nextX = clamp(start.element.x + dx, 0, start.element.x + start.element.width - minWidth);
          nextWidth = start.element.width + start.element.x - nextX;
        }
        if (direction.includes('n')) {
          nextY = clamp(start.element.y + dy, 0, start.element.y + start.element.height - minHeight);
          nextHeight = start.element.height + start.element.y - nextY;
        }

        const patch = { x: nextX, y: nextY, width: nextWidth, height: nextHeight };
        if (element.type === 'text') {
          // Dragging a handle on a text box scales the font with it, like
          // resizing an image — a corner scales by the box's own area
          // change (both dimensions), an edge handle by that one dimension.
          const widthRatio = nextWidth / (start.element.width || nextWidth);
          const heightRatio = nextHeight / (start.element.height || nextHeight);
          const isCorner = direction.length === 2;
          const scaleRatio = isCorner ? Math.sqrt(widthRatio * heightRatio)
            : direction.includes('e') || direction.includes('w') ? widthRatio
            : heightRatio;
          const startFontSize = start.element.style?.fontSizeLocked && Number(start.element.style?.fontSize)
            ? Number(start.element.style.fontSize)
            : adaptiveCanvasFontSize(start.element);
          const nextFontSize = Math.round(Math.min(200, Math.max(6, startFontSize * scaleRatio)) * 10) / 10;
          patch.style = { ...element.style, fontSize: nextFontSize, fontSizeLocked: true };
        }
        updateElement(element.id, patch);
      }
    };

    if (mode.startsWith('resize-')) setResizingId(element.id);

    const up = () => {
      setGuides({ x: null, y: null });
      setResizingId(null);
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up, { once: true });
  };

  const startRotate = (event, element) => {
    if (element.locked) return;
    event.preventDefault();
    event.stopPropagation();
    const canvasRect = event.currentTarget.closest('.element-canvas').getBoundingClientRect();
    const centerX = canvasRect.left + (element.x + element.width / 2) * scale;
    const centerY = canvasRect.top + (element.y + element.height / 2) * scale;
    const startAngle = Math.atan2(event.clientY - centerY, event.clientX - centerX) * 180 / Math.PI;
    const initialRotation = element.rotation || 0;

    const move = (pointerEvent) => {
      const angle = Math.atan2(pointerEvent.clientY - centerY, pointerEvent.clientX - centerX) * 180 / Math.PI;
      let rotation = initialRotation + angle - startAngle;
      if (pointerEvent.shiftKey) rotation = Math.round(rotation / 15) * 15;
      updateElement(element.id, { rotation: Math.round(rotation * 10) / 10 });
    };
    const up = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up, { once: true });
  };

  return (
    <div ref={canvasRootRef} className={`element-canvas ${readonly ? 'readonly' : ''} ${preserveTemplate ? 'preserve-template' : ''} ${THEMES[theme] ? '' : 'custom-theme'}`} data-theme={theme} data-slide-type={slide?.type || ''} data-title-tl={titleAtTopLeft ? 'true' : 'false'} style={{ background: preserveTemplate ? 'transparent' : themeData.bgGrad, '--slide-accent': themeData.accent, ...(isGeneratedTheme(theme) ? buildGeneratedTheme(theme).cssVars : null), ...(slide?.richText?._tplBg && isDarkColor(slide.richText._tplBg) ? { '--card-bg': 'rgba(255, 255, 255, 0.08)', '--card-border': 'rgba(255, 255, 255, 0.2)' } : null) }} onPointerDown={readonly ? undefined : startMarquee}>
      {preserveTemplate ? (
        <div className="element-canvas-template">
          <EditableSlide slide={{ ...slide, elements: [] }} theme={theme} readonly />
        </div>
      ) : THEMES[theme] && !slide?.richText?._noOrnaments ? (
        // Custom (uploaded) templates have no built-in ornaments; the fallback
        // decoration would stamp a stray indigo bar on every one of them.
        <BgDecorations theme={theme} />
      ) : null}
      {Array.isArray(slide?.richText?._decor) && slide.richText._decor.length > 0 && (
        <TemplateArt
          art={slide.richText._noOrnaments ? slide.richText._decor.filter(isBackdrop) : slide.richText._decor}
          onPick={readonly || !onAdoptArt ? undefined : onAdoptArt}
        />
      )}
      {!readonly && <div className={`element-canvas-actions${pickerOpen || formatOpen || alignOpen ? ' open' : ''}`} onPointerDown={(event) => event.stopPropagation()}>
        <input ref={imageInputRef} type="file" accept="image/png,image/jpeg,image/webp,image/gif" hidden onChange={handleImageUpload}/>
        <button type="button" onClick={addText} title="Thêm ô chữ"><Plus size={15}/> Chữ</button>
        <span className="ea-anchor">
          <button
            type="button"
            className={pickerOpen ? 'active' : ''}
            onClick={() => { setPickerOpen((open) => !open); setFormatOpen(false); }}
            title="Thêm hình khối hoặc biểu tượng"
            aria-expanded={pickerOpen}
          >
            <Shapes size={15}/> Hình
          </button>
          {pickerOpen && <ShapePicker color={accentColor} onAddShape={addShape} onAddIcon={addIcon} />}
        </span>
        {(selectedElement?.type === 'shape' || selectedElement?.type === 'icon') && (
          <span className="ea-anchor">
            <button
              type="button"
              className={formatOpen ? 'active' : ''}
              onClick={() => { setFormatOpen((open) => !open); setPickerOpen(false); }}
              disabled={selectedElement?.locked}
              title="Định dạng hình: màu, viền, độ mờ"
              aria-expanded={formatOpen}
            >
              <Palette size={15}/>
            </button>
            {formatOpen && <GraphicInspector element={selectedElement} onChange={(patch) => updateElement(selectedElement.id, patch)} />}
          </span>
        )}
        <button type="button" onClick={() => imageInputRef.current?.click()} disabled={uploadingImage || selectedElement?.locked} title={selectedElement?.type === 'image' ? 'Thay ảnh' : 'Thêm ảnh'}>
          {uploadingImage ? <Loader2 size={15} className="spin"/> : <ImagePlus size={15}/>} {selectedElement?.type === 'image' ? 'Thay' : 'Ảnh'}
        </button>
        <button
          type="button"
          onClick={() => updateElement(selectedElement.id, {
            objectFit: selectedElement.objectFit === 'contain' ? 'cover' : 'contain',
            fitExplicit: true,
          })}
          disabled={selectedElement?.type !== 'image' || selectedElement?.locked}
          title="Chuyển giữa vừa khung và phủ khung"
        >
          <Scan size={15}/>
        </button>
        <button
          type="button"
          onClick={() => setCroppingId((current) => current === selectedElement?.id ? null : selectedElement?.id)}
          disabled={selectedElement?.type !== 'image' || selectedElement?.locked}
          className={croppingId === selectedElement?.id ? 'active' : ''}
          title={croppingId === selectedElement?.id ? 'Hoàn tất crop' : 'Crop ảnh'}
        >
          <Crop size={15}/>
        </button>
        <button
          type="button"
          onClick={() => updateElement(selectedElement.id, {
            imageScale: clamp(
              Number(selectedElement.imageScale || 1) - 0.1,
              selectedElement.objectFit === 'contain' ? 1 : 0.5,
              4,
            ),
          })}
          disabled={selectedElement?.type !== 'image' || selectedElement?.locked}
          title="Thu nhỏ ảnh bên trong khung"
        >
          <ZoomOut size={15}/>
        </button>
        <button
          type="button"
          onClick={() => updateElement(selectedElement.id, {
            imageScale: clamp(Number(selectedElement.imageScale || 1) + 0.1, 0.5, 4),
          })}
          disabled={selectedElement?.type !== 'image' || selectedElement?.locked}
          title="Phóng to ảnh bên trong khung"
        >
          <ZoomIn size={15}/>
        </button>
        <button
          type="button"
          onClick={() => updateElement(selectedElement.id, {
            imageScale: 1,
            objectPositionX: 50,
            objectPositionY: 50,
          })}
          disabled={selectedElement?.type !== 'image' || selectedElement?.locked}
          title="Đặt lại vị trí và độ phóng ảnh"
        >
          <RotateCcw size={15}/>
        </button>
        <button type="button" onClick={copySelected} disabled={!selectedId} title="Sao chép (Ctrl+C)"><Copy size={15}/></button>
        <button type="button" onClick={pasteElement} disabled={!hasClipboard} title="Dán (Ctrl+V)"><ClipboardPaste size={15}/></button>
        <button type="button" onClick={duplicateSelected} disabled={!selectedId} title="Nhân bản (Ctrl+D)"><Copy size={15}/><Plus size={10}/></button>
        {onCopyToAllSlides && (
          <button
            type="button"
            onClick={() => selectedElement && onCopyToAllSlides(selectedElement)}
            disabled={!selectedElement}
            title="Đặt phần tử này lên mọi slide (logo, chân trang, watermark…)"
          >
            <CopyPlus size={15}/>
          </button>
        )}
        <button type="button" onClick={() => moveLayer('back')} disabled={!selectedId} title="Đưa xuống dưới"><ArrowDownToLine size={15}/></button>
        <button type="button" onClick={() => moveLayer('front')} disabled={!selectedId} title="Đưa lên trên"><ArrowUpToLine size={15}/></button>
        <span className="ea-anchor">
          <button
            type="button"
            className={alignOpen ? 'active' : ''}
            onClick={() => { setAlignOpen((open) => !open); setPickerOpen(false); setFormatOpen(false); }}
            disabled={!selectionIds.length}
            title="Căn chỉnh, phân bố và gộp nhóm"
            aria-expanded={alignOpen}
          >
            <AlignHorizontalJustifyCenter size={15}/>
          </button>
          {alignOpen && (
            <SelectionTools
              count={selectionIds.length}
              canGroup={selectionIds.length > 1}
              canUngroup={hasGroup(elements, selectionIds)}
              onAlign={alignSelection}
              onDistribute={distributeSelection}
              onGroup={groupSelection}
              onUngroup={ungroupSelection}
            />
          )}
        </span>
        <button type="button" onClick={toggleLock} disabled={!selectedId} title={selectedElement?.locked ? 'Mở khóa phần tử' : 'Khóa phần tử'}>
          {selectedElement?.locked ? <Unlock size={15}/> : <Lock size={15}/>}
        </button>
        <button type="button" onClick={removeSelected} disabled={!selectedId || selectedElement?.locked} title="Xóa (Delete)"><Trash2 size={15}/></button>
      </div>}

      {isMulti && selectionBounds && (
        <div
          className="canvas-multi-frame"
          style={{ left: selectionBounds.x - 4, top: selectionBounds.y - 4, width: selectionBounds.width + 8, height: selectionBounds.height + 8 }}
        >
          <span>{multiIds.length} phần tử{hasGroup(elements, multiIds) ? ' · nhóm' : ''}</span>
        </div>
      )}
      {marquee && (
        <div
          className="canvas-marquee"
          style={{ left: Math.min(marquee.x0, marquee.x1), top: Math.min(marquee.y0, marquee.y1), width: Math.abs(marquee.x1 - marquee.x0), height: Math.abs(marquee.y1 - marquee.y0) }}
        />
      )}
      {guides.x !== null && <div className="canvas-guide vertical" style={{ left: guides.x }}/>} 
      {guides.y !== null && <div className="canvas-guide horizontal" style={{ top: guides.y }}/>} 

      {elements.map((element, index) => (
        <div
          key={element.id}
          className={`canvas-element role-${element.role || 'custom'} ${element.type === 'image' && (element.objectFit || inferImageFit(element.src)) === 'contain' ? 'fit-contain' : ''} ${!isMulti && selectedId === element.id ? 'selected' : ''} ${isMulti && multiIds.includes(element.id) ? 'multi-selected' : ''} ${editingId === element.id ? 'editing' : ''} ${element.locked ? 'locked' : ''} ${croppingId === element.id ? 'cropping' : ''}`}
          style={{
            left: element.x,
            top: element.y,
            width: element.width,
            height: element.height,
            zIndex: index + 1,
            transform: `rotate(${element.rotation || 0}deg)`,
          }}
          onPointerDown={readonly ? undefined : (event) => {
            if (editingId === element.id || croppingId === element.id) {
              event.stopPropagation();
              return;
            }
            startPointerAction(event, element, 'move', true);
          }}
          onDoubleClick={readonly ? undefined : (event) => {
            if (element.locked) return;
            event.stopPropagation();
            setSelectedId(element.id);
            if (element.type === 'image') {
              setEditingId(null);
              setCroppingId(element.id);
            } else if (element.type === 'text') {
              // contentEditable only turns on once this sets editingId (see
              // the `editable` prop below) — while merely *selected*, the
              // box stays a plain div so a press-and-drag anywhere on it
              // moves the box instead of the browser starting a native
              // text-selection drag.
              setEditingId(element.id);
            }
          }}
        >
          {!isMulti && selectedId === element.id && !element.locked && croppingId !== element.id && (
            <button
              type="button"
              className="canvas-drag-handle"
              onPointerDown={(event) => startPointerAction(event, element, 'move')}
              title="Kéo để di chuyển"
            >
              <GripHorizontal size={15}/>
            </button>
          )}
          {!isMulti && selectedId === element.id && !element.locked && croppingId !== element.id && (
            <button
              type="button"
              className="canvas-rotate-handle"
              onPointerDown={(event) => startRotate(event, element)}
              title="Kéo để xoay; giữ Shift để bắt góc 15°"
            >
              <RotateCw size={13}/>
            </button>
          )}
          {element.type === 'image' ? (
            element.src || element.storageUrl || element.assetId ? (
            <div className="canvas-image-viewport">
              <AssetImage
                src={resolveAssetUrl(element.src)}
                storageUrl={element.storageUrl}
                assetId={element.assetId}
                alt=""
                draggable={false}
                onLoad={(event) => handleImageLoaded(event, element)}
                onPointerDown={croppingId === element.id ? (event) => startImageCrop(event, element) : undefined}
                style={{
                  objectFit: element.objectFit || inferImageFit(element.src),
                  objectPosition: `${element.objectPositionX ?? 50}% ${element.objectPositionY ?? 50}%`,
                  transform: `scale(${element.imageScale || 1})`,
                  transformOrigin: 'center',
                }}
              />
            </div>
            ) : (
              <div className="canvas-image-placeholder" title="Khung ảnh">
                <ImagePlus size={32}/>
              </div>
            )
          ) : element.type === 'shape' ? (
            <ShapeGlyph element={element} />
          ) : element.type === 'icon' ? (
            <IconGlyph element={element} />
          ) : element.type === 'art' ? (
            <ArtGlyph item={{ type: element.artType, src: element.src, fill: element.fill, style: element.style, opacity: element.opacity }} />
          ) : element.type === 'table' ? (
            <TableVisual
              table={element.data || slide.table}
              theme={themeData}
              onInteract={readonly ? undefined : () => {
                setSelectedId(element.id);
                setEditingId(null);
              }}
              onChange={readonly ? undefined : (data) => updateStructuredElement(element.id, 'table', data)}
            />
          ) : element.type === 'chart' ? (
            <ChartVisual
              chart={element.data || slide.chart}
              theme={themeData}
              onChange={readonly ? undefined : (data) => updateStructuredElement(element.id, 'chart', data)}
            />
          ) : (
            <TiptapInlineEditor
              style={{
                ...element.style,
                display: 'flex',
                flexDirection: 'column',
                justifyContent: {
                  top: 'flex-start',
                  middle: 'center',
                  bottom: 'flex-end',
                }[element.style?.verticalAlign] || 'flex-start',
              }}
              className={`canvas-text${element.decor ? ` decor-${element.decor}` : ''}`}
              value={element.content}
              autoFit={false}
              autoResizeHeight={!readonly && resizingId !== element.id}
              minHeight={element.role === 'title' ? 40 : element.role === 'pageNumber' ? 20 : 60}
              onHeightChange={readonly ? undefined : (height) => syncElementLayout(element.id, { height })}
              autoFitBaseFontSize={adaptiveCanvasFontSize(element)}
              minFontSize={element.role === 'title' ? 12 : 8}
              selected={!readonly && !isMulti && selectedId === element.id && !element.locked}
              editable={!readonly && editingId === element.id && !element.locked}
              boxStyle={element.style}
              onBoxStyleChange={(patch) => updateElement(element.id, { style: { ...element.style, ...patch } })}
              onEnterEdit={() => setEditingId(element.id)}
              onExitEdit={() => setEditingId((current) => current === element.id ? null : current)}
              onSave={(html) => updateElement(element.id, { content: html })}
            />
          )}
          {!isMulti && selectedId === element.id && !element.locked && croppingId !== element.id && (
            <>
              {['nw', 'n', 'ne', 'e', 'se', 's', 'sw', 'w'].map((direction) => (
                <button
                  key={direction}
                  type="button"
                  className={`canvas-resize-handle resize-${direction}`}
                  onPointerDown={(event) => startPointerAction(event, element, `resize-${direction}`)}
                  title="Kéo để đổi kích thước"
                  aria-label={`Đổi kích thước ${direction}`}
                />
              ))}
            </>
          )}
        </div>
      ))}
    </div>
  );
}
