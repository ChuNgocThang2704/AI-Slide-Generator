import { useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { TiptapInlineEditor } from './TiptapEditor';
import './EditableSlide.css';
import { ChartVisual, TableVisual } from './StructuredVisual';
import './StructuredVisual.css';
import { resolveAssetUrl } from '../../utils/assetUrl';
import { documentService } from '../../services/documentService';
import AssetImage from './AssetImage';
import { fitTextToBox } from '../../utils/textFit';
import { inferImageFit } from '../../utils/imageFit';

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
function plainTextLength(value) {
  if (!value) return 0;
  const tmp = document.createElement('div');
  tmp.innerHTML = String(value);
  return (tmp.innerText || tmp.textContent || '').trim().length;
}

function adaptiveTextStyle(value, className, style) {
  const length = plainTextLength(value);
  if (className.includes('es-main-title')) {
    return { ...style, fontSize: length > 90 ? 34 : length > 60 ? 40 : style.fontSize };
  }
  if (className.includes('es-section-title')) {
    return { ...style, fontSize: length > 110 ? 22 : length > 75 ? 26 : length > 48 ? 30 : style.fontSize };
  }
  if (className.includes('es-body-text')) {
    return { ...style, fontSize: length > 700 ? 11 : length > 500 ? 12 : length > 320 ? 13 : style.fontSize };
  }
  if (className.includes('es-quote-text')) {
    return { ...style, fontSize: length > 320 ? 15 : length > 220 ? 17 : style.fontSize };
  }
  return style;
}

function InlineText({ value, richValue = '', onSave, slideKey, field, className = '', style = {}, placeholder = '' }) {
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
      value={richValue || value || ''}
      onSave={handleSave}
      className={`es-editable ${className}`}
      style={adaptiveTextStyle(richValue || value, className, style)}
      placeholder={placeholder}
      autoFit={className.includes('es-body-text') || className.includes('es-quote-text')}
      minFontSize={className.includes('es-body-text') ? 11.5 : 12}
    />
  );
}

