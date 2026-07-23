import { useRef, useState, useCallback, useEffect, useLayoutEffect } from 'react';
import FloatingTextToolbar from './FloatingTextToolbar';
import './FloatingTextToolbar.css';

/**
 * TiptapInlineEditor — pure contentEditable rich text editor.
 * Toolbar shows on both click AND text selection.
 */
export function TiptapInlineEditor({
  value = '',
  onSave,
  className = '',
  style = {},
  placeholder = '',
  editable = true,
  selected = false,
  elementKey,
  onExitEdit,
  autoFit = false,
  minFontSize = 8,
  autoFitBaseFontSize,
  boxStyle,
  onBoxStyleChange,
  onPointerDown,
  onPointerEnter,
  batchMode = false,
}) {
  const editorRef = useRef(null);
  const selectionIdRef = useRef(Symbol('slide-text-box'));
  const selectionRangeRef = useRef(null);
  const [selectedInternal, setSelectedInternal] = useState(false);
  const [editing, setEditing] = useState(false);
  const [toolbarVisible, setToolbarVisible] = useState(false);
  const [toolbarPos, setToolbarPos] = useState({ x: 0, y: 0 });
  const isSelected = selected || selectedInternal;

  // ── Compute toolbar position ─────────────────────────────────────────────
  const computePosition = useCallback(() => {
    const sel = window.getSelection();

    // If text is selected inside this editor → position above selection
    if (sel && sel.rangeCount > 0 && !sel.isCollapsed) {
      const range = sel.getRangeAt(0);
      if (editorRef.current?.contains(range.commonAncestorContainer)) {
        const rect = range.getBoundingClientRect();
        return {
          x: rect.left + rect.width / 2,
          y: rect.top,
        };
      }
    }

    // Otherwise → position above the editor element itself
    if (editorRef.current) {
      const rect = editorRef.current.getBoundingClientRect();
      return {
        x: rect.left + rect.width / 2,
        y: rect.top,
      };
    }

    return null;
  }, []);

  // ── Show toolbar on click / focus ────────────────────────────────────────
  const handleFocus = useCallback(() => {
    const pos = computePosition();
    if (pos) {
      setToolbarPos(pos);
      setToolbarVisible(true);
    }
  }, [computePosition]);

  // ── Update toolbar position when selection changes ────────────────────────
  const handleSelectionChange = useCallback(() => {
    const selection = window.getSelection();
    if (selection?.rangeCount) {
      const range = selection.getRangeAt(0);
      if (editorRef.current?.contains(range.commonAncestorContainer)) {
        selectionRangeRef.current = range.cloneRange();
      }
    }
    if (!toolbarVisible) return;
    const pos = computePosition();
    if (pos) setToolbarPos(pos);
  }, [toolbarVisible, computePosition]);

  useEffect(() => {
    document.addEventListener('selectionchange', handleSelectionChange);
    return () => document.removeEventListener('selectionchange', handleSelectionChange);
  }, [handleSelectionChange]);

  useEffect(() => {
    const handleBoxSelection = (event) => {
      if (event.detail !== selectionIdRef.current) {
        setSelectedInternal(false);
        setEditing(false);
        setToolbarVisible(false);
      }
    };
    const handleOutsidePointer = (event) => {
      if (editorRef.current?.contains(event.target) || event.target.closest?.('.floating-toolbar')) return;
      setSelectedInternal(false);
      setEditing(false);
    };
    document.addEventListener('slide-text-box-selected', handleBoxSelection);
    document.addEventListener('pointerdown', handleOutsidePointer);
    return () => {
      document.removeEventListener('slide-text-box-selected', handleBoxSelection);
      document.removeEventListener('pointerdown', handleOutsidePointer);
    };
  }, []);

  // ── Hide toolbar when focus leaves editor area ────────────────────────────
  const handleBlur = useCallback(() => {
    // Commit before the following click/navigation event reads slide state.
    if (onSave) onSave(editorRef.current?.innerHTML || '');
    setTimeout(() => {
      // Check if focus moved to toolbar (toolbar buttons use onMouseDown preventDefault)
      const activeEl = document.activeElement;
      if (editorRef.current?.contains(activeEl)) return;
      // If focused element is inside floating-toolbar div, keep open
      if (activeEl?.closest('.floating-toolbar')) return;
      setToolbarVisible(false);
    }, 120);
  }, [onSave]);

  // ── Set initial HTML on mount ─────────────────────────────────────────────
  useEffect(() => {
    if (editorRef.current) {
      editorRef.current.innerHTML = value || '';
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // mount only

  useEffect(() => {
    if (document.activeElement !== editorRef.current && editorRef.current?.innerHTML !== (value || '')) {
      editorRef.current.innerHTML = value || '';
    }
  }, [value]);

  useLayoutEffect(() => {
    if (!autoFit || !editorRef.current) return undefined;
    const element = editorRef.current;
    const fit = () => {
      element.style.removeProperty('font-size');
      let size = Number(autoFitBaseFontSize)
        || Number.parseFloat(window.getComputedStyle(element).fontSize)
        || 16;
      element.style.setProperty('font-size', `${size}px`, 'important');
      let attempts = 0;
      while (
        (element.scrollHeight > element.clientHeight + 1 || element.scrollWidth > element.clientWidth + 1)
        && size > minFontSize
        && attempts < 120
      ) {
        size = Math.max(minFontSize, size - 0.5);
        element.style.setProperty('font-size', `${size}px`, 'important');
        attempts += 1;
      }
    };
    const frame = window.requestAnimationFrame(fit);
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(fit);
    observer?.observe(element);
    if (element.parentElement) observer?.observe(element.parentElement);
    window.addEventListener('resize', fit);
    return () => {
      window.cancelAnimationFrame(frame);
      observer?.disconnect();
      window.removeEventListener('resize', fit);
    };
  }, [autoFit, autoFitBaseFontSize, minFontSize, value]);

  useEffect(() => {
    if (!editable || !editing || !editorRef.current) return;
    editorRef.current.focus();
    const selection = window.getSelection();
    const range = document.createRange();
    range.selectNodeContents(editorRef.current);
    range.collapse(false);
    selection?.removeAllRanges();
    selection?.addRange(range);
  }, [editable, editing]);

  useEffect(() => {
    const showToolbar = () => {
      const pos = computePosition();
      if (pos) {
        setToolbarPos(pos);
        setToolbarVisible(true);
      }
    };
    let timeout;
    if (!isSelected) {
      if (!editable) timeout = window.setTimeout(() => setToolbarVisible(false), 0);
      else timeout = window.setTimeout(() => setToolbarVisible(false), 0);
      return () => window.clearTimeout(timeout);
    }
    if (editorRef.current && !editing) {
      const range = document.createRange();
      range.selectNodeContents(editorRef.current);
      selectionRangeRef.current = range;
    }
    timeout = window.setTimeout(showToolbar, 0);
    return () => window.clearTimeout(timeout);
  }, [computePosition, editable, editing, isSelected]);

  const selectBox = useCallback(() => {
    if (!editable) return;
    setSelectedInternal(true);
    document.dispatchEvent(new CustomEvent('slide-text-box-selected', { detail: selectionIdRef.current }));
    editorRef.current?.focus({ preventScroll: true });
  }, [editable]);

  const enterEditMode = useCallback(() => {
    if (!editable) return;
    selectBox();
    setEditing(true);
  }, [editable, selectBox]);

  return (
    <>
      <FloatingTextToolbar
        editorRef={editorRef}
        selectionRangeRef={selectionRangeRef}
        visible={toolbarVisible}
        position={toolbarPos}
        boxStyle={boxStyle}
        onBoxStyleChange={onBoxStyleChange}
        batchMode={batchMode}
        onFormatChange={() => onSave?.(editorRef.current?.innerHTML || '')}
      />
      <div
        ref={editorRef}
        data-slide-element={elementKey || undefined}
        className={`tiptap-editor-wrapper ${isSelected ? 'is-selected' : ''} ${editing ? 'is-editing' : ''} ${className}`}
        style={style}
        contentEditable={editable && editing}
        tabIndex={editable ? 0 : -1}
        suppressContentEditableWarning
        data-placeholder={placeholder}
        onFocus={editing ? handleFocus : undefined}
        onClick={editable ? selectBox : undefined}
        onDoubleClick={editable ? enterEditMode : undefined}
        onPointerDown={onPointerDown}
        onPointerEnter={onPointerEnter}
        onMouseDown={(event) => {
          if (!editable || !editing) event.preventDefault();
        }}
        onBlur={(event) => {
          handleBlur(event);
          setEditing(false);
          onExitEdit?.();
        }}
        onKeyDown={(event) => {
          if (event.key === 'Enter' && !editing) {
            event.preventDefault();
            enterEditMode();
          } else if (event.key === 'Escape') {
            event.preventDefault();
            editorRef.current?.blur();
            setEditing(false);
          }
        }}
      />
    </>
  );
}

export const useTiptapEditor = null;
