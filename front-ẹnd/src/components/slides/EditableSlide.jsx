import React from 'react';
import { motion } from 'framer-motion';
import { TiptapInlineEditor } from './TiptapEditor';
import './EditableSlide.css';
import { ChartVisual, TableVisual } from './StructuredVisual';
import './StructuredVisual.css';
import { resolveAssetUrl } from '../../utils/assetUrl';

// ─── Theme map (same as SlideRenderer) ───────────────────────────────────────
export const THEMES = {
  'soft-blue': {
    id: 'soft-blue',
    bg: '#f8fbff', bgGrad: 'linear-gradient(160deg, #f0f7ff 0%, #ffffff 55%, #e8f4fd 100%)',
    primary: '#0d5099', accent: '#3b96d2',
    accentAlt: '#7ec8e3',
    text: '#0b2e4a', textSub: '#4a6a85',
    surface: '#eaf4fc', surfaceAlt: '#ffffff',
    surfaceBorder: 'rgba(59, 150, 210, 0.2)',
    accentGrad: 'linear-gradient(135deg, #0d5099 0%, #3b96d2 60%, #7ec8e3 100%)',
    panelBg: 'linear-gradient(160deg, #0d5099 0%, #1a72b8 100%)',
    fontTitle: "'Nunito', sans-serif", fontBody: "'Inter', sans-serif",
    isLight: true,
  },
  'royal-purple': {
    id: 'royal-purple',
    bg: '#0b0518', bgGrad: 'linear-gradient(135deg, #0b0518, #1a0f30)',
    primary: '#9948FF', accent: '#ED7D31',
    text: '#ffffff', textSub: '#c0a8e0',
    surface: 'rgba(153, 72, 255, 0.08)', surfaceBorder: 'rgba(153, 72, 255, 0.25)',
    accentGrad: 'linear-gradient(135deg, #9948FF, #ED7D31)',
    fontTitle: "'Playfair Display', serif", fontBody: "'Inter', sans-serif",
    isLight: false,
  },
  'clean-white': {
    id: 'clean-white',
    bg: '#ffffff', bgGrad: '#ffffff',
    primary: '#2d2d2d', accent: '#4f46e5',
    text: '#1a1a1a', textSub: '#555555',
    surface: '#f5f5f5', surfaceBorder: '#e0e0e0',
    accentGrad: 'linear-gradient(135deg,#4f46e5,#7c3aed)',
    fontTitle: "'Playfair Display', serif", fontBody: "'Inter', sans-serif",
    isLight: true,
  },
  'modern-dark': {
    id: 'modern-dark',
    bg: '#0d0d1a', bgGrad: 'linear-gradient(135deg,#0d0d1a,#1c1c3a)',
    primary: '#6c63ff', accent: '#ff6584',
    text: '#ffffff', textSub: 'rgba(255,255,255,0.65)',
    surface: 'rgba(255,255,255,0.06)', surfaceBorder: 'rgba(108,99,255,0.3)',
    accentGrad: 'linear-gradient(135deg,#6c63ff,#ff6584)',
    fontTitle: "'Space Grotesk', sans-serif", fontBody: "'Inter', sans-serif",
    isLight: false,
  },
  'playful-yellow': {
    id: 'playful-yellow',
    bg: '#fffcf0', bgGrad: 'linear-gradient(135deg,#fffbeb,#fef9e7)',
    primary: '#f59e0b', accent: '#8b5cf6',
    text: '#2e1e0a', textSub: 'rgba(46,30,10,0.72)',
    surface: 'rgba(245,158,11,0.08)', surfaceBorder: 'rgba(245,158,11,0.25)',
    accentGrad: 'linear-gradient(135deg,#f59e0b,#8b5cf6)',
    fontTitle: "'Fredoka One', cursive", fontBody: "'Inter', sans-serif",
    isLight: true,
  },
  'gradient-border': {
    id: 'gradient-border',
    bg: '#f8fafc', bgGrad: 'linear-gradient(160deg,#f8fafc 0%,#eff6ff 100%)',
    primary: '#6c63ff', accent: '#38bdf8',
    text: '#0f172a', textSub: '#475569',
    surface: '#f1f5f9', surfaceBorder: 'rgba(108,99,255,0.15)',
    accentGrad: 'linear-gradient(135deg,#6c63ff,#38bdf8)',
    fontTitle: "'Plus Jakarta Sans', sans-serif", fontBody: "'Inter', sans-serif",
    isLight: true,
  },
  'blue-planet': {
    id: 'blue-planet',
    bg: '#02001a', bgGrad: 'linear-gradient(145deg, #02001a, #04022a, #0b0754)',
    primary: '#00f2fe', accent: '#4facfe',
    text: '#ffffff', textSub: 'rgba(255,255,255,0.65)',
    surface: 'rgba(255,255,255,0.05)', surfaceBorder: 'rgba(0,242,254,0.3)',
    accentGrad: 'linear-gradient(135deg,#00f2fe,#4facfe)',
    fontTitle: "'Exo 2', sans-serif", fontBody: "'Inter', sans-serif",
    isLight: false,
  },
  'nature-green': {
    id: 'nature-green',
    bg: '#0a2318', bgGrad: 'linear-gradient(135deg,#0a2318,#0f3426)',
    primary: '#27ae60', accent: '#2ecc71',
    text: '#e8f5e2', textSub: 'rgba(232,245,226,0.75)',
    surface: 'rgba(255,255,255,0.07)', surfaceBorder: 'rgba(39,174,96,0.35)',
    accentGrad: 'linear-gradient(135deg,#27ae60,#2ecc71)',
    fontTitle: "'Merriweather', serif", fontBody: "'Inter', sans-serif",
    isLight: false,
  },
  'tech-purple': {
    id: 'tech-purple',
    bg: '#0a0015', bgGrad: 'linear-gradient(135deg,#0a0015,#160026)',
    primary: '#9b59b6', accent: '#e056fd',
    text: '#ffffff', textSub: 'rgba(255,255,255,0.65)',
    surface: 'rgba(255,255,255,0.06)', surfaceBorder: 'rgba(224,86,253,0.35)',
    accentGrad: 'linear-gradient(135deg,#9b59b6,#e056fd)',
    fontTitle: "'Rajdhani', sans-serif", fontBody: "'Inter', sans-serif",
    isLight: false,
  },
};