// Bullets (Tiptap with BulletList support)
function InlineBullets({ bullets = [], richValue = '', onSave, slideKey, t }) {
  // Convert bullet array → HTML list for Tiptap
  const initialHTML = richValue || (bullets.length
    ? `<ul>${bullets.map((b) => `<li>${b}</li>`).join('')}</ul>`
    : '');
  const estimatedLines = bullets.reduce(
    (sum, bullet) => sum + Math.max(1, Math.ceil(plainTextLength(bullet) / 82)),
    0,
  );
  const gap = estimatedLines > 16 ? 3 : estimatedLines > 12 ? 6 : estimatedLines > 9 ? 10 : 14;
  const boxHeight = estimatedLines > 14 ? 380 : estimatedLines > 9 ? 365 : bullets.length >= 4 ? 340 : 270;
  const fontSize = fitTextToBox(initialHTML, {
    width: 820,
    height: boxHeight,
    min: 10,
    max: 22,
    lineHeight: 1.5,
    itemCount: bullets.length,
  });

  const handleSave = (html) => {
    // Parse HTML back to array of plain text lines
    const tmp = document.createElement('div');
    tmp.innerHTML = html;
    tmp.querySelectorAll('li').forEach((item) => {
      if (!item.innerText?.trim()) item.remove();
    });
    const lines = [];
    const items = tmp.querySelectorAll('li').length
      ? tmp.querySelectorAll('li')
      : tmp.querySelectorAll('p');
    items.forEach((el) => {
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
      className="es-editable es-bullets-editable es-themed-bullets"
      style={{
        color: t.textSub,
        fontFamily: t.fontBody,
        fontSize,
        '--bullet-gap': `${gap}px`,
        '--bullet-box-height': `${boxHeight}px`,
      }}
      autoFit
      minFontSize={8}
      autoFitBaseFontSize={fontSize}
      placeholder="Nhập bullet points, mỗi dòng một ý..."
    />
  );
}

function InlinePointList({ points = [], richValue = '', onSave, slideKey, field, t }) {
  const initialHTML = richValue || (points.length
    ? `<ul>${points.map((point) => `<li>${point}</li>`).join('')}</ul>`
    : '');
  const totalChars = points.reduce((sum, point) => sum + plainTextLength(point), 0);
  const fontSize = points.length > 6 || totalChars > 420
    ? 10.5
    : points.length > 4 || totalChars > 280
      ? 11.5
      : 13;

  const handleSave = (html) => {
    const tmp = document.createElement('div');
    tmp.innerHTML = html;
    const items = tmp.querySelectorAll('li').length
      ? tmp.querySelectorAll('li')
      : tmp.querySelectorAll('p');
    const nextPoints = [...items]
      .map((item) => item.innerText?.trim())
      .filter(Boolean);
    if (!nextPoints.length) {
      tmp.innerText.split('\n').map((line) => line.trim()).filter(Boolean).forEach((line) => nextPoints.push(line));
    }
    onSave(nextPoints, tmp.innerHTML);
  };

  return (
    <TiptapInlineEditor
      key={`${slideKey}__${field}`}
      value={initialHTML}
      onSave={handleSave}
      className="es-editable es-col-points es-point-list"
      style={{ color: t.textSub, fontFamily: t.fontBody, fontSize }}
      autoFit
      minFontSize={8}
      autoFitBaseFontSize={fontSize}
      placeholder="Mỗi dòng một ý..."
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
  return (
    <div className="es-slide es-content" style={{ background: t.bgGrad, position: 'relative' }}>
      <Deco t={t} />
      <div style={{ position: 'absolute', left: 48, top: 48, width: 5, height: 40, borderRadius: 999, background: t.accentGrad }} />
      <div style={{ position: 'absolute', left: 64, top: 46, width: '87%', display: 'flex', flexDirection: 'column', gap: 28 }}>
        <InlineText value={slide.title} onSave={onSave} slideKey={sk} field="title"
          tag="h2" className="es-section-title"
          style={{ width: '100%', color: t.text, fontFamily: t.fontTitle, fontSize: 34, fontWeight: 700, lineHeight: 1.2 }}
          placeholder="Tiêu đề slide" />
        <InlineBullets bullets={slide.bullets} richValue={slide.richText?.bullets} onSave={onSave} slideKey={sk} t={t} />
      </div>
    </div>
  );
}


// ─── Reusable inline-editable bullet helper ───────────────────────────────────
// ROYAL-PURPLE editable — gradient left-bordered cards
function RoyalPurpleContentSlide({ slide, t, sk, onSave }) {
  return (
    <div className="es-slide es-content" style={{ background: t.bgGrad, position: 'relative' }}>
      <Deco t={t} />
      <div style={{ position: 'absolute', left: 48, top: 48, width: 5, height: 44, borderRadius: 999, background: t.accentGrad }} />
      <div style={{ position: 'absolute', left: 64, top: 44, width: '87%', display: 'flex', flexDirection: 'column', gap: 28 }}>
        <InlineText value={slide.title} onSave={onSave} slideKey={sk} field="title"
          tag="h2" className="es-section-title"
          style={{ width: '100%', color: t.text, fontFamily: t.fontTitle, fontSize: 34, fontWeight: 700, lineHeight: 1.2 }}
          placeholder="Tiêu đề slide" />
        <InlineBullets bullets={slide.bullets} richValue={slide.richText?.bullets} onSave={onSave} slideKey={sk} t={t} />
      </div>
    </div>
  );
}

// CLEAN-WHITE editable — numbered timeline with dividers
function CleanWhiteContentSlide({ slide, t, sk, onSave }) {
  return (
    <div className="es-slide es-content" style={{ background: t.bgGrad, position: 'relative' }}>
      <Deco t={t} />
      <div style={{ position: 'absolute', left: 48, top: 48, width: 4, height: 40, borderRadius: 999, background: t.accentGrad }} />
      <div style={{ position: 'absolute', left: 64, top: 46, width: '87%', display: 'flex', flexDirection: 'column', gap: 28 }}>
        <InlineText value={slide.title} onSave={onSave} slideKey={sk} field="title"
          tag="h2" className="es-section-title"
          style={{ width: '100%', color: t.text, fontFamily: t.fontTitle, fontSize: 36, fontWeight: 400, lineHeight: 1.2, letterSpacing: '-0.3px' }}
          placeholder="Tiêu đề slide" />
        <InlineBullets bullets={slide.bullets} richValue={slide.richText?.bullets} onSave={onSave} slideKey={sk} t={t} />
      </div>
    </div>
  );
}

// MODERN-DARK editable — glassmorphism cards
function ModernDarkContentSlide({ slide, t, sk, onSave }) {
  return (
    <div className="es-slide es-content" style={{ background: t.bgGrad, position: 'relative' }}>
      <Deco t={t} />
      <div style={{ position: 'absolute', left: 48, top: 48, width: 5, height: 40, borderRadius: 999, background: t.accentGrad }} />
      <div style={{ position: 'absolute', left: 64, top: 44, width: '87%', display: 'flex', flexDirection: 'column', gap: 28 }}>
        <InlineText value={slide.title} onSave={onSave} slideKey={sk} field="title"
          tag="h2" className="es-section-title"
          style={{ width: '100%', color: t.text, fontFamily: t.fontTitle, fontSize: 34, fontWeight: 600, lineHeight: 1.2, letterSpacing: '-0.5px' }}
          placeholder="Tiêu đề slide" />
        <InlineBullets bullets={slide.bullets} richValue={slide.richText?.bullets} onSave={onSave} slideKey={sk} t={t} />
      </div>
    </div>
  );
}

// PLAYFUL-YELLOW editable — colorful alternating badges
function PlayfulYellowContentSlide({ slide, t, sk, onSave }) {
  return (
    <div className="es-slide es-content" style={{ background: t.bgGrad, position: 'relative' }}>
      <Deco t={t} />
      <div style={{ position: 'absolute', left: 64, top: 44, width: '87%', display: 'flex', flexDirection: 'column', gap: 28 }}>
        <InlineText value={slide.title} onSave={onSave} slideKey={sk} field="title"
          tag="h2" className="es-section-title"
          style={{ width: '100%', color: t.text, fontFamily: t.fontTitle, fontSize: 38, fontWeight: 400, lineHeight: 1.2 }}
          placeholder="Tiêu đề slide" />
        <InlineBullets bullets={slide.bullets} richValue={slide.richText?.bullets} onSave={onSave} slideKey={sk} t={t} />
      </div>
    </div>
  );
}

// GRADIENT-BORDER editable — left bar + tinted rows
function GradientBorderContentSlide({ slide, t, sk, onSave }) {
  return (
    <div className="es-slide es-content" style={{ background: t.bgGrad, position: 'relative' }}>
      <Deco t={t} />
      <div style={{ position: 'absolute', left: 64, top: 44, width: '87%', display: 'flex', flexDirection: 'column', gap: 28 }}>
        <InlineText value={slide.title} onSave={onSave} slideKey={sk} field="title"
          tag="h2" className="es-section-title"
          style={{ width: '100%', color: t.text, fontFamily: t.fontTitle, fontSize: 34, fontWeight: 700, lineHeight: 1.2 }}
          placeholder="Tiêu đề slide" />
        <InlineBullets bullets={slide.bullets} richValue={slide.richText?.bullets} onSave={onSave} slideKey={sk} t={t} />
      </div>
    </div>
  );
}

// BLUE-PLANET editable — cyan glowing dots
function BluePlanetContentSlide({ slide, t, sk, onSave }) {
  return (
    <div className="es-slide es-content" style={{ background: t.bgGrad, position: 'relative' }}>
      <Deco t={t} />
      <div style={{ position: 'absolute', left: 48, top: 48, width: 5, height: 40, borderRadius: 999, background: t.accentGrad }} />
      <div style={{ position: 'absolute', left: 64, top: 44, width: '65%', display: 'flex', flexDirection: 'column', gap: 28 }}>
        <InlineText value={slide.title} onSave={onSave} slideKey={sk} field="title"
          tag="h2" className="es-section-title"
          style={{ width: '100%', color: t.text, fontFamily: t.fontTitle, fontSize: 32, fontWeight: 600, lineHeight: 1.2, letterSpacing: '0.5px' }}
          placeholder="Tiêu đề slide" />
        <InlineBullets bullets={slide.bullets} richValue={slide.richText?.bullets} onSave={onSave} slideKey={sk} t={t} />
      </div>
    </div>
  );
}

// NATURE-GREEN editable — leaf-shaped bullets
function NatureGreenContentSlide({ slide, t, sk, onSave }) {
  return (
    <div className="es-slide es-content" style={{ background: t.bgGrad, position: 'relative' }}>
      <Deco t={t} />
      <div style={{ position: 'absolute', left: 48, top: 48, width: 5, height: 40, borderRadius: '0 999px 999px 0', background: t.accentGrad }} />
      <div style={{ position: 'absolute', left: 64, top: 44, width: '87%', display: 'flex', flexDirection: 'column', gap: 28 }}>
        <InlineText value={slide.title} onSave={onSave} slideKey={sk} field="title"
          tag="h2" className="es-section-title"
          style={{ width: '100%', color: t.text, fontFamily: t.fontTitle, fontSize: 32, fontWeight: 700, lineHeight: 1.25 }}
          placeholder="Tiêu đề slide" />
        <InlineBullets bullets={slide.bullets} richValue={slide.richText?.bullets} onSave={onSave} slideKey={sk} t={t} />
      </div>
    </div>
  );
}

// TECH-PURPLE editable — 2-column grid with square dots
function TechPurpleContentSlide({ slide, t, sk, onSave }) {
  return (
    <div className="es-slide es-content" style={{ background: t.bgGrad, position: 'relative' }}>
      <Deco t={t} />
      <div style={{ position: 'absolute', left: 48, top: 48, width: 4, height: 40, background: t.accentGrad }} />
      <div style={{ position: 'absolute', left: 64, top: 44, width: '87%', display: 'flex', flexDirection: 'column', gap: 28 }}>
        <InlineText value={slide.title} onSave={onSave} slideKey={sk} field="title"
          tag="h2" className="es-section-title"
          style={{ width: '100%', color: t.text, fontFamily: t.fontTitle, fontSize: 34, fontWeight: 700, lineHeight: 1.2, letterSpacing: '1px', textTransform: 'uppercase' }}
          placeholder="Tiêu đề slide" />
        <InlineBullets bullets={slide.bullets} richValue={slide.richText?.bullets} onSave={onSave} slideKey={sk} t={t} />
      </div>
    </div>
  );
}

// Two column slide
function TwoColumnSlide({ slide, t, sk, onSave }) {
  return (
    <div className="es-slide es-twocol" style={{ background: t.bgGrad }}>
      <Deco t={t} />
      <div className="es-content-inner">
        <div className="es-bar" style={{ background: t.accentGrad }} />
        <InlineText value={slide.title} onSave={onSave} slideKey={sk} field="title"
          tag="h2" className="es-section-title" style={{ color: t.text, fontFamily: t.fontTitle }} placeholder="Tiêu đề" />
        <div className="es-cols">
          {[
            { side: 'left', colData: slide.left },
            { side: 'right', colData: slide.right },
          ].map(({ side, colData }) => (
            <div key={side} className="es-col-card" style={{ background: t.surface, borderColor: t.surfaceBorder }}>
              <InlineText
                value={colData?.heading}
                richValue={slide.richText?.[`${side}Heading`]}
                onSave={(_, value, html) => onSave(side, { ...colData, heading: value }, html, `${side}Heading`)}
                slideKey={sk}
                field={`${side}-h`}
                className="es-col-heading" style={{ color: t.primary, fontFamily: t.fontTitle }} placeholder="Tiêu đề cột" />
              <InlinePointList
                points={colData?.points}
                richValue={slide.richText?.[`${side}Points`]}
                slideKey={sk}
                field={`${side}-points`}
                t={t}
                onSave={(points, html) => onSave(side, { ...colData, points }, html, `${side}Points`)}
              />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// Image + Text slide
function ImageTextSlide({ slide, t, sk, onSave, readonly, onPickImage, imageFit = 'cover', uploadingImage }) {
  const textLength = plainTextLength(slide.text);
  const titleLength = plainTextLength(slide.title);
  const density = textLength > 980
    ? 'density-extreme'
    : textLength > 520 || titleLength > 78
      ? 'density-dense'
      : 'density-normal';
  const contentWidth = density === 'density-extreme' ? 530 : density === 'density-dense' ? 470 : 390;
  const bodyFontSize = fitTextToBox(slide.text, {
    width: contentWidth,
    height: density === 'density-extreme' ? 390 : 350,
    min: 11.5,
    max: 21,
    lineHeight: density === 'density-normal' ? 1.6 : 1.45,
    itemCount: Math.max(1, String(slide.text || '').split(/\n+/).filter(Boolean).length),
  });
  const titleFontSize = fitTextToBox(slide.title, {
    width: contentWidth,
    height: density === 'density-normal' ? 92 : 76,
    min: 23,
    max: 35,
    lineHeight: 1.15,
    padding: 0,
  });
  return (
    <div
      className={`es-slide es-imgtext ${density}`}
      style={{
        background: t.bgGrad,
        '--image-body-font-size': `${bodyFontSize}px`,
        '--image-title-font-size': `${titleFontSize}px`,
      }}
    >
      <Deco t={t} />
      <div className="es-imgtext-inner">
        <div className="es-img-box" style={{ background: t.surface, borderColor: t.surfaceBorder, overflow: 'hidden', padding: 0 }}>
          {slide.imageUrl ? (
            <AssetImage
              src={resolveAssetUrl(slide.imageUrl)}
              storageUrl={slide.imageStorageUrl}
              assetId={slide.imageAssetId}
              alt={slide.title}
              style={{ width: '100%', height: '100%', objectFit: imageFit, borderRadius: 'inherit' }}
            />
          ) : (
            <>
              <InlineText value={slide.imageEmoji || '🖼️'} onSave={onSave} slideKey={sk} field="imageEmoji"
                className="es-emoji" style={{}} placeholder="🖼️" />
              <div className="es-img-hint" style={{ color: t.textSub, fontFamily: t.fontBody }}>Click để đổi emoji</div>
            </>
          )}
          {!readonly && (
            <div className="es-image-actions">
              <button type="button" onClick={(event) => { event.stopPropagation(); onPickImage?.(); }}>
                {uploadingImage ? 'Đang tải...' : 'Thay ảnh'}
              </button>
              <button type="button" onClick={(event) => {
                event.stopPropagation();
                const nextFit = imageFit === 'cover' ? 'contain' : 'cover';
                onSave('imageFit', nextFit, nextFit, 'imageFit');
              }}>
                {imageFit === 'cover' ? 'Vừa khung' : 'Phủ khung'}
              </button>
            </div>
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
  const itemCount = slide.type === 'table'
    ? Math.max(slide.table?.headers?.length || 0, slide.table?.rows?.length || 0)
    : Math.max(slide.chart?.labels?.length || slide.chart?.categories?.length || 0, slide.chart?.series?.length || 0);
  const density = itemCount >= 8 ? 'density-extreme' : itemCount >= 6 ? 'density-dense' : 'density-normal';
  return (
    <div className={`es-slide es-content es-structured ${density}`} style={{ background: t.bgGrad }}>
      <Deco t={t} />
      <div className="es-content-inner" style={{ gap: 18 }}>
        <div className="es-bar" style={{ background: t.accentGrad }} />
        <InlineText value={slide.title} onSave={onSave} slideKey={sk} field="title"
          tag="h2" className="es-section-title" style={{ color: t.text, fontFamily: t.fontTitle }} placeholder="Tiêu đề" />
        <div style={{ flex: 1, minHeight: 0, padding: '0 2px' }}>
          {slide.type === 'table'
            ? <TableVisual table={slide.table} theme={t} onChange={(table) => onSave('table', table)} />
            : <ChartVisual chart={slide.chart} theme={t} onChange={(chart) => onSave('chart', chart)} />}
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

export default function EditableSlide({ slide, theme = 'clean-white', slideIndex = 0, onUpdate, onNotify, readonly = false }) {
  const imageInputRef = useRef(null);
  const [uploadingImage, setUploadingImage] = useState(false);
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

  const handleSave = (field, value, html, richKey = field) => {
    const existingHtml = slide.richText?.[richKey];
    if (value === slide[field] && (html === undefined || html === existingHtml)) return;
    const richText = html === undefined
      ? slide.richText
      : { ...(slide.richText || {}), [richKey]: html };
    onUpdate?.({ ...slide, [field]: value, richText });
  };

  const handleImageUpload = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    if (!file.type.startsWith('image/')) {
      onNotify?.('Vui lòng chọn ảnh PNG, JPEG, WebP hoặc GIF', 'warning');
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      onNotify?.('Ảnh không được vượt quá 10 MB', 'warning');
      return;
    }
    setUploadingImage(true);
    try {
      const uploaded = await documentService.upload(file);
      const imageUrl = uploaded?.viewUrl || uploaded?.url;
      if (!imageUrl) throw new Error('Máy chủ không trả về URL ảnh');
      onUpdate?.({
        ...slide,
        imageUrl,
        richText: {
          ...(slide.richText || {}),
          imageStorageUrl: uploaded?.url || '',
          imageAssetId: uploaded?.id || '',
        },
      });
      onNotify?.('Đã thay ảnh', 'success');
    } catch (error) {
      onNotify?.(error.message || 'Không thể tải ảnh lên', 'error');
    } finally {
      setUploadingImage(false);
    }
  };

  const richFields = { ...(slide.richText || {}) };
  delete richFields.bullets;
  const displaySlide = { ...slide, ...richFields };

  return (
    <div className={`editable-slide-root ${readonly ? 'readonly' : ''}`} data-theme={theme}>
      {!readonly && slide?.type === 'imageText' && (
        <input
          ref={imageInputRef}
          className="es-image-input"
          type="file"
          accept="image/png,image/jpeg,image/webp,image/gif"
          onChange={handleImageUpload}
        />
      )}
      <Component
        slide={displaySlide}
        t={t}
        sk={sk}
        onSave={handleSave}
        readonly={readonly}
        imageFit={inferImageFit(displaySlide)}
        uploadingImage={uploadingImage}
        onPickImage={() => imageInputRef.current?.click()}
      />
      <div className="es-slide-number" style={{ color: t.textSub }}>
        {String(slideIndex + 1).padStart(2, '0')}
      </div>
    </div>
  );
}
