import React, { useRef, useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import './FloatingTextToolbar.css';

// ── Icon Components ──────────────────────────────────────────────────────────
const IconBold = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
    <path d="M6 4h8a4 4 0 0 1 4 4 4 4 0 0 1-4 4H6z"/>
    <path d="M6 12h9a4 4 0 0 1 4 4 4 4 0 0 1-4 4H6z"/>
  </svg>
);
const IconItalic = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
    <line x1="19" y1="4" x2="10" y2="4"/>
    <line x1="14" y1="20" x2="5" y2="20"/>
    <line x1="15" y1="4" x2="9" y2="20"/>
  </svg>
);
const IconUnderline = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
    <path d="M6 3v7a6 6 0 0 0 6 6 6 6 0 0 0 6-6V3"/>
    <line x1="4" y1="21" x2="20" y2="21"/>
  </svg>
);
const IconAlignLeft = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
    <line x1="3" y1="6" x2="21" y2="6"/>
    <line x1="3" y1="12" x2="15" y2="12"/>
    <line x1="3" y1="18" x2="18" y2="18"/>
  </svg>
);
const IconAlignCenter = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
    <line x1="3" y1="6" x2="21" y2="6"/>
    <line x1="6" y1="12" x2="18" y2="12"/>
    <line x1="4" y1="18" x2="20" y2="18"/>
  </svg>
);
const IconAlignRight = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
    <line x1="3" y1="6" x2="21" y2="6"/>
    <line x1="9" y1="12" x2="21" y2="12"/>
    <line x1="6" y1="18" x2="21" y2="18"/>
  </svg>
);
const IconList = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
    <line x1="9" y1="6" x2="20" y2="6"/>
    <line x1="9" y1="12" x2="20" y2="12"/>
    <line x1="9" y1="18" x2="20" y2="18"/>
    <circle cx="4" cy="6" r="1" fill="currentColor" stroke="none"/>
    <circle cx="4" cy="12" r="1" fill="currentColor" stroke="none"/>
    <circle cx="4" cy="18" r="1" fill="currentColor" stroke="none"/>
  </svg>
);

// ── Font options ─────────────────────────────────────────────────────────────
const FONT_OPTIONS = [
  { label: 'Body font',   value: '' },
  { label: 'Inter',       value: 'Inter, sans-serif' },
  { label: 'Outfit',      value: 'Outfit, sans-serif' },
  { label: 'Arial',       value: 'Arial, sans-serif' },
  { label: 'Verdana',     value: 'Verdana, sans-serif' },
  { label: 'Tahoma',      value: 'Tahoma, sans-serif' },
  { label: 'Trebuchet MS', value: "'Trebuchet MS', sans-serif" },
  { label: 'Georgia',     value: 'Georgia, serif' },
  { label: 'Times New Roman', value: "'Times New Roman', serif" },
  { label: 'Garamond',    value: 'Garamond, serif' },
  { label: 'Roboto',      value: 'Roboto, sans-serif' },
  { label: 'Impact',      value: 'Impact, sans-serif' },
  { label: 'Comic Sans MS', value: "'Comic Sans MS', cursive" },
  { label: 'Courier New', value: "'Courier New', monospace" },
];
const FONT_SIZE_OPTIONS = [4, 5, 6, 8, 9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 32, 36, 40, 48, 54, 60, 72, 80, 96, 120, 144, 180, 200];

// ── Core: wrap selected text in a <span> with given styles ───────────────────
function applySpanStyle(styles = {}) {
  const sel = window.getSelection();
  if (!sel || sel.rangeCount === 0) return;
  const range = sel.getRangeAt(0);
  if (range.collapsed) return; // no selection — nothing to do

  // Check if the selection is entirely within a single existing span we can reuse
  const container = range.commonAncestorContainer;
  const parentSpan =
    container.nodeType === Node.TEXT_NODE
      ? container.parentElement
      : container;

  // Create new span
  const span = document.createElement('span');
  Object.entries(styles).forEach(([prop, val]) => {
    if (val) span.style[prop] = val;
  });

  try {
    // surroundContents works when selection doesn't cross element boundaries
    const contents = range.extractContents();
    span.appendChild(contents);
    range.insertNode(span);

    // Restore selection to the new span
    const newRange = document.createRange();
    newRange.selectNodeContents(span);
    sel.removeAllRanges();
    sel.addRange(newRange);
  } catch (e) {
    // Fallback to execCommand for complex selections
    console.warn('applySpanStyle fallback:', e);
  }
}

// ── Core: execCommand helpers ─────────────────────────────────────────────────
function execCmd(cmd, value = null) {
  document.execCommand(cmd, false, value);
}
function queryState(cmd) {
  try { return document.queryCommandState(cmd); } catch { return false; }
}