// ─── Inline editable text (Tiptap-powered) ───────────────────────────────────
function InlineText({ value, onSave, slideKey, field, tag: Tag = 'div', className = '', style = {}, placeholder = '' }) {
  const handleSave = (html) => {
    // Strip to plain text for simple fields (title, subtitle, author, role, contact)
    const tmp = document.createElement('div');
    tmp.innerHTML = html;
    const plain = tmp.innerText?.trim() || '';
    onSave(field, plain, html);
  };

  return (
    <TiptapInlineEditor
      key={`${slideKey}__${field}`}
      value={value || ''}
      onSave={handleSave}
      className={`es-editable ${className}`}
      style={style}
      placeholder={placeholder}
    />
  );
}

// Bullets (Tiptap with BulletList support)
function InlineBullets({ bullets = [], richValue = '', onSave, slideKey, t }) {
  // Convert bullet array → HTML list for Tiptap
  const initialHTML = richValue || (bullets.length
    ? `<ul>${bullets.map((b) => `<li>${b}</li>`).join('')}</ul>`
    : '');

  const handleSave = (html) => {
    // Parse HTML back to array of plain text lines
    const tmp = document.createElement('div');
    tmp.innerHTML = html;
    tmp.querySelectorAll('li').forEach((item) => {
      if (!item.innerText?.trim()) item.remove();
    });
    const lines = [];
    // Handle both <li> items and plain <p> paragraphs
    tmp.querySelectorAll('li, p').forEach((el) => {
      const text = el.innerText?.trim();
      if (text) lines.push(text);
    });
    // Fallback: if no structured elements, split by newline
    if (lines.length === 0) {
      const raw = tmp.innerText?.trim() || '';
      raw.split('\n').filter(Boolean).forEach((l) => lines.push(l.trim()));
    }
    onSave('bullets', lines, tmp.innerHTML);
  };

  return (
    <TiptapInlineEditor
      key={`${slideKey}__bullets`}
      value={initialHTML}
      onSave={handleSave}
      className="es-editable es-bullets-editable"
      style={{ color: t.textSub, fontFamily: t.fontBody }}
      placeholder="Nhập bullet points, mỗi dòng một ý..."
    />
  );
}

