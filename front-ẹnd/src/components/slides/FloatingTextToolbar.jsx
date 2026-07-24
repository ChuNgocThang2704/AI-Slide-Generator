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
const IconNumberedList = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
    <line x1="9" y1="6" x2="20" y2="6"/>
    <line x1="9" y1="12" x2="20" y2="12"/>
    <line x1="9" y1="18" x2="20" y2="18"/>
    <text x="2.2" y="8" fill="currentColor" stroke="none" fontSize="6.5" fontWeight="700">1</text>
    <text x="2.2" y="14" fill="currentColor" stroke="none" fontSize="6.5" fontWeight="700">2</text>
    <text x="2.2" y="20" fill="currentColor" stroke="none" fontSize="6.5" fontWeight="700">3</text>
  </svg>
);
const IconVerticalAlign = ({ position }) => {
  const y = position === 'top' ? 6 : position === 'bottom' ? 18 : 12;
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
      <line x1="4" y1={y} x2="20" y2={y}/>
      <path d={position === 'top' ? 'M12 19V9m0 0-3 3m3-3 3 3' : position === 'bottom' ? 'M12 5v10m0 0-3-3m3 3 3-3' : 'M12 4v5m0-5-2 2m2-2 2 2M12 20v-5m0 5-2-2m2 2 2-2'}/>
    </svg>
  );
};

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
export default function FloatingTextToolbar({
  editorRef,
  selectionRangeRef,
  visible,
  position,
  onFormatChange,
  boxStyle = {},
  onBoxStyleChange,
  batchMode = false,
}) {
  const colorRef = useRef(null);
  const temporaryEditableRef = useRef(false);
  const [isBold, setIsBold]           = useState(false);
  const [isItalic, setIsItalic]       = useState(false);
  const [isUnderline, setIsUnderline] = useState(false);
  const [align, setAlign]             = useState('left');
  const [fontSize, setFontSize]       = useState('14');
  const [sizeMenuOpen, setSizeMenuOpen] = useState(false);
  const [fontFamily, setFontFamily]   = useState('');
  const [color, setColor]             = useState('#ffffff');
  const [listMode, setListMode]       = useState('none');
  const [lineHeight, setLineHeight]   = useState(String(boxStyle?.lineHeight || 1.35));
  const [verticalAlign, setVerticalAlign] = useState(boxStyle?.verticalAlign || 'top');

  // Sync state with current selection format
  useEffect(() => {
    if (!visible) return;
    setIsBold(queryState('bold'));
    setIsItalic(queryState('italic'));
    setIsUnderline(queryState('underline'));
    const editor = editorRef.current;
    if (batchMode) {
      setIsBold(Number(boxStyle?.fontWeight) >= 600);
      setIsItalic(boxStyle?.fontStyle === 'italic');
      setIsUnderline(String(boxStyle?.textDecoration || '').includes('underline'));
      setAlign(boxStyle?.textAlign || 'left');
      if (boxStyle?.fontSize) setFontSize(String(boxStyle.fontSize));
      if (boxStyle?.fontFamily) setFontFamily(boxStyle.fontFamily);
      if (boxStyle?.color) setColor(boxStyle.color);
    }
    setLineHeight(String(boxStyle?.lineHeight || 1.35));
    setVerticalAlign(boxStyle?.verticalAlign || 'top');
    setListMode(
      editor?.querySelector('ol') ? 'number' :
      editor?.querySelector('ul') ? 'bullet' : 'none'
    );
    setAlign(
      queryState('justifyCenter') ? 'center' :
      queryState('justifyRight')  ? 'right'  : 'left'
    );
  }, [batchMode, boxStyle, editorRef, visible]);

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
    if (!editorRef.current.isContentEditable) {
      editorRef.current.setAttribute('contenteditable', 'true');
      temporaryEditableRef.current = true;
    }
    editorRef.current.focus({ preventScroll: true });
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
    if (temporaryEditableRef.current && editorRef.current) {
      editorRef.current.setAttribute('contenteditable', 'false');
      temporaryEditableRef.current = false;
    }
  };

  // ── Apply font family to selected text ────────────────────────────────────
  const handleFontFamily = (family) => {
    setFontFamily(family);
    if (!family) return;
    if (batchMode && onBoxStyleChange) {
      onBoxStyleChange({ fontFamily: family });
      return;
    }
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
    if (batchMode && onBoxStyleChange) {
      onBoxStyleChange({ fontSize: normalized });
      return;
    }
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
    if (batchMode && onBoxStyleChange) {
      onBoxStyleChange({ color: c });
      return;
    }
    restoreSelection();
    applyInlineStyle(editorRef.current, selectionRangeRef.current, { color: c });
    commitFormat();
  };

  // ── Toggle bold/italic/underline via execCommand (these work reliably) ────
  const toggleBold = () => {
    if (batchMode && onBoxStyleChange) {
      const next = !isBold;
      setIsBold(next);
      onBoxStyleChange({ fontWeight: next ? 700 : 400 });
      return;
    }
    restoreSelection();
    execCmd('bold');
    setIsBold(!isBold);
    commitFormat();
  };
  const toggleItalic = () => {
    if (batchMode && onBoxStyleChange) {
      const next = !isItalic;
      setIsItalic(next);
      onBoxStyleChange({ fontStyle: next ? 'italic' : 'normal' });
      return;
    }
    restoreSelection();
    execCmd('italic');
    setIsItalic(!isItalic);
    commitFormat();
  };
  const toggleUnderline = () => {
    if (batchMode && onBoxStyleChange) {
      const next = !isUnderline;
      setIsUnderline(next);
      onBoxStyleChange({ textDecoration: next ? 'underline' : 'none' });
      return;
    }
    restoreSelection();
    execCmd('underline');
    setIsUnderline(!isUnderline);
    commitFormat();
  };

  // ── Align (works on block level via execCommand) ──────────────────────────
  const applyAlign = (dir) => {
    if (batchMode && onBoxStyleChange) {
      setAlign(dir);
      onBoxStyleChange({ textAlign: dir });
      return;
    }
    restoreSelection();
    execCmd(`justify${dir.charAt(0).toUpperCase() + dir.slice(1)}`);
    setAlign(dir);
    commitFormat();
  };

  const applyListMode = (mode) => {
    restoreSelection();
    const bulletActive = queryState('insertUnorderedList');
    const numberActive = queryState('insertOrderedList');

    if (mode === 'bullet') {
      if (numberActive) execCmd('insertOrderedList');
      if (!bulletActive) execCmd('insertUnorderedList');
      else execCmd('insertUnorderedList');
    } else if (mode === 'number') {
      if (bulletActive) execCmd('insertUnorderedList');
      if (!numberActive) execCmd('insertOrderedList');
      else execCmd('insertOrderedList');
    } else {
      if (bulletActive) execCmd('insertUnorderedList');
      if (numberActive) execCmd('insertOrderedList');
    }
    setListMode(mode === listMode ? 'none' : mode);
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
        className={`ft-btn ${listMode === 'bullet' ? 'active' : ''}`}
        onClick={() => applyListMode(listMode === 'bullet' ? 'none' : 'bullet')}
        title="Danh sách dấu đầu dòng"
      ><IconList /></button>
      <button
        className={`ft-btn ${listMode === 'number' ? 'active' : ''}`}
        onClick={() => applyListMode(listMode === 'number' ? 'none' : 'number')}
        title="Danh sách đánh số"
      ><IconNumberedList /></button>

      <div className="ft-divider" />

      {onBoxStyleChange && (
        <>
          <select
            className="ft-select ft-line-height"
            value={lineHeight}
            onChange={(event) => {
              const value = Number(event.target.value);
              setLineHeight(String(value));
              onBoxStyleChange({ lineHeight: value });
            }}
            title="Khoảng cách dòng"
            aria-label="Khoảng cách dòng"
          >
            <option value="1">1.0</option>
            <option value="1.15">1.15</option>
            <option value="1.2">1.2</option>
            <option value="1.35">1.35</option>
            <option value="1.5">1.5</option>
            <option value="1.55">1.55</option>
            <option value="1.75">1.75</option>
            <option value="2">2.0</option>
          </select>
          {['top', 'middle', 'bottom'].map((value) => (
            <button
              key={value}
              className={`ft-btn ${verticalAlign === value ? 'active' : ''}`}
              onClick={() => {
                setVerticalAlign(value);
                onBoxStyleChange({ verticalAlign: value });
              }}
              title={{ top: 'Căn trên', middle: 'Căn giữa theo chiều dọc', bottom: 'Căn dưới' }[value]}
              aria-label={{ top: 'Căn trên', middle: 'Căn giữa theo chiều dọc', bottom: 'Căn dưới' }[value]}
            >
              <IconVerticalAlign position={value} />
            </button>
          ))}
          <div className="ft-divider" />
        </>
      )}

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
