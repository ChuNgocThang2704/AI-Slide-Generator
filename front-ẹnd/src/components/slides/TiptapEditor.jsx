import { useRef, useState, useCallback, useEffect } from 'react';
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
  onExitEdit,
}) {
  const editorRef = useRef(null);
  const selectionRangeRef = useRef(null);
  const [toolbarVisible, setToolbarVisible] = useState(false);
  const [toolbarPos, setToolbarPos] = useState({ x: 0, y: 0 });

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

  useEffect(() => {
    if (!editable || !editorRef.current) return;
    editorRef.current.focus();
    const selection = window.getSelection();
    const range = document.createRange();
    range.selectNodeContents(editorRef.current);
    range.collapse(false);
    selection?.removeAllRanges();
    selection?.addRange(range);
  }, [editable]);

  useEffect(() => {
    const showToolbar = () => {
      const pos = computePosition();
      if (pos) {
        setToolbarPos(pos);
        setToolbarVisible(true);
      }
    };
    let timeout;
    if (!selected) {
      if (!editable) timeout = window.setTimeout(() => setToolbarVisible(false), 0);
      return () => window.clearTimeout(timeout);
    }
    if (!editable) selectionRangeRef.current = null;
    timeout = window.setTimeout(showToolbar, 0);
    return () => window.clearTimeout(timeout);
  }, [computePosition, editable, selected]);

  return (
    <>
      <FloatingTextToolbar
        editorRef={editorRef}
        selectionRangeRef={selectionRangeRef}
        visible={toolbarVisible}
        position={toolbarPos}
        onFormatChange={() => onSave?.(editorRef.current?.innerHTML || '')}
      />
      <div
        ref={editorRef}
        className={`tiptap-editor-wrapper ${className}`}
        style={style}
        contentEditable={editable || selected}
        tabIndex={editable ? 0 : -1}
        suppressContentEditableWarning
        data-placeholder={placeholder}
        onFocus={editable ? handleFocus : undefined}
        onClick={editable ? handleFocus : undefined}
        onMouseDown={(event) => {
          if (!editable) event.preventDefault();
        }}
        onBlur={(event) => {
          handleBlur(event);
          onExitEdit?.();
        }}
        onKeyDown={(event) => {
          if (event.key !== 'Escape') return;
          event.preventDefault();
          editorRef.current?.blur();
        }}
      />
    </>
  );
}

export const useTiptapEditor = null;