// Theme-specific decorations
function Deco({ t }) {
  if (t.id === 'royal-purple') {
    return (
      <div className="es-deco" aria-hidden>
        {/* Deep violet background decorative orbs */}
        <motion.div
          animate={{ scale: [1, 1.1, 1], opacity: [0.3, 0.5, 0.3] }}
          transition={{ duration: 10, repeat: Infinity, ease: "easeInOut" }}
          style={{ position: 'absolute', top: -80, right: -80, width: 260, height: 260, borderRadius: '50%', background: '#9948FF', filter: 'blur(45px)' }}
        />
        <motion.div
          animate={{ scale: [1, 1.08, 1] }}
          transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
          style={{ position: 'absolute', bottom: -60, left: -60, width: 200, height: 200, borderRadius: '50%', background: '#ED7D31', filter: 'blur(40px)', opacity: 0.15 }}
        />
      </div>
    );
  }

  if (t.id === 'soft-blue') {
    return (
      <div className="es-deco" aria-hidden>
        {/* Soft blob top-left */}
        <motion.div
          animate={{ scale: [1, 1.08, 1], opacity: [0.35, 0.55, 0.35] }}
          transition={{ duration: 12, repeat: Infinity, ease: 'easeInOut' }}
          style={{
            position: 'absolute', top: -70, left: -70,
            width: 260, height: 260, borderRadius: '50%',
            background: 'radial-gradient(circle, #bfdffa 0%, #dbeafe 60%, transparent 100%)',
            filter: 'blur(18px)',
          }}
        />
        {/* Wave bottom */}
        <motion.svg
          animate={{ y: [0, -6, 0] }}
          transition={{ duration: 8, repeat: Infinity, ease: 'easeInOut' }}
          style={{ position: 'absolute', bottom: -10, left: 0, width: '100%', height: 110 }}
          viewBox="0 0 960 110" preserveAspectRatio="none"
        >
          <path d="M0,60 C180,110 380,20 600,70 C780,110 880,50 960,65 L960,110 L0,110 Z"
            fill="#0d5099" opacity="0.05" />
          <path d="M0,80 C200,40 450,100 700,60 C840,38 920,75 960,80 L960,110 L0,110 Z"
            fill="#3b96d2" opacity="0.07" />
        </motion.svg>
        {/* Rotating ring top-right */}
        <motion.div
          animate={{ rotate: [0, 360] }}
          transition={{ duration: 40, repeat: Infinity, ease: 'linear' }}
          style={{
            position: 'absolute', top: -30, right: 60,
            width: 160, height: 160, borderRadius: '50%',
            border: '1.5px dashed rgba(59,150,210,0.25)',
          }}
        />
        <div style={{
          position: 'absolute', top: 10, right: 90,
          width: 100, height: 100, borderRadius: '50%',
          border: '1px solid rgba(13,80,153,0.12)',
        }} />
        {/* Sparkle dots */}
        <motion.div
          animate={{ opacity: [0.4, 1, 0.4], scale: [1, 1.3, 1] }}
          transition={{ duration: 4, repeat: Infinity, ease: 'easeInOut' }}
          style={{ position: 'absolute', bottom: 68, left: '38%', width: 7, height: 7, borderRadius: '50%', background: '#3b96d2' }}
        />
        <motion.div
          animate={{ opacity: [0.2, 0.7, 0.2], scale: [1, 1.2, 1] }}
          transition={{ duration: 6, repeat: Infinity, ease: 'easeInOut', delay: 1.5 }}
          style={{ position: 'absolute', top: 55, right: '32%', width: 5, height: 5, borderRadius: '50%', background: '#0d5099' }}
        />
        <motion.div
          animate={{ opacity: [0.3, 0.8, 0.3] }}
          transition={{ duration: 5, repeat: Infinity, ease: 'easeInOut', delay: 0.8 }}
          style={{ position: 'absolute', top: 90, left: '55%', width: 4, height: 4, borderRadius: '50%', background: '#7ec8e3' }}
        />
      </div>
    );
  }

  if (t.id === 'clean-white') {
    return (
      <div className="es-deco" aria-hidden>
        <div style={{ position: 'absolute', top: 32, left: 32, width: 3, height: 40, background: t.accentGrad }} />
      </div>
    );
  }

  if (t.id === 'playful-yellow') {
    return (
      <div className="es-deco" aria-hidden>
        <motion.svg
          animate={{ y: [0, -6, 0] }}
          transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}
          style={{ position: 'absolute', top: -30, right: -30, width: 220, height: 220, fill: '#f59e0b', opacity: 0.15 }}
          viewBox="0 0 100 100"
        >
          <path d="M30,0 C50,15 65,-10 85,10 C105,30 90,55 100,80 L100,0 Z" />
        </motion.svg>
        <motion.div
          animate={{ scale: [1, 1.1, 1], opacity: [0.12, 0.18, 0.12] }}
          transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
          style={{ position: 'absolute', width: 140, height: 140, borderRadius: '50%', background: '#8b5cf6', bottom: -50, left: -50, filter: 'blur(30px)' }}
        />
        <motion.svg
          animate={{ scale: [1, 1.05, 1] }}
          transition={{ duration: 7, repeat: Infinity, ease: "easeInOut" }}
          style={{ position: 'absolute', bottom: -20, right: -20, width: 120, height: 120, fill: '#f59e0b', opacity: 0.12 }}
          viewBox="0 0 100 100"
        >
          <circle cx="50" cy="50" r="40" />
        </motion.svg>
      </div>
    );
  }

  if (t.id === 'gradient-border') {
    return (
      <div className="es-deco" aria-hidden>
        <motion.div
          animate={{ opacity: [0.85, 1, 0.85] }}
          transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
          style={{
            position: 'absolute',
            inset: 16,
            border: '3px solid transparent',
            borderRadius: 12,
            pointerEvents: 'none',
            background: 'linear-gradient(#f8fafc, #f8fafc) padding-box, linear-gradient(135deg, #6c63ff, #38bdf8) border-box'
          }}
        />
      </div>
    );
  }

  if (t.id === 'blue-planet') {
    return (
      <div className="es-deco" aria-hidden>
        {/* Giant glowing planet sphere at bottom right */}
        <motion.div
          animate={{ rotate: [0, 360] }}
          transition={{ duration: 90, repeat: Infinity, ease: "linear" }}
          style={{
            position: 'absolute',
            width: 260,
            height: 260,
            borderRadius: '50%',
            background: 'radial-gradient(circle at 30% 30%, #00f2fe 0%, #4facfe 40%, #02001a 100%)',
            bottom: -70,
            right: -50,
            boxShadow: '0 0 50px rgba(0, 242, 254, 0.35)',
            filter: 'blur(1px)'
          }}
        />
        {/* Glowing backdrop purple orb */}
        <motion.div
          animate={{ scale: [1, 1.15, 1], opacity: [0.2, 0.3, 0.2] }}
          transition={{ duration: 10, repeat: Infinity, ease: "easeInOut" }}
          style={{ position: 'absolute', width: 220, height: 220, borderRadius: '50%', background: '#7c3aed', top: -60, left: -60, filter: 'blur(60px)' }}
        />
      </div>
    );
  }

  if (t.id === 'tech-purple') {
    return (
      <div className="es-deco" aria-hidden>
        <div style={{ position: 'absolute', top: 28, left: 28, width: 36, height: 36, borderLeft: `2px solid ${t.accent}`, borderTop: `2px solid ${t.accent}`, opacity: 0.4 }} />
        <div style={{ position: 'absolute', bottom: 28, right: 28, width: 36, height: 36, borderRight: `2px solid ${t.primary}`, borderBottom: `2px solid ${t.primary}`, opacity: 0.4 }} />
        <motion.div
          animate={{ opacity: [0.2, 0.6, 0.2] }}
          transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
          style={{ position: 'absolute', top: 32, right: 32, width: 6, height: 6, background: t.accent, borderRadius: '50%' }}
        />
        <motion.div
          animate={{ opacity: [0.6, 0.2, 0.6] }}
          transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
          style={{ position: 'absolute', bottom: 32, left: 32, width: 6, height: 6, background: t.primary, borderRadius: '50%' }}
        />
      </div>
    );
  }

  if (t.id === 'nature-green') {
    return (
      <div className="es-deco" aria-hidden>
        <motion.div
          animate={{ scale: [1, 1.12, 1], rotate: [0, 6, 0] }}
          transition={{ duration: 12, repeat: Infinity, ease: "easeInOut" }}
          style={{ position: 'absolute', width: 220, height: 220, borderRadius: '60% 40% 50% 50% / 40% 55% 45% 60%', background: '#27ae60', top: -70, right: -70, filter: 'blur(50px)', opacity: 0.28 }}
        />
        <motion.div
          animate={{ scale: [1, 1.08, 1], rotate: [0, -6, 0] }}
          transition={{ duration: 15, repeat: Infinity, ease: "easeInOut" }}
          style={{ position: 'absolute', width: 160, height: 160, borderRadius: '40% 60% 40% 60% / 50% 40% 60% 50%', background: '#2ecc71', bottom: -50, left: -50, filter: 'blur(40px)', opacity: 0.22 }}
        />
      </div>
    );
  }

  // Fallback (modern-dark)
  return (
    <div className="es-deco" aria-hidden>
      <motion.div
        animate={{ scale: [1, 1.1, 1], y: [0, 10, 0] }}
        transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
        className="es-deco-c1"
        style={{ background: t.primary + '20' }}
      />
      <motion.div
        animate={{ scale: [1, 1.15, 1], x: [0, -10, 0] }}
        transition={{ duration: 10, repeat: Infinity, ease: "easeInOut" }}
        className="es-deco-c2"
        style={{ background: t.accent + '18' }}
      />
      <div className="es-deco-line" style={{ background: t.accentGrad }} />
    </div>
  );
}

