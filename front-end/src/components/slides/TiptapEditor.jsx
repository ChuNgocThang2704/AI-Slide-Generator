import { useEffect, useRef, useState, useLayoutEffect, useCallback } from 'react';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import { TextStyleKit } from '@tiptap/extension-text-style';
import TextAlign from '@tiptap/extension-text-align';
import FloatingTextToolbar from './FloatingTextToolbar';
import { PreserveClassAttribute } from './tiptapClassAttribute';
import './FloatingTextToolbar.css';

/**
 * TiptapInlineEditor — a real Tiptap/ProseMirror instance per canvas
 * element (not the previous hand-rolled contentEditable + execCommand
 * wrapper). Undo/redo is intentionally left to the app's own slide-level
 * history (see EditorPage's undo stack), so Tiptap's History extension is
 * disabled — otherwise Ctrl+Z inside a focused box would fight the app
 * shortcut instead of the two ever agreeing on one state.
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
  onEnterEdit,
  onExitEdit,
  autoFit = false,
  minFontSize = 8,
  autoFitBaseFontSize,
  autoResizeHeight = false,
  minHeight = 40,
  onHeightChange,
  boxStyle,
  onBoxStyleChange,
  onPointerDown,
  onPointerEnter,
  batchMode = false,
}) {
  const wrapperRef = useRef(null);
  const [toolbarVisible, setToolbarVisible] = useState(false);
  const [toolbarPos, setToolbarPos] = useState({ x: 0, y: 0 });

  // Callback props change every render; keep the latest in refs so the
  // editor's own event handlers (bound once) never see a stale closure.
  const latest = useRef({});
  useEffect(() => {
    latest.current = { onSave, onEnterEdit, onExitEdit };
  }, [onSave, onEnterEdit, onExitEdit]);

  const computePosition = useCallback(() => {
    const sel = window.getSelection();
    if (sel && sel.rangeCount > 0 && !sel.isCollapsed) {
      const range = sel.getRangeAt(0);
      if (wrapperRef.current?.contains(range.commonAncestorContainer)) {
        const rect = range.getBoundingClientRect();
        return { x: rect.left + rect.width / 2, y: rect.top };
      }
    }
    if (wrapperRef.current) {
      const rect = wrapperRef.current.getBoundingClientRect();
      return { x: rect.left + rect.width / 2, y: rect.top };
    }
    return null;
  }, []);

  const showToolbar = useCallback(() => {
    const pos = computePosition();
    if (pos) {
      setToolbarPos(pos);
      setToolbarVisible(true);
    }
  }, [computePosition]);

  const editor = useEditor({
    editable,
    content: value || '',
    extensions: [
      // trailingNode: Tiptap's default that keeps an empty paragraph after
      // the last block so users can click past a list to type outside it.
      // A slide bullet box has no "outside the list" to click past, so it
      // only ever adds unwanted blank space at the bottom.
      StarterKit.configure({ undoRedo: false, heading: false, trailingNode: false }),
      TextStyleKit,
      TextAlign.configure({ types: ['paragraph'] }),
      PreserveClassAttribute,
    ],
    editorProps: {
      attributes: {
        class: 'canvas-text-content',
        ...(placeholder ? { 'data-placeholder': placeholder } : {}),
      },
    },
    onFocus: () => {
      latest.current.onEnterEdit?.();
      showToolbar();
    },
    onBlur: () => {
      const instance = editorInstanceRef.current;
      if (instance && !instance.isDestroyed) latest.current.onSave?.(instance.getHTML() || '');
      window.setTimeout(() => {
        const active = document.activeElement;
        if (active?.closest?.('.floating-toolbar')) return;
        setToolbarVisible(false);
      }, 120);
      latest.current.onExitEdit?.();
    },
    onSelectionUpdate: () => {
      setToolbarVisible((visible) => {
        if (visible) {
          const pos = computePosition();
          if (pos) setToolbarPos(pos);
        }
        return visible;
      });
    },
  }, []);

  // `onBlur` above is bound once at editor creation and closes over the
  // editor instance from that first render; read the live instance via a
  // ref instead of the (possibly stale) `editor` variable it captured.
  const editorInstanceRef = useRef(null);
  useEffect(() => {
    editorInstanceRef.current = editor;
  }, [editor]);

  useEffect(() => {
    if (!editor || editor.isDestroyed) return;
    editor.setEditable(editable);
    // The double-click that turns editable on is what the user meant as
    // "start typing here" — without this, they'd need a third click just
    // to place the cursor after the box became editable.
    if (editable) editor.commands.focus('end');
  }, [editable, editor]);

  // Sync external content changes (undo/redo, AI edits) into the editor,
  // but never while the user is actively focused in it — that would wipe
  // out their cursor position and any not-yet-blurred keystrokes.
  useLayoutEffect(() => {
    if (!editor || editor.isDestroyed || editor.isFocused) return;
    const current = editor.getHTML();
    const next = value || '';
    if (current !== next && !(current === '<p></p>' && !next)) {
      editor.commands.setContent(next, { emitUpdate: false });
    }
  }, [editor, value]);

  useEffect(() => {
    if (!editor || !selected || editor.isFocused) return;
    // toolbarVisible also has to react to the editor's own focus/blur
    // events (bound once at creation, outside React's render flow), so it
    // can't be derived purely from props during render.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    showToolbar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editor, selected]);

  useEffect(() => {
    if (selected || editor?.isFocused) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setToolbarVisible(false);
  }, [selected, editor]);

  // autoResizeHeight: let the box grow or shrink to fit its content, with
  // no ceiling — deliberately unbounded per product decision, favoring a
  // fully flexible box over stopping it from ever covering something below
  // it. autoFit (used elsewhere, e.g. table cells) is the older, separate
  // strategy: box size stays fixed and the font shrinks to fit instead.
  // The two are mutually exclusive per element, never combined, so neither
  // one's measurement loop fights the other's.
  const latestOnHeightChange = useRef(onHeightChange);
  useEffect(() => {
    latestOnHeightChange.current = onHeightChange;
  }, [onHeightChange]);
  useLayoutEffect(() => {
    if ((!autoFit && !autoResizeHeight) || !wrapperRef.current) return undefined;
    const element = wrapperRef.current;
    let disposed = false;
    let lastReportedHeight = null;

    const resizeToContent = () => {
      element.style.setProperty('height', 'auto', 'important');
      const natural = Math.ceil(element.scrollHeight);
      element.style.removeProperty('height');
      const next = Math.max(minHeight, natural);
      if (lastReportedHeight === null || Math.abs(next - lastReportedHeight) >= 2) {
        lastReportedHeight = next;
        latestOnHeightChange.current?.(next);
      }
    };

    const shrinkFontToFit = () => {
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

    const fit = () => {
      if (disposed) return;
      if (autoResizeHeight) resizeToContent();
      else shrinkFontToFit();
    };
    const frame = window.requestAnimationFrame(fit);
    document.fonts?.ready.then(fit);
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(fit);
    observer?.observe(element);
    if (element.parentElement) observer?.observe(element.parentElement);
    window.addEventListener('resize', fit);
    // The box itself keeps its fixed width/height while typing (that's the
    // slide layout, not something content should resize), so deleting or
    // adding text never changes ITS box size and never fires the observers
    // above. Without this, neither the font nor the height recalculated
    // until something external (like a blur/reload) forced a re-render.
    editor?.on('update', fit);
    return () => {
      disposed = true;
      window.cancelAnimationFrame(frame);
      observer?.disconnect();
      window.removeEventListener('resize', fit);
      editor?.off('update', fit);
    };
  }, [autoFit, autoResizeHeight, autoFitBaseFontSize, minFontSize, minHeight, value, editor]);

  useEffect(() => () => editor?.destroy(), [editor]);

  if (!editor) return null;

  return (
    <>
      <FloatingTextToolbar
        editor={editor}
        visible={toolbarVisible}
        position={toolbarPos}
        boxStyle={boxStyle}
        onBoxStyleChange={onBoxStyleChange}
        batchMode={batchMode}
      />
      <div
        ref={wrapperRef}
        data-slide-element={elementKey || undefined}
        className={`tiptap-editor-wrapper ${selected ? 'is-selected' : ''} ${editor.isFocused ? 'is-editing' : ''} ${className}`}
        style={style}
        onPointerDown={onPointerDown}
        onPointerEnter={onPointerEnter}
      >
        <EditorContent editor={editor} />
      </div>
    </>
  );
}

export const useTiptapEditor = null;
