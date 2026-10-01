import { useRef, useState, useEffect } from 'react';
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
  { label: 'Be Vietnam Pro',      value: "'Be Vietnam Pro', sans-serif" },
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

// ── FloatingTextToolbar Component ─────────────────────────────────────────────
// All formatting goes through the Tiptap `editor` instance's own command
// chain (`editor.chain().focus()....run()`), never `document.execCommand` —
// that deprecated API is what made list-toggling and other formatting
// unreliable before. `editor.isActive(...)` replaces `queryCommandState`.
export default function FloatingTextToolbar({
  editor,
  visible,
  position,
  boxStyle = {},
  onBoxStyleChange,
  batchMode = false,
}) {
  const colorRef = useRef(null);
  const [sizeMenuOpen, setSizeMenuOpen] = useState(false);
  // Only the font-size text input needs a local buffer, for the keystrokes
  // between focus and commit — everything else below is derived fresh from
  // the editor/box on every render (like isBold/isItalic already were),
  // so it never goes stale when the selection moves or a different box
  // gets focused.
  const [fontSizeDraft, setFontSizeDraft] = useState(null);
  const [, forceUpdate] = useState(0);

  // Re-render on every selection/transaction so isActive()- and
  // getAttributes()-driven state (bold/italic/list/align/font/size/color)
  // stays in sync with the cursor, including while highlighting a range
  // whose formatting differs from whatever was selected before.
  useEffect(() => {
    if (!editor) return undefined;
    const rerender = () => forceUpdate((n) => n + 1);
    editor.on('selectionUpdate', rerender);
    editor.on('transaction', rerender);
    return () => {
      editor.off('selectionUpdate', rerender);
      editor.off('transaction', rerender);
    };
  }, [editor]);

  if (!visible || !editor || editor.isDestroyed) return null;

  const attrs = editor.getAttributes('textStyle');
  const derivedFontSize = String(
    (batchMode && boxStyle?.fontSize) || Number.parseInt(attrs.fontSize, 10) || 14,
  );
  const fontSize = fontSizeDraft ?? derivedFontSize;
  const fontFamily = (batchMode && boxStyle?.fontFamily) || attrs.fontFamily || '';
  const color = (batchMode && boxStyle?.color) || attrs.color || '#ffffff';
  const lineHeight = String(boxStyle?.lineHeight || 1.35);
  const verticalAlign = boxStyle?.verticalAlign || 'top';

  const isBold = editor.isActive('bold');
  const isItalic = editor.isActive('italic');
  const isUnderline = editor.isActive('underline');
  const listMode = editor.isActive('bulletList') ? 'bullet' : editor.isActive('orderedList') ? 'number' : 'none';
  // Paragraphs inside list items report their alignment through their own
  // attributes; isActive({ textAlign }) alone misses them.
  const paragraphAlign = editor.getAttributes('paragraph').textAlign;
  const align = ['center', 'right', 'justify'].includes(paragraphAlign) ? paragraphAlign : 'left';

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

  // Keep selection alive when clicking toolbar.
  const handleMouseDown = (e) => {
    if (e.target.closest('select, input')) return;
    e.preventDefault();
  };

  // ── Font family ────────────────────────────────────────────────────────
  const handleFontFamily = (family) => {
    if (!family) return;
    if (batchMode && onBoxStyleChange) {
      onBoxStyleChange({ fontFamily: family });
      return;
    }
    editor.chain().focus().setFontFamily(family).run();
  };

  // ── Font size ──────────────────────────────────────────────────────────
  const handleFontSize = (sz) => {
    const num = parseInt(sz, 10);
    if (!Number.isFinite(num)) return;
    const normalized = Math.min(200, Math.max(4, num));
    if (batchMode && onBoxStyleChange) {
      onBoxStyleChange({ fontSize: normalized });
      return;
    }
    editor.chain().focus().setFontSize(`${normalized}px`).run();
  };

  const stepFontSize = (delta) => {
    const current = parseInt(fontSize, 10);
    handleFontSize((Number.isFinite(current) ? current : 14) + delta);
  };

  // ── Text color ─────────────────────────────────────────────────────────
  const handleColor = (c) => {
    if (batchMode && onBoxStyleChange) {
      onBoxStyleChange({ color: c });
      return;
    }
    editor.chain().focus().setColor(c).run();
  };

  // ── Bold / italic / underline ─────────────────────────────────────────
  const toggleBold = () => {
    if (batchMode && onBoxStyleChange) {
      onBoxStyleChange({ fontWeight: isBold ? 400 : 700 });
      return;
    }
    editor.chain().focus().toggleBold().run();
  };
  const toggleItalic = () => {
    if (batchMode && onBoxStyleChange) {
      onBoxStyleChange({ fontStyle: isItalic ? 'normal' : 'italic' });
      return;
    }
    editor.chain().focus().toggleItalic().run();
  };
  const toggleUnderline = () => {
    if (batchMode && onBoxStyleChange) {
      onBoxStyleChange({ textDecoration: isUnderline ? 'none' : 'underline' });
      return;
    }
    editor.chain().focus().toggleUnderline().run();
  };

  // ── Align ──────────────────────────────────────────────────────────────
  const applyAlign = (dir) => {
    if (batchMode && onBoxStyleChange) {
      onBoxStyleChange({ textAlign: dir });
      return;
    }
    editor.chain().focus().setTextAlign(dir).run();
  };

  // Tiptap's toggleBulletList/toggleOrderedList are real ProseMirror
  // commands, not the deprecated execCommand — they reliably turn a list
  // off again when it's already active, switch cleanly between bullet and
  // numbered, and never split one list into disconnected fragments.
  const applyListMode = (mode) => {
    const chain = editor.chain().focus();
    if (mode === 'bullet') chain.toggleBulletList().run();
    else if (mode === 'number') chain.toggleOrderedList().run();
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
            setFontSizeDraft(fontSize);
          }}
          onChange={(e) => {
            if (/^\d{0,3}$/.test(e.target.value)) setFontSizeDraft(e.target.value);
          }}
          onBlur={(e) => {
            handleFontSize(e.target.value);
            setFontSizeDraft(null);
            window.setTimeout(() => setSizeMenuOpen(false), 120);
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              handleFontSize(e.currentTarget.value);
              setFontSizeDraft(null);
              editor.chain().focus();
            } else if (e.key === 'Escape') {
              setFontSizeDraft(null);
              editor.chain().focus();
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
                  setFontSizeDraft(null);
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
        onClick={() => applyListMode('bullet')}
        title="Danh sách dấu đầu dòng"
      ><IconList /></button>
      <button
        className={`ft-btn ${listMode === 'number' ? 'active' : ''}`}
        onClick={() => applyListMode('number')}
        title="Danh sách đánh số"
      ><IconNumberedList /></button>

      <div className="ft-divider" />

      {onBoxStyleChange && (
        <>
          <select
            className="ft-select ft-line-height"
            value={lineHeight}
            onChange={(event) => {
              onBoxStyleChange({ lineHeight: Number(event.target.value) });
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
              onClick={() => onBoxStyleChange({ verticalAlign: value })}
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