// ─── Slide Types ──────────────────────────────────────────────────────────────

function TitleSlide({ slide, t, sk, onSave }) {
  return (
    <div className="es-slide es-title" style={{ background: t.bgGrad }}>
      <Deco t={t} />
      <div className="es-title-content">
        <div className="es-badge" style={{ color: t.primary, background: t.primary + '18', borderColor: t.primary + '44', fontFamily: t.fontTitle }}>
          ✦ Presentation
        </div>
        <InlineText value={slide.title} onSave={onSave} slideKey={sk} field="title"
          tag="h1" className="es-main-title" style={{ color: t.text, fontFamily: t.fontTitle }} placeholder="Tiêu đề chính" />
        <InlineText value={slide.subtitle} onSave={onSave} slideKey={sk} field="subtitle"
          className="es-subtitle" style={{ color: t.textSub, fontFamily: t.fontBody }} placeholder="Phụ đề..." />
        <div className="es-divider" style={{ background: t.accentGrad }} />
      </div>
    </div>
  );
}

// Helper: compute gap between bullet items based on count in editor
function bulletGap(count) {
  if (count <= 2) return 36;
  if (count <= 3) return 28;
  if (count <= 4) return 20;
  if (count <= 5) return 14;
  return 10;
}

// Content slide — default
function ContentSlide({ slide, t, sk, onSave }) {
  return (
    <div className="es-slide es-content" style={{ background: t.bgGrad }}>
      <Deco t={t} />
      <div className="es-content-inner">
        <div className="es-bar" style={{ background: t.accentGrad }} />
        <InlineText value={slide.title} onSave={onSave} slideKey={sk} field="title"
          tag="h2" className="es-section-title" style={{ color: t.text, fontFamily: t.fontTitle }} placeholder="Tiêu đề slide" />
        <div className="es-bullets-wrap">
          <InlineBullets bullets={slide.bullets} richValue={slide.richText?.bullets} onSave={onSave} slideKey={sk} t={t} />
        </div>
      </div>
    </div>
  );
}

// Content slide — SOFT-BLUE variant with numbered badge bullets
function SoftBlueContentSlide({ slide, t, sk, onSave }) {
  const count = slide.bullets?.length || 0;
  return (
    <div className="es-slide es-content" style={{ background: t.bgGrad, position: 'relative' }}>
      <Deco t={t} />
      <div style={{ position: 'absolute', left: 48, top: 48, width: 5, height: 40, borderRadius: 999, background: t.accentGrad }} />
      <div style={{ position: 'absolute', left: 64, top: 46, width: '87%', display: 'flex', flexDirection: 'column', gap: 28 }}>
        <InlineText value={slide.title} onSave={onSave} slideKey={sk} field="title"
          tag="h2" className="es-section-title"
          style={{ width: '100%', color: t.text, fontFamily: t.fontTitle, fontSize: 34, fontWeight: 700, lineHeight: 1.2 }}
          placeholder="Tiêu đề slide" />
        <div style={{ display: 'flex', flexDirection: 'column', gap: bulletGap(count) }}>
          <EditableBulletList bullets={slide.bullets} t={t} onSave={onSave}
            renderBulletIcon={(i) => (
              <div style={{ flexShrink: 0, width: 26, height: 26, borderRadius: '50%', background: t.accentGrad, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, fontWeight: 700, color: '#fff', fontFamily: t.fontTitle, marginTop: 2 }}>{String(i + 1).padStart(2, '0')}</div>
            )}
          />
        </div>
      </div>
    </div>
  );
}