function applyInlineStyle(editor, range, styles) {
  if (!editor || !range || range.collapsed) return null;
  const root = range.commonAncestorContainer;
  const walker = document.createTreeWalker(
    root.nodeType === Node.TEXT_NODE ? root.parentNode : root,
    NodeFilter.SHOW_TEXT
  );
  const nodes = [];
  let node = walker.nextNode();
  while (node) {
    if (editor.contains(node) && node.nodeValue && range.intersectsNode(node)) nodes.push(node);
    node = walker.nextNode();
  }

  const styledNodes = [];
  nodes.forEach((textNode) => {
    const start = textNode === range.startContainer ? range.startOffset : 0;
    const end = textNode === range.endContainer ? range.endOffset : textNode.nodeValue.length;
    if (start >= end) return;

    if (end < textNode.nodeValue.length) textNode.splitText(end);
    const selectedNode = start > 0 ? textNode.splitText(start) : textNode;
    const span = document.createElement('span');
    Object.assign(span.style, styles);
    selectedNode.parentNode.insertBefore(span, selectedNode);
    span.appendChild(selectedNode);
    styledNodes.push(selectedNode);
  });

  if (!styledNodes.length) return null;
  const nextRange = document.createRange();
  nextRange.setStart(styledNodes[0], 0);
  nextRange.setEnd(styledNodes.at(-1), styledNodes.at(-1).nodeValue.length);
  const selection = window.getSelection();
  selection.removeAllRanges();
  selection.addRange(nextRange);
  return nextRange;
}

