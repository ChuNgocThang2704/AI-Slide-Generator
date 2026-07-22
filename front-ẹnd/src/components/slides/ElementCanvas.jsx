import { useEffect, useMemo, useRef, useState } from 'react';
import { ArrowDownToLine, ArrowUpToLine, ClipboardPaste, Copy, Crop, GripHorizontal, ImagePlus, Loader2, Lock, Plus, Scan, Trash2, Unlock, RotateCw } from 'lucide-react';
import { createElementsFromSlide, createTextElement } from '../../utils/slideElements';
import { resolveAssetUrl } from '../../utils/assetUrl';
import { THEMES } from './EditableSlide';
import { TiptapInlineEditor } from './TiptapEditor';
import { documentService } from '../../services/documentService';
import AssetImage from './AssetImage';
import './ElementCanvas.css';

const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
const SNAP_DISTANCE = 6;
let elementClipboard = null;

const cloneElement = (element) => ({
  ...element,
  id: `el-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
  x: clamp((element.x || 0) + 20, 0, 920),
  y: clamp((element.y || 0) + 20, 0, 510),
  style: element.style ? { ...element.style } : undefined,
});

export default function ElementCanvas({ slide, theme, scale = 1, onUpdate, onNotify }) {
  const imageInputRef = useRef(null);
  const fallbackElements = useMemo(() => createElementsFromSlide(slide), [slide]);
  const elements = Array.isArray(slide.elements) && slide.elements.length
    ? slide.elements
    : fallbackElements;
  const [selectedId, setSelectedId] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [hasClipboard, setHasClipboard] = useState(Boolean(elementClipboard));
  const [guides, setGuides] = useState({ x: null, y: null });
  const [uploadingImage, setUploadingImage] = useState(false);
  const [croppingId, setCroppingId] = useState(null);
  const themeData = THEMES[theme] || THEMES['clean-white'];
  const selectedElement = elements.find((item) => item.id === selectedId) || null;

  const commit = (next) => onUpdate({ ...slide, elements: next });
  const updateElement = (elementId, patch) => {
    commit(elements.map((item) => item.id === elementId ? { ...item, ...patch } : item));
  };

  const addText = () => {
    const element = createTextElement();
    commit([...elements, element]);
    setSelectedId(element.id);
  };

  const removeSelected = () => {
    if (!selectedId || selectedElement?.locked) return;
    commit(elements.filter((item) => item.id !== selectedId));
    setSelectedId(null);
    setEditingId(null);
  };

  const copySelected = () => {
    const source = elements.find((item) => item.id === selectedId);
    if (!source) return;
    elementClipboard = { ...source, style: source.style ? { ...source.style } : undefined };
    setHasClipboard(true);
  };

  const pasteElement = () => {
    if (!elementClipboard) return;
    const copy = cloneElement(elementClipboard);
    commit([...elements, copy]);
    setSelectedId(copy.id);
    elementClipboard = { ...copy, style: copy.style ? { ...copy.style } : undefined };
    setHasClipboard(true);
  };

  const moveLayer = (direction) => {
    const index = elements.findIndex((item) => item.id === selectedId);
    if (index < 0) return;
    const target = direction === 'front' ? elements.length - 1 : 0;
    if (index === target) return;
    const next = [...elements];
    const [element] = next.splice(index, 1);
    next.splice(target, 0, element);
    commit(next);
  };

  const toggleLock = () => {
    if (!selectedElement) return;
    updateElement(selectedElement.id, { locked: !selectedElement.locked });
    setEditingId(null);
    setCroppingId(null);
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

  const handleImageUpload = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = '';
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
        updateElement(selectedElement.id, { src, storageUrl: uploaded.url, assetId: uploaded.id });
        onNotify?.('Đã thay ảnh', 'success');
      } else {
        const image = {
          id: `el-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          type: 'image',
          role: 'image',
          x: 280,
          y: 120,
          width: 400,
          height: 300,
          rotation: 0,
          objectFit: 'cover',
          src,
          storageUrl: uploaded.url,
          assetId: uploaded.id,
        };
        commit([...elements, image]);
        setSelectedId(image.id);
        onNotify?.('Đã thêm ảnh vào slide', 'success');
      }
    } catch (error) {
      onNotify?.(error.message || 'Không thể tải ảnh lên', 'error');
    } finally {
      setUploadingImage(false);
    }
  };

  useEffect(() => {
    const onKeyDown = (event) => {
      if (document.activeElement?.isContentEditable) return;
      const command = event.ctrlKey || event.metaKey;
      const key = event.key.toLowerCase();

      if (command && key === 'c' && selectedId) {
        event.preventDefault();
        copySelected();
      } else if (command && key === 'v' && elementClipboard) {
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

    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  });

  const startPointerAction = (event, element, mode, deferUntilMove = false) => {
    if (element.locked) {
      event.stopPropagation();
      setSelectedId(element.id);
      return;
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
        const verticalTargets = [0, 480, 960];
        const horizontalTargets = [0, 270, 540];
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
      } else {
        updateElement(element.id, {
          width: clamp(start.element.width + dx, 40, 960 - element.x),
          height: clamp(start.element.height + dy, 30, 540 - element.y),
        });
      }
    };

    const up = () => {
      setGuides({ x: null, y: null });
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
    <div className="element-canvas" style={{ background: themeData.bgGrad }} onPointerDown={() => {
      setSelectedId(null);
      setEditingId(null);
    }}>
      <div className="element-canvas-actions" onPointerDown={(event) => event.stopPropagation()}>
        <input ref={imageInputRef} type="file" accept="image/png,image/jpeg,image/webp,image/gif" hidden onChange={handleImageUpload}/>
        <button type="button" onClick={addText} title="Thêm ô chữ"><Plus size={15}/> Chữ</button>
        <button type="button" onClick={() => imageInputRef.current?.click()} disabled={uploadingImage || selectedElement?.locked} title={selectedElement?.type === 'image' ? 'Thay ảnh' : 'Thêm ảnh'}>
          {uploadingImage ? <Loader2 size={15} className="spin"/> : <ImagePlus size={15}/>} {selectedElement?.type === 'image' ? 'Thay' : 'Ảnh'}
        </button>
        <button
          type="button"
          onClick={() => updateElement(selectedElement.id, { objectFit: selectedElement.objectFit === 'contain' ? 'cover' : 'contain' })}
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
        <button type="button" onClick={copySelected} disabled={!selectedId} title="Sao chép (Ctrl+C)"><Copy size={15}/></button>
        <button type="button" onClick={pasteElement} disabled={!hasClipboard} title="Dán (Ctrl+V)"><ClipboardPaste size={15}/></button>
        <button type="button" onClick={() => moveLayer('back')} disabled={!selectedId} title="Đưa xuống dưới"><ArrowDownToLine size={15}/></button>
        <button type="button" onClick={() => moveLayer('front')} disabled={!selectedId} title="Đưa lên trên"><ArrowUpToLine size={15}/></button>
        <button type="button" onClick={toggleLock} disabled={!selectedId} title={selectedElement?.locked ? 'Mở khóa phần tử' : 'Khóa phần tử'}>
          {selectedElement?.locked ? <Unlock size={15}/> : <Lock size={15}/>}
        </button>
        <button type="button" onClick={removeSelected} disabled={!selectedId || selectedElement?.locked} title="Xóa (Delete)"><Trash2 size={15}/></button>
      </div>

      {guides.x !== null && <div className="canvas-guide vertical" style={{ left: guides.x }}/>} 
      {guides.y !== null && <div className="canvas-guide horizontal" style={{ top: guides.y }}/>} 

      {elements.map((element, index) => (
        <div
          key={element.id}
          className={`canvas-element ${selectedId === element.id ? 'selected' : ''} ${editingId === element.id ? 'editing' : ''} ${element.locked ? 'locked' : ''} ${croppingId === element.id ? 'cropping' : ''}`}
          style={{
            left: element.x,
            top: element.y,
            width: element.width,
            height: element.height,
            zIndex: index + 1,
            transform: `rotate(${element.rotation || 0}deg)`,
          }}
          onPointerDown={(event) => {
            if (editingId === element.id || croppingId === element.id) {
              event.stopPropagation();
              return;
            }
            startPointerAction(event, element, 'move', true);
          }}
          onDoubleClick={(event) => {
            if (element.type !== 'text' || element.locked) return;
            event.stopPropagation();
            setSelectedId(element.id);
            setEditingId(element.id);
          }}
        >
          {selectedId === element.id && !element.locked && croppingId !== element.id && (
            <button
              type="button"
              className="canvas-drag-handle"
              onPointerDown={(event) => startPointerAction(event, element, 'move')}
              title="Kéo để di chuyển"
            >
              <GripHorizontal size={15}/>
            </button>
          )}
          {selectedId === element.id && !element.locked && croppingId !== element.id && (
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
            <AssetImage
              src={resolveAssetUrl(element.src)}
              storageUrl={element.storageUrl}
              assetId={element.assetId}
              alt=""
              draggable={false}
              onPointerDown={croppingId === element.id ? (event) => startImageCrop(event, element) : undefined}
              style={{
                objectFit: element.objectFit || 'cover',
                objectPosition: `${element.objectPositionX ?? 50}% ${element.objectPositionY ?? 50}%`,
              }}
            />
          ) : (
            <TiptapInlineEditor
              style={element.style}
              className="canvas-text"
              value={element.content}
              selected={selectedId === element.id && !element.locked}
              editable={editingId === element.id}
              onExitEdit={() => setEditingId((current) => current === element.id ? null : current)}
              onSave={(html) => updateElement(element.id, { content: html })}
            />
          )}
          {selectedId === element.id && !element.locked && croppingId !== element.id && (
            <button
              type="button"
              className="canvas-resize-handle"
              onPointerDown={(event) => startPointerAction(event, element, 'resize')}
              title="Kéo để đổi kích thước"
            />
          )}
        </div>
      ))}
    </div>
  );
}