// ─── Reusable inline-editable bullet helper ───────────────────────────────────
// Each bullet item is directly contentEditable for immediate editing
function EditableBulletList({ bullets, t, onSave, renderBulletIcon }) {
  const saveBullet = (i, text) => {
    const next = [...(bullets || [])];
    next[i] = text;
    onSave('bullets', next);
  };
  return (
    <>
      {(bullets || []).map((b, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
          {renderBulletIcon(i)}
          <span
            contentEditable
            suppressContentEditableWarning
            style={{ fontFamily: t.fontBody, fontSize: 16, color: t.textSub, lineHeight: 1.55, fontWeight: 400, outline: 'none', flex: 1 }}
            onBlur={(e) => saveBullet(i, e.currentTarget.innerText.trim())}
          >{b}</span>
        </div>
      ))}
    </>
  );
}

// ROYAL-PURPLE editable — gradient left-bordered cards
function RoyalPurpleContentSlide({ slide, t, sk, onSave }) {
  const count = slide.bullets?.length || 0;
  return (
    <div className="es-slide es-content" style={{ background: t.bgGrad, position: 'relative' }}>
      <Deco t={t} />
      <div style={{ position: 'absolute', left: 48, top: 48, width: 5, height: 44, borderRadius: 999, background: t.accentGrad }} />
      <div style={{ position: 'absolute', left: 64, top: 44, width: '87%', display: 'flex', flexDirection: 'column', gap: 28 }}>
        <InlineText value={slide.title} onSave={onSave} slideKey={sk} field="title"
          tag="h2" className="es-section-title"
          style={{ width: '100%', color: t.text, fontFamily: t.fontTitle, fontSize: 34, fontWeight: 700, lineHeight: 1.2 }}
          placeholder="Tiêu đề slide" />
        <div style={{ display: 'flex', flexDirection: 'column', gap: bulletGap(count) }}>
          <EditableBulletList bullets={slide.bullets} t={t} onSave={onSave}
            renderBulletIcon={(i) => (
              <span style={{ color: t.accent, fontWeight: 700, fontFamily: t.fontTitle, fontSize: 13, marginRight: 0, marginTop: 2, flexShrink: 0 }}>{String(i+1).padStart(2,'0')}.</span>
            )}
          />
        </div>
      </div>
    </div>
  );
}