// ── FloatingTextToolbar Component ─────────────────────────────────────────────
export default function FloatingTextToolbar({ editorRef, selectionRangeRef, visible, position, onFormatChange }) {
  const colorRef = useRef(null);
  const [isBold, setIsBold]           = useState(false);
  const [isItalic, setIsItalic]       = useState(false);
  const [isUnderline, setIsUnderline] = useState(false);
  const [align, setAlign]             = useState('left');
  const [fontSize, setFontSize]       = useState('14');
  const [sizeMenuOpen, setSizeMenuOpen] = useState(false);
  const [fontFamily, setFontFamily]   = useState('');
  const [color, setColor]             = useState('#ffffff');

  // Sync state with current selection format
  useEffect(() => {
    if (!visible) return;
    setIsBold(queryState('bold'));
    setIsItalic(queryState('italic'));
    setIsUnderline(queryState('underline'));
    setAlign(
      queryState('justifyCenter') ? 'center' :
      queryState('justifyRight')  ? 'right'  : 'left'
    );
  }, [visible]);

  if (!visible) return null;

  // ── Position: fixed, above the selection/editor ───────────────────────────
  const toolbarStyle = {
    position: 'fixed',
    top:  Math.max(8, position.y - 54),
    left: Math.min(
      Math.max(80, position.x),
      window.innerWidth - 80
    ),
    transform: 'translateX(-50%)',
    zIndex: 99999,
  };
  const dockHost = document.getElementById('editor-format-toolbar-host');

  // Keep selection alive when clicking toolbar
  const handleMouseDown = (e) => {
    if (e.target.closest('select, input')) return;
    e.preventDefault();
  };

  const restoreSelection = () => {
    if (!editorRef.current) return false;
    let range = selectionRangeRef?.current;
    if (!range || range.collapsed) {
      range = document.createRange();
      range.selectNodeContents(editorRef.current);
      selectionRangeRef.current = range;
    }
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    return true;
  };

  const commitFormat = () => {
    selectionRangeRef.current = window.getSelection()?.rangeCount
      ? window.getSelection().getRangeAt(0).cloneRange()
      : selectionRangeRef.current;
    onFormatChange?.();
  };

  // ── Apply font family to selected text ────────────────────────────────────
  const handleFontFamily = (family) => {
    setFontFamily(family);
    if (!family) return;
    restoreSelection();
    applyInlineStyle(editorRef.current, selectionRangeRef.current, { fontFamily: family });
    commitFormat();
  };

  // ── Apply font size to selected text ─────────────────────────────────────
  const handleFontSize = (sz) => {
    const num = parseInt(sz, 10);
    if (!Number.isFinite(num)) {
      setFontSize('14');
      return;
    }
    const normalized = Math.min(200, Math.max(4, num));
    setFontSize(String(normalized));
    restoreSelection();
    applyInlineStyle(editorRef.current, selectionRangeRef.current, { fontSize: `${normalized}px` });
    commitFormat();
  };

  const stepFontSize = (delta) => {
    const current = parseInt(fontSize, 10);
    handleFontSize((Number.isFinite(current) ? current : 14) + delta);
  };

  // ── Apply color to selected text ──────────────────────────────────────────
  const handleColor = (c) => {
    setColor(c);
    restoreSelection();
    applyInlineStyle(editorRef.current, selectionRangeRef.current, { color: c });
    commitFormat();
  };

  // ── Toggle bold/italic/underline via execCommand (these work reliably) ────
  const toggleBold = () => {
    restoreSelection();
    execCmd('bold');
    setIsBold(!isBold);
    commitFormat();
  };
  const toggleItalic = () => {
    restoreSelection();
    execCmd('italic');
    setIsItalic(!isItalic);
    commitFormat();
  };
  const toggleUnderline = () => {
    restoreSelection();
    execCmd('underline');
    setIsUnderline(!isUnderline);
    commitFormat();
  };

  // ── Align (works on block level via execCommand) ──────────────────────────
  const applyAlign = (dir) => {
    restoreSelection();
    execCmd(`justify${dir.charAt(0).toUpperCase() + dir.slice(1)}`);
    setAlign(dir);
    commitFormat();
  };

  const toggleBulletList = () => {
    restoreSelection();
    execCmd('insertUnorderedList');
    commitFormat();
  };


  const toolbar = (
    <div
      className={`floating-toolbar ${dockHost ? 'docked' : ''}`}
      style={dockHost ? undefined : toolbarStyle}
      onMouseDown={handleMouseDown}
    >
      {/* ── Font Family ── */}
      <select
        className="ft-select"
        value={fontFamily}
        onChange={(e) => handleFontFamily(e.target.value)}
      >
        {FONT_OPTIONS.map((f) => (
          <option key={f.value} value={f.value}>{f.label}</option>
        ))}
      </select>

      {/* ── Font Size ── */}
      <div className="ft-size-control">
        <button className="ft-size-step" onClick={() => stepFontSize(-1)} title="Giảm cỡ chữ">−</button>
        <input
          type="text"
          inputMode="numeric"
          className="ft-size-input"
          value={fontSize}
          aria-label="Cỡ chữ"
          onFocus={(e) => {
            e.target.select();
            setSizeMenuOpen(true);
          }}
          onChange={(e) => {
            if (/^\d{0,3}$/.test(e.target.value)) setFontSize(e.target.value);
          }}
          onBlur={(e) => {
            handleFontSize(e.target.value);
            window.setTimeout(() => setSizeMenuOpen(false), 120);
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              handleFontSize(e.currentTarget.value);
              editorRef?.current?.focus();
            } else if (e.key === 'Escape') {
              setFontSize('14');
              editorRef?.current?.focus();
            }
          }}
        />
        <button className="ft-size-step" onClick={() => stepFontSize(1)} title="Tăng cỡ chữ">+</button>
        {sizeMenuOpen && (
          <div className="ft-size-menu" role="listbox" aria-label="Danh sách cỡ chữ">
            {FONT_SIZE_OPTIONS.map((size) => (
              <button
                key={size}
                type="button"
                className={String(size) === fontSize ? 'active' : ''}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => {
                  handleFontSize(size);
                  setSizeMenuOpen(false);
                }}
              >
                {size}
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="ft-divider" />

      {/* ── Bold ── */}
      <button
        className={`ft-btn ${isBold ? 'active' : ''}`}
        onClick={toggleBold}
        title="Bold (Ctrl+B)"
      ><IconBold /></button>

      {/* ── Italic ── */}
      <button
        className={`ft-btn ${isItalic ? 'active' : ''}`}
        onClick={toggleItalic}
        title="Italic (Ctrl+I)"
      ><IconItalic /></button>

      {/* ── Underline ── */}
      <button
        className={`ft-btn ${isUnderline ? 'active' : ''}`}
        onClick={toggleUnderline}
        title="Underline (Ctrl+U)"
      ><IconUnderline /></button>

      <div className="ft-divider" />

      {/* ── Bullet list ── */}
      <button
        className="ft-btn"
        onClick={toggleBulletList}
        title="Bullet list"
      ><IconList /></button>

      <div className="ft-divider" />

      {/* ── Text Align ── */}
      <button
        className={`ft-btn ${align === 'left' ? 'active' : ''}`}
        onClick={() => applyAlign('left')}
        title="Align left"
      ><IconAlignLeft /></button>
      <button
        className={`ft-btn ${align === 'center' ? 'active' : ''}`}
        onClick={() => applyAlign('center')}
        title="Align center"
      ><IconAlignCenter /></button>
      <button
        className={`ft-btn ${align === 'right' ? 'active' : ''}`}
        onClick={() => applyAlign('right')}
        title="Align right"
      ><IconAlignRight /></button>

      <div className="ft-divider" />

      {/* ── Text Color ── */}
      <div
        className="ft-color-btn"
        title="Text color"
        onClick={() => colorRef.current?.click()}
      >
        <div className="ft-color-swatch" style={{ background: color }} />
        <input
          ref={colorRef}
          type="color"
          value={color}
          onChange={(e) => handleColor(e.target.value)}
        />
      </div>
    </div>
  );
  return dockHost ? createPortal(toolbar, dockHost) : toolbar;
}