// CLEAN-WHITE editable — numbered timeline with dividers
function CleanWhiteContentSlide({ slide, t, sk, onSave }) {
  const count = slide.bullets?.length || 0;
  const padV = count <= 3 ? 20 : count <= 5 ? 14 : 10;
  return (
    <div className="es-slide es-content" style={{ background: t.bgGrad, position: 'relative' }}>
      <Deco t={t} />
      <div style={{ position: 'absolute', left: 48, top: 48, width: 4, height: 40, borderRadius: 999, background: t.accentGrad }} />
      <div style={{ position: 'absolute', left: 64, top: 46, width: '87%', display: 'flex', flexDirection: 'column', gap: 28 }}>
        <InlineText value={slide.title} onSave={onSave} slideKey={sk} field="title"
          tag="h2" className="es-section-title"
          style={{ width: '100%', color: t.text, fontFamily: t.fontTitle, fontSize: 36, fontWeight: 400, lineHeight: 1.2, letterSpacing: '-0.3px' }}
          placeholder="Tiêu đề slide" />
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {(slide.bullets || []).map((b, i) => {
            const saveBullet = (e) => {
              const next = [...(slide.bullets || [])];
              next[i] = e.currentTarget.innerText.trim();
              onSave('bullets', next);
            };
            return (
              <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 20, padding: `${padV}px 0`, borderBottom: i < (count-1) ? '1px solid #e5e5e5' : 'none' }}>
                <span style={{ color: t.accent, fontFamily: t.fontTitle, fontWeight: 800, fontSize: 26, lineHeight: 1, minWidth: 36, paddingTop: 2 }}>{i+1}</span>
                <span contentEditable suppressContentEditableWarning style={{ fontFamily: t.fontBody, fontSize: 16, color: t.textSub, lineHeight: 1.6, outline: 'none', flex: 1 }} onBlur={saveBullet}>{b}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// MODERN-DARK editable — glassmorphism cards
function ModernDarkContentSlide({ slide, t, sk, onSave }) {
  const count = slide.bullets?.length || 0;
  return (
    <div className="es-slide es-content" style={{ background: t.bgGrad, position: 'relative' }}>
      <Deco t={t} />
      <div style={{ position: 'absolute', left: 48, top: 48, width: 5, height: 40, borderRadius: 999, background: t.accentGrad }} />
      <div style={{ position: 'absolute', left: 64, top: 44, width: '87%', display: 'flex', flexDirection: 'column', gap: 28 }}>
        <InlineText value={slide.title} onSave={onSave} slideKey={sk} field="title"
          tag="h2" className="es-section-title"
          style={{ width: '100%', color: t.text, fontFamily: t.fontTitle, fontSize: 34, fontWeight: 600, lineHeight: 1.2, letterSpacing: '-0.5px' }}
          placeholder="Tiêu đề slide" />
        <div style={{ display: 'flex', flexDirection: 'column', gap: bulletGap(count) }}>
          <EditableBulletList bullets={slide.bullets} t={t} onSave={onSave}
            renderBulletIcon={() => (
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: t.accentGrad, flexShrink: 0, marginTop: 7, display: 'block' }} />
            )}
          />
        </div>
      </div>
    </div>
  );
}

// PLAYFUL-YELLOW editable — colorful alternating badges
function PlayfulYellowContentSlide({ slide, t, sk, onSave }) {
  const colors = ['#f59e0b','#8b5cf6','#ef4444','#10b981','#3b82f6'];
  const count = slide.bullets?.length || 0;
  return (
    <div className="es-slide es-content" style={{ background: t.bgGrad, position: 'relative' }}>
      <Deco t={t} />
      <div style={{ position: 'absolute', left: 64, top: 44, width: '87%', display: 'flex', flexDirection: 'column', gap: 28 }}>
        <InlineText value={slide.title} onSave={onSave} slideKey={sk} field="title"
          tag="h2" className="es-section-title"
          style={{ width: '100%', color: t.text, fontFamily: t.fontTitle, fontSize: 38, fontWeight: 400, lineHeight: 1.2 }}
          placeholder="Tiêu đề slide" />
        <div style={{ display: 'flex', flexDirection: 'column', gap: bulletGap(count) }}>
          <EditableBulletList bullets={slide.bullets} t={t} onSave={onSave}
            renderBulletIcon={(i) => (
              <div style={{ flexShrink: 0, width: 28, height: 28, borderRadius: '50%', background: colors[i % colors.length], display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, fontWeight: 700, color: '#fff', fontFamily: t.fontTitle, marginTop: 2 }}>{i+1}</div>
            )}
          />
        </div>
      </div>
    </div>
  );
}

// GRADIENT-BORDER editable — left bar + tinted rows
function GradientBorderContentSlide({ slide, t, sk, onSave }) {
  const count = slide.bullets?.length || 0;
  return (
    <div className="es-slide es-content" style={{ background: t.bgGrad, position: 'relative' }}>
      <Deco t={t} />
      <div style={{ position: 'absolute', left: 64, top: 44, width: '87%', display: 'flex', flexDirection: 'column', gap: 28 }}>
        <InlineText value={slide.title} onSave={onSave} slideKey={sk} field="title"
          tag="h2" className="es-section-title"
          style={{ width: '100%', color: t.text, fontFamily: t.fontTitle, fontSize: 34, fontWeight: 700, lineHeight: 1.2 }}
          placeholder="Tiêu đề slide" />
        <div style={{ display: 'flex', flexDirection: 'column', gap: bulletGap(count) }}>
          {(slide.bullets || []).map((b, i) => {
            const saveBullet = (e) => {
              const next = [...(slide.bullets || [])];
              next[i] = e.currentTarget.innerText.trim();
              onSave('bullets', next);
            };
            return (
              <div key={i} style={{ display: 'flex', alignItems: 'stretch', background: i%2===0 ? 'rgba(108,99,255,0.05)' : 'rgba(56,189,248,0.04)', borderRadius: '0 10px 10px 0', overflow: 'hidden' }}>
                <div style={{ width: 4, flexShrink: 0, background: t.accentGrad }} />
                <span contentEditable suppressContentEditableWarning style={{ fontFamily: t.fontBody, fontSize: 16, color: t.textSub, lineHeight: 1.5, padding: '12px 16px', outline: 'none', flex: 1 }} onBlur={saveBullet}>{b}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// BLUE-PLANET editable — cyan glowing dots
function BluePlanetContentSlide({ slide, t, sk, onSave }) {
  const count = slide.bullets?.length || 0;
  return (
    <div className="es-slide es-content" style={{ background: t.bgGrad, position: 'relative' }}>
      <Deco t={t} />
      <div style={{ position: 'absolute', left: 48, top: 48, width: 5, height: 40, borderRadius: 999, background: t.accentGrad }} />
      <div style={{ position: 'absolute', left: 64, top: 44, width: '65%', display: 'flex', flexDirection: 'column', gap: 28 }}>
        <InlineText value={slide.title} onSave={onSave} slideKey={sk} field="title"
          tag="h2" className="es-section-title"
          style={{ width: '100%', color: t.text, fontFamily: t.fontTitle, fontSize: 32, fontWeight: 600, lineHeight: 1.2, letterSpacing: '0.5px' }}
          placeholder="Tiêu đề slide" />
        <div style={{ display: 'flex', flexDirection: 'column', gap: bulletGap(count) }}>
          <EditableBulletList bullets={slide.bullets} t={t} onSave={onSave}
            renderBulletIcon={() => (
              <div style={{ flexShrink: 0, width: 10, height: 10, borderRadius: '50%', background: t.accentGrad, boxShadow: `0 0 8px ${t.primary}88`, marginTop: 7 }} />
            )}
          />
        </div>
      </div>
    </div>
  );
}

// NATURE-GREEN editable — leaf-shaped bullets
function NatureGreenContentSlide({ slide, t, sk, onSave }) {
  const count = slide.bullets?.length || 0;
  return (
    <div className="es-slide es-content" style={{ background: t.bgGrad, position: 'relative' }}>
      <Deco t={t} />
      <div style={{ position: 'absolute', left: 48, top: 48, width: 5, height: 40, borderRadius: '0 999px 999px 0', background: t.accentGrad }} />
      <div style={{ position: 'absolute', left: 64, top: 44, width: '87%', display: 'flex', flexDirection: 'column', gap: 28 }}>
        <InlineText value={slide.title} onSave={onSave} slideKey={sk} field="title"
          tag="h2" className="es-section-title"
          style={{ width: '100%', color: t.text, fontFamily: t.fontTitle, fontSize: 32, fontWeight: 700, lineHeight: 1.25 }}
          placeholder="Tiêu đề slide" />
        <div style={{ display: 'flex', flexDirection: 'column', gap: bulletGap(count) }}>
          <EditableBulletList bullets={slide.bullets} t={t} onSave={onSave}
            renderBulletIcon={() => (
              <div style={{ flexShrink: 0, width: 12, height: 12, background: t.accentGrad, borderRadius: '50% 0 50% 0', transform: 'rotate(-15deg)', marginTop: 6 }} />
            )}
          />
        </div>
      </div>
    </div>
  );
}

// TECH-PURPLE editable — 2-column grid with square dots
function TechPurpleContentSlide({ slide, t, sk, onSave }) {
  const bullets = slide.bullets || [];
  const half = Math.ceil(bullets.length / 2);
  const cols = [bullets.slice(0, half), bullets.slice(half)];
  const rowGap = bulletGap(Math.max(cols[0].length, cols[1].length));
  const saveBullet = (colIdx, rowIdx, text) => {
    const next = [...bullets];
    const absoluteIdx = colIdx === 0 ? rowIdx : half + rowIdx;
    next[absoluteIdx] = text;
    onSave('bullets', next);
  };
  return (
    <div className="es-slide es-content" style={{ background: t.bgGrad, position: 'relative' }}>
      <Deco t={t} />
      <div style={{ position: 'absolute', left: 48, top: 48, width: 4, height: 40, background: t.accentGrad }} />
      <div style={{ position: 'absolute', left: 64, top: 44, width: '87%', display: 'flex', flexDirection: 'column', gap: 28 }}>
        <InlineText value={slide.title} onSave={onSave} slideKey={sk} field="title"
          tag="h2" className="es-section-title"
          style={{ width: '100%', color: t.text, fontFamily: t.fontTitle, fontSize: 34, fontWeight: 700, lineHeight: 1.2, letterSpacing: '1px', textTransform: 'uppercase' }}
          placeholder="Tiêu đề slide" />
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: `0 40px` }}>
          {cols.map((col, ci) => (
            <div key={ci} style={{ display: 'flex', flexDirection: 'column', gap: rowGap }}>
              {col.map((b, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                  <div style={{ flexShrink: 0, width: 8, height: 8, background: t.accentGrad, marginTop: 7 }} />
                  <span contentEditable suppressContentEditableWarning style={{ fontFamily: t.fontBody, fontSize: 15.5, color: t.textSub, lineHeight: 1.5, outline: 'none', flex: 1 }} onBlur={(e) => saveBullet(ci, i, e.currentTarget.innerText.trim())}>{b}</span>
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// Two column slide
function TwoColumnSlide({ slide, t, sk, onSave }) {
  const saveLeft = (f, v) => onSave('left', { ...slide.left, [f]: v });
  const saveRight = (f, v) => onSave('right', { ...slide.right, [f]: v });
  const saveLeftPoints = (pts) => onSave('left', { ...slide.left, points: pts });
  const saveRightPoints = (pts) => onSave('right', { ...slide.right, points: pts });

  return (
    <div className="es-slide es-twocol" style={{ background: t.bgGrad }}>
      <Deco t={t} />
      <div className="es-content-inner">
        <div className="es-bar" style={{ background: t.accentGrad }} />
        <InlineText value={slide.title} onSave={onSave} slideKey={sk} field="title"
          tag="h2" className="es-section-title" style={{ color: t.text, fontFamily: t.fontTitle }} placeholder="Tiêu đề" />
        <div className="es-cols">
          {[
            { side: 'left', colData: slide.left, saveH: (v) => saveLeft('heading', v), saveP: saveLeftPoints },
            { side: 'right', colData: slide.right, saveH: (v) => saveRight('heading', v), saveP: saveRightPoints },
          ].map(({ side, colData, saveH, saveP }) => (
            <div key={side} className="es-col-card" style={{ background: t.surface, borderColor: t.surfaceBorder }}>
              <InlineText value={colData?.heading} onSave={(_, v) => saveH(v)} slideKey={sk} field={`${side}-h`}
                className="es-col-heading" style={{ color: t.primary, fontFamily: t.fontTitle }} placeholder="Tiêu đề cột" />
              <div
                key={`${sk}__${side}-pts`}
                className="es-editable es-col-points"
                contentEditable suppressContentEditableWarning
                data-placeholder="Mỗi dòng một điểm..."
                onBlur={(e) => saveP(e.currentTarget.innerText.split('\n').filter((l) => l.trim()))}
                dangerouslySetInnerHTML={{ __html: (colData?.points || []).join('<br>') }}
                style={{ color: t.textSub, fontFamily: t.fontBody }}
              />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// Image + Text slide
function ImageTextSlide({ slide, t, sk, onSave }) {
  return (
    <div className="es-slide es-imgtext" style={{ background: t.bgGrad }}>
      <Deco t={t} />
      <div className="es-imgtext-inner">
        <div className="es-img-box" style={{ background: t.surface, borderColor: t.surfaceBorder, overflow: 'hidden', padding: 0 }}>
          {slide.imageUrl ? (
            <img src={resolveAssetUrl(slide.imageUrl)} alt={slide.title} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
          ) : (
            <>
              <InlineText value={slide.imageEmoji || '🖼️'} onSave={onSave} slideKey={sk} field="imageEmoji"
                className="es-emoji" style={{}} placeholder="🖼️" />
              <div className="es-img-hint" style={{ color: t.textSub, fontFamily: t.fontBody }}>Click để đổi emoji</div>
            </>
          )}
        </div>
        <div className="es-imgtext-content">
          <div className="es-bar" style={{ background: t.accentGrad }} />
          <InlineText value={slide.title} onSave={onSave} slideKey={sk} field="title"
            tag="h2" className="es-section-title" style={{ color: t.text, fontFamily: t.fontTitle }} placeholder="Tiêu đề" />
          <InlineText value={slide.text} onSave={onSave} slideKey={sk} field="text"
            className="es-body-text" style={{ color: t.textSub, fontFamily: t.fontBody }} placeholder="Nội dung mô tả..." />
        </div>
      </div>
    </div>
  );
}

function StructuredSlide({ slide, t, sk, onSave }) {
  return (
    <div className="es-slide es-content" style={{ background: t.bgGrad }}>
      <Deco t={t} />
      <div className="es-content-inner" style={{ gap: 18 }}>
        <div className="es-bar" style={{ background: t.accentGrad }} />
        <InlineText value={slide.title} onSave={onSave} slideKey={sk} field="title"
          tag="h2" className="es-section-title" style={{ color: t.text, fontFamily: t.fontTitle }} placeholder="Tiêu đề" />
        <div style={{ flex: 1, minHeight: 0, padding: '0 2px' }}>
          {slide.type === 'table'
            ? <TableVisual table={slide.table} theme={t} />
            : <ChartVisual chart={slide.chart} theme={t} />}
        </div>
      </div>
    </div>
  );
}

// Quote slide
function QuoteSlide({ slide, t, sk, onSave }) {
  return (
    <div className="es-slide es-quote" style={{ background: t.bgGrad }}>
      <Deco t={t} />
      <div className="es-quote-inner">
        <div className="es-quote-mark" style={{ ...getGradStyle(t.accentGrad), fontFamily: t.fontTitle }}>"</div>
        <InlineText value={slide.quote} onSave={onSave} slideKey={sk} field="quote"
          tag="blockquote" className="es-quote-text" style={{ color: t.text, fontFamily: t.fontTitle }} placeholder="Nhập trích dẫn..." />
        <div className="es-quote-divider" style={{ background: t.accentGrad }} />
        <InlineText value={slide.author} onSave={onSave} slideKey={sk} field="author"
          className="es-quote-author" style={{ color: t.primary, fontFamily: t.fontTitle }} placeholder="Tên tác giả" />
        <InlineText value={slide.role} onSave={onSave} slideKey={sk} field="role"
          className="es-quote-role" style={{ color: t.textSub, fontFamily: t.fontBody }} placeholder="Chức danh" />
      </div>
    </div>
  );
}

// Thank you slide
function ThankYouSlide({ slide, t, sk, onSave }) {
  return (
    <div className="es-slide es-thankyou" style={{ background: t.bgGrad }}>
      <Deco t={t} />
      <div className="es-ty-content">
        <div className="slide-ty-icon" style={{ background: t.primary + '18', borderColor: t.primary + '44', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '28px', width: '68px', height: '68px', borderRadius: '50%', marginBottom: 12 }}>🎉</div>
        <InlineText value={slide.title} onSave={onSave} slideKey={sk} field="title"
          tag="h1" className="es-main-title" style={{ color: t.text, fontFamily: t.fontTitle }} placeholder="Tiêu đề" />
        <InlineText value={slide.subtitle} onSave={onSave} slideKey={sk} field="subtitle"
          className="es-subtitle" style={{ color: t.textSub, fontFamily: t.fontBody }} placeholder="Phụ đề..." />
        <InlineText value={slide.contact} onSave={onSave} slideKey={sk} field="contact"
          className="es-ty-contact" style={{ color: t.primary, background: t.surface, borderColor: t.surfaceBorder, fontFamily: t.fontBody }}
          placeholder="Email liên hệ" />
        <div className="es-divider" style={{ background: t.accentGrad }} />
      </div>
    </div>
  );
}

function getGradStyle(grad) {
  return { background: grad, WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text' };
}

// ─── Main export ─────────────────────────────────────────────────────────────
const SLIDE_MAP = { title: TitleSlide, content: ContentSlide, twoColumn: TwoColumnSlide, imageText: ImageTextSlide, table: StructuredSlide, chart: StructuredSlide, quote: QuoteSlide, thankyou: ThankYouSlide };

export default function EditableSlide({ slide, theme = 'clean-white', slideIndex = 0, onUpdate }) {
  const t = THEMES[theme] || THEMES['clean-white'];
  const sk = `${slideIndex}`;
  let Component = SLIDE_MAP[slide?.type] || ContentSlide;
  const contentVariants = {
    'soft-blue': SoftBlueContentSlide,
    'royal-purple': RoyalPurpleContentSlide,
    'clean-white': CleanWhiteContentSlide,
    'modern-dark': ModernDarkContentSlide,
    'playful-yellow': PlayfulYellowContentSlide,
    'gradient-border': GradientBorderContentSlide,
    'blue-planet': BluePlanetContentSlide,
    'nature-green': NatureGreenContentSlide,
    'tech-purple': TechPurpleContentSlide,
  };
  if (slide?.type === 'content' && contentVariants[theme]) Component = contentVariants[theme];

  const handleSave = (field, value, html) => {
    const existingHtml = slide.richText?.[field];
    if (value === slide[field] && (html === undefined || html === existingHtml)) return;
    const richText = html === undefined
      ? slide.richText
      : { ...(slide.richText || {}), [field]: html };
    onUpdate?.({ ...slide, [field]: value, richText });
  };

  const richFields = { ...(slide.richText || {}) };
  delete richFields.bullets;
  const displaySlide = { ...slide, ...richFields };

  return (
    <div className="editable-slide-root" data-theme={theme}>
      <Component slide={displaySlide} t={t} sk={sk} onSave={handleSave} />
      <div className="es-slide-number" style={{ color: t.textSub }}>
        {String(slideIndex + 1).padStart(2, '0')}
      </div>
    </div>
  );
}
