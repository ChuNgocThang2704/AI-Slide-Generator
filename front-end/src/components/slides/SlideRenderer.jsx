import { motion } from 'framer-motion';
import './SlideRenderer.css';
import { ChartVisual, TableVisual } from './StructuredVisual';
import './StructuredVisual.css';
import { resolveAssetUrl } from '../../utils/assetUrl';
import AssetImage from './AssetImage';
import { inferImageFit } from '../../utils/imageFit';

// ─────────────────────────────────────────────
// Template Themes (colors, fonts, accent styles)
// ─────────────────────────────────────────────
const THEMES = {
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

// ─────────────────────────────────────────────
// Decorative background shapes per template
// ─────────────────────────────────────────────
export function BgDecorations({ theme }) {
  const t = THEMES[theme] || THEMES['clean-white'];

  if (t.id === 'royal-purple') {
    return (
      <div className="slide-bg-deco" aria-hidden="true">
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
      <div className="slide-bg-deco" aria-hidden="true">
        {/* Deep blue panel on the right — SlideSpeak style */}
        <div style={{
          position: 'absolute', right: 0, top: 0,
          width: 320, height: '100%',
          background: 'linear-gradient(160deg, #0d5099 0%, #1a72b8 80%, #3b96d2 100%)',
          opacity: 0.07,
          borderRadius: '60% 0 0 60% / 50% 0 0 50%',
        }} />
        {/* Top-left large soft blob */}
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
        {/* Bottom-right wave layer */}
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
        {/* Decorative circle ring top-right */}
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
        {/* Floating sparkle dots */}
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
      <div className="slide-bg-deco" aria-hidden="true">
        <div style={{ position: 'absolute', top: 32, left: 32, width: 3, height: 40, background: t.accentGrad }} />
      </div>
    );
  }

  if (t.id === 'playful-yellow') {
    return (
      <div className="slide-bg-deco" aria-hidden="true">
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
      <div className="slide-bg-deco" aria-hidden="true">
        <motion.div
          animate={{ opacity: [0.85, 1, 0.85] }}
          transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
          style={{
            position: 'absolute',
            inset: 16,
            border: '3px solid transparent',
            borderRadius: 12,
            pointerEvents: 'none',
            background: `linear-gradient(${t.bg}, ${t.bg}) padding-box, linear-gradient(135deg, #6c63ff, #38bdf8) border-box`
          }}
        />
      </div>
    );
  }

  if (t.id === 'blue-planet') {
    return (
      <div className="slide-bg-deco" aria-hidden="true">
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
      <div className="slide-bg-deco" aria-hidden="true">
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
      <div className="slide-bg-deco" aria-hidden="true">
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
    <div className="slide-bg-deco" aria-hidden="true">
      <motion.div
        animate={{ scale: [1, 1.1, 1], y: [0, 10, 0] }}
        transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
        className="deco-circle deco-1"
        style={{ background: t.primary + '20' }}
      />
      <motion.div
        animate={{ scale: [1, 1.15, 1], x: [0, -10, 0] }}
        transition={{ duration: 10, repeat: Infinity, ease: "easeInOut" }}
        className="deco-circle deco-2"
        style={{ background: t.accent + '15' }}
      />
      <div className="deco-line" style={{ background: t.accentGrad }} />
    </div>
  );
}

// ─────────────────────────────────────────────
// Slide Type: TITLE — SOFT-BLUE variant
// ─────────────────────────────────────────────
function SoftBlueTitleSlide({ slide, theme }) {
  const t = THEMES[theme];
  return (
    <div className="slide-wrap slide-title sb-title-wrap" style={{ background: t.bgGrad }}>
      <BgDecorations theme={theme} />
      {/* Right decorative panel */}
      <div className="sb-title-panel" style={{ background: t.panelBg }}>
        <svg viewBox="0 0 200 420" width="100%" height="100%" style={{ opacity: 0.18 }}>
          <circle cx="100" cy="80" r="60" fill="white" />
          <rect x="30" y="160" width="140" height="8" rx="4" fill="white" />
          <rect x="55" y="184" width="90" height="6" rx="3" fill="white" />
          <rect x="30" y="220" width="140" height="8" rx="4" fill="white" />
          <rect x="55" y="244" width="90" height="6" rx="3" fill="white" />
          <rect x="30" y="280" width="140" height="8" rx="4" fill="white" />
          <circle cx="100" cy="360" r="30" fill="none" stroke="white" strokeWidth="6" />
          <path d="M85,360 L115,360 M100,345 L100,375" stroke="white" strokeWidth="4" strokeLinecap="round" />
        </svg>
      </div>
      {/* Left text content */}
      <div className="sb-title-left">
        <motion.div
          initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="slide-title-badge"
          style={{ background: 'rgba(13,80,153,0.08)', borderColor: 'rgba(13,80,153,0.2)', color: t.primary, fontFamily: t.fontTitle }}
        >
          ✦ Presentation
        </motion.div>
        <motion.h1
          initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, delay: 0.08 }}
          className="slide-main-title sb-main-title"
          style={{ color: t.text, fontFamily: t.fontTitle }}
        >{slide.title}</motion.h1>
        {slide.subtitle && (
          <motion.p
            initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.18 }}
            className="slide-subtitle sb-subtitle"
            style={{ color: t.textSub, fontFamily: t.fontBody }}
          >{slide.subtitle}</motion.p>
        )}
        <div className="slide-title-divider" style={{ background: t.accentGrad }} />
      </div>
      <div className="slide-slide-number" style={{ color: t.textSub }}>01</div>
    </div>
  );
}

// ─────────────────────────────────────────────
// Slide Type: CONTENT — SOFT-BLUE variant (numbered list)
// ─────────────────────────────────────────────
function SoftBlueContentSlide({ slide, theme, index }) {
  const t = THEMES[theme];
  const count = slide.bullets?.length || 0;
  const fs = bulletFontSize(count);
  const tfs = titleFontSize(count);
  const badgeSize = count <= 2 ? 32 : count <= 3 ? 28 : 24;
  const badgeFontSz = count <= 2 ? 14 : count <= 3 ? 12 : 11;
  return (
    <div className="slide-wrap slide-content" style={{ background: t.bgGrad, position: 'relative' }}>
      <BgDecorations theme={theme} />
      <div style={{ position: 'absolute', left: 48, top: 48, width: 5, height: 40, borderRadius: 999, background: t.accentGrad }} />
      <div style={{ position: 'absolute', left: 64, top: 44, right: 64, bottom: 44, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
        <h2 style={{ fontFamily: t.fontTitle, fontSize: tfs, fontWeight: 700, color: t.text, lineHeight: 1.2, marginBottom: count <= 2 ? 32 : count <= 3 ? 24 : 18 }}>{slide.title}</h2>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-evenly' }}>
          {slide.bullets?.map((b, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 16 }}>
              <div style={{ flexShrink: 0, width: badgeSize, height: badgeSize, borderRadius: '50%', background: t.accentGrad, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: badgeFontSz, fontWeight: 700, color: '#fff', fontFamily: t.fontTitle, marginTop: 2 }}>{String(i + 1).padStart(2, '0')}</div>
              <span style={{ fontFamily: t.fontBody, fontSize: fs, color: t.textSub, lineHeight: 1.6, fontWeight: 400 }}>{b}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="slide-slide-number" style={{ color: t.textSub }}>{String(index + 1).padStart(2, '0')}</div>
    </div>
  );
}


// Helper: compute gap between bullet items based on count
// Adaptive — fewer items get tighter gap (content is already bigger), more items need less gap
function bulletGap(count) {
  if (count <= 2) return 20;
  if (count <= 3) return 16;
  if (count <= 4) return 12;
  if (count <= 5) return 10;
  return 8;
}

// Helper: compute font size for bullet text based on count
// Fewer bullets → bigger text to fill space nicely
function bulletFontSize(count) {
  if (count <= 2) return 20;
  if (count <= 3) return 18;
  if (count <= 4) return 16.5;
  if (count <= 5) return 15.5;
  return 14;
}

// Helper: compute font size for h2 title on content slides
function titleFontSize(count) {
  if (count <= 2) return 38;
  if (count <= 3) return 35;
  if (count <= 4) return 32;
  return 30;
}

// ─────────────────────────────────────────────
// Template-specific CONTENT slide variants
// ─────────────────────────────────────────────

// ROYAL-PURPLE — gradient-bordered cards
function RoyalPurpleContentSlide({ slide, theme, index }) {
  const t = THEMES[theme];
  const count = slide.bullets?.length || 0;
  const fs = bulletFontSize(count);
  const tfs = titleFontSize(count);
  const padV = count <= 2 ? 18 : count <= 3 ? 14 : count <= 4 ? 11 : 9;
  const numFs = count <= 3 ? 15 : 13;
  return (
    <div className="slide-wrap slide-content" style={{ background: t.bgGrad, display: 'flex', flexDirection: 'column', padding: 64 }}>
      <BgDecorations theme={theme} />
      <div style={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
        <div style={{ width: 5, height: 44, borderRadius: 999, background: t.accentGrad, marginBottom: count <= 2 ? 36 : count <= 3 ? 28 : 22 }} />
        <h2 style={{ fontFamily: t.fontTitle, fontSize: tfs, fontWeight: 700, color: t.text, lineHeight: 1.2, marginBottom: count <= 2 ? 36 : count <= 3 ? 28 : 22 }}>{slide.title}</h2>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: bulletGap(count) }}>
          {slide.bullets?.map((b, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 0, borderLeft: '3px solid', borderImage: `${t.accentGrad} 1`, background: 'rgba(153,72,255,0.07)', borderRadius: '0 10px 10px 0', padding: `${padV}px 16px ${padV}px 14px` }}>
              <span style={{ color: t.accent, fontWeight: 700, fontFamily: t.fontTitle, fontSize: numFs, marginRight: 12, marginTop: 2, flexShrink: 0 }}>{String(i+1).padStart(2,'0')}.</span>
              <span style={{ fontFamily: t.fontBody, fontSize: fs, color: t.textSub, lineHeight: 1.6 }}>{b}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="slide-slide-number" style={{ color: t.textSub }}>{String(index+1).padStart(2,'0')}</div>
    </div>
  );
}

// CLEAN-WHITE — numbered timeline with dividers
function CleanWhiteContentSlide({ slide, theme, index }) {
  const t = THEMES[theme];
  const count = slide.bullets?.length || 0;
  const fs = count <= 2 ? 21 : count <= 3 ? 18.5 : count <= 4 ? 17 : count <= 5 ? 15.5 : 14;
  const tfs = count <= 2 ? 40 : count <= 3 ? 36 : count <= 4 ? 32 : 30;
  const numFs = count <= 2 ? 40 : count <= 3 ? 32 : count <= 4 ? 26 : 22;
  const padV = count <= 2 ? 28 : count <= 3 ? 22 : count <= 4 ? 16 : count <= 5 ? 12 : 8;
  return (
    <div className="slide-wrap slide-content" style={{ background: t.bgGrad, position: 'relative' }}>
      <BgDecorations theme={theme} />
      <div style={{ position: 'absolute', left: 48, top: 48, width: 4, height: 40, borderRadius: 999, background: t.accentGrad }} />
      <div style={{ position: 'absolute', left: 64, top: 46, right: 64, bottom: 44, display: 'flex', flexDirection: 'column' }}>
        <h2 style={{ fontFamily: t.fontTitle, fontSize: tfs, fontWeight: 400, color: t.text, lineHeight: 1.2, letterSpacing: '-0.3px', marginBottom: count <= 2 ? 32 : count <= 3 ? 22 : 14, flexShrink: 0 }}>{slide.title}</h2>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-evenly', minHeight: 0 }}>
          {slide.bullets?.map((b, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 20, paddingTop: padV, paddingBottom: padV, borderBottom: i < (count-1) ? `1px solid ${t.accent}22` : 'none' }}>
              <span style={{ color: t.accent, fontFamily: t.fontTitle, fontWeight: 800, fontSize: numFs, lineHeight: 1, minWidth: count <= 2 ? 50 : count <= 3 ? 44 : 36, paddingTop: 2, flexShrink: 0 }}>{i+1}</span>
              <span style={{ fontFamily: t.fontBody, fontSize: fs, color: t.textSub, lineHeight: 1.7, fontWeight: 400 }}>{b}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="slide-slide-number" style={{ color: t.textSub }}>{String(index+1).padStart(2,'0')}</div>
    </div>
  );
}


// MODERN-DARK — glassmorphism cards
function ModernDarkContentSlide({ slide, theme, index }) {
  const t = THEMES[theme];
  const count = slide.bullets?.length || 0;
  const fs = bulletFontSize(count);
  const tfs = titleFontSize(count);
  const padCard = count <= 2 ? '18px 22px' : count <= 3 ? '15px 20px' : count <= 4 ? '12px 18px' : '9px 16px';
  const dotSize = count <= 3 ? 10 : 8;
  return (
    <div className="slide-wrap slide-content" style={{ background: t.bgGrad, position: 'relative' }}>
      <BgDecorations theme={theme} />
      <div style={{ position: 'absolute', left: 48, top: 48, width: 5, height: 40, borderRadius: 999, background: t.accentGrad }} />
      <div style={{ position: 'absolute', left: 64, top: 44, right: 64, bottom: 44, display: 'flex', flexDirection: 'column' }}>
        <h2 style={{ fontFamily: t.fontTitle, fontSize: tfs, fontWeight: 600, color: t.text, lineHeight: 1.2, letterSpacing: '-0.5px', marginBottom: count <= 2 ? 28 : count <= 3 ? 20 : 14 }}>{slide.title}</h2>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-evenly' }}>
          {slide.bullets?.map((b, i) => (
            <div key={i} style={{ background: 'rgba(255,255,255,0.05)', backdropFilter: 'blur(10px)', border: '1px solid rgba(108,99,255,0.2)', borderRadius: 10, padding: padCard, display: 'flex', alignItems: 'flex-start', gap: 14 }}>
              <span style={{ width: dotSize, height: dotSize, borderRadius: '50%', background: t.accentGrad, flexShrink: 0, marginTop: 4 }} />
              <span style={{ fontFamily: t.fontBody, fontSize: fs, color: t.textSub, lineHeight: 1.6 }}>{b}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="slide-slide-number" style={{ color: t.textSub }}>{String(index+1).padStart(2,'0')}</div>
    </div>
  );
}

// PLAYFUL-YELLOW — alternating color badge bullets
function PlayfulYellowContentSlide({ slide, theme, index }) {
  const t = THEMES[theme];
  const colors = ['#f59e0b','#8b5cf6','#ef4444','#10b981','#3b82f6'];
  const count = slide.bullets?.length || 0;
  const fs = bulletFontSize(count);
  const tfs = count <= 2 ? 42 : count <= 3 ? 38 : count <= 4 ? 34 : 30;
  const badgeSize = count <= 2 ? 34 : count <= 3 ? 30 : 26;
  const badgeFontSize = count <= 2 ? 15 : count <= 3 ? 13 : 12;
  return (
    <div className="slide-wrap slide-content" style={{ background: t.bgGrad, position: 'relative' }}>
      <BgDecorations theme={theme} />
      <div style={{ position: 'absolute', left: 64, top: 44, right: 64, bottom: 44, display: 'flex', flexDirection: 'column' }}>
        <h2 style={{ fontFamily: t.fontTitle, fontSize: tfs, fontWeight: 400, color: t.text, lineHeight: 1.2, marginBottom: count <= 2 ? 28 : count <= 3 ? 20 : 14 }}>{slide.title}</h2>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-evenly' }}>
          {slide.bullets?.map((b, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
              <div style={{ flexShrink: 0, width: badgeSize, height: badgeSize, borderRadius: '50%', background: colors[i % colors.length], display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: badgeFontSize, fontWeight: 700, color: '#fff', fontFamily: t.fontTitle, marginTop: 2 }}>{i+1}</div>
              <span style={{ fontFamily: t.fontBody, fontSize: fs, color: t.textSub, lineHeight: 1.6 }}>{b}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="slide-slide-number" style={{ color: t.textSub }}>{String(index+1).padStart(2,'0')}</div>
    </div>
  );
}

// GRADIENT-BORDER — left gradient bar + tinted rows
function GradientBorderContentSlide({ slide, theme, index }) {
  const t = THEMES[theme];
  const count = slide.bullets?.length || 0;
  const fs = bulletFontSize(count);
  const tfs = titleFontSize(count);
  const padRow = count <= 2 ? '18px 18px' : count <= 3 ? '14px 16px' : count <= 4 ? '11px 15px' : '9px 14px';
  return (
    <div className="slide-wrap slide-content" style={{ background: t.bgGrad, position: 'relative' }}>
      <BgDecorations theme={theme} />
      <div style={{ position: 'absolute', left: 64, top: 44, right: 64, bottom: 44, display: 'flex', flexDirection: 'column' }}>
        <h2 style={{ fontFamily: t.fontTitle, fontSize: tfs, fontWeight: 700, color: t.text, lineHeight: 1.2, marginBottom: count <= 2 ? 28 : count <= 3 ? 20 : 14 }}>{slide.title}</h2>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-evenly' }}>
          {slide.bullets?.map((b, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'stretch', gap: 0, background: i%2===0 ? 'rgba(108,99,255,0.05)' : 'rgba(56,189,248,0.04)', borderRadius: '0 10px 10px 0', overflow: 'hidden' }}>
              <div style={{ width: count <= 3 ? 5 : 4, flexShrink: 0, background: t.accentGrad }} />
              <span style={{ fontFamily: t.fontBody, fontSize: fs, color: t.textSub, lineHeight: 1.6, padding: padRow, display: 'flex', alignItems: 'center' }}>{b}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="slide-slide-number" style={{ color: t.textSub }}>{String(index+1).padStart(2,'0')}</div>
    </div>
  );
}

// BLUE-PLANET — cyan glowing bullets (content fits left to avoid planet)
function BluePlanetContentSlide({ slide, theme, index }) {
  const t = THEMES[theme];
  const count = slide.bullets?.length || 0;
  const fs = bulletFontSize(count);
  const tfs = count <= 2 ? 34 : count <= 3 ? 30 : count <= 4 ? 28 : 26;
  const dotSize = count <= 3 ? 12 : 10;
  return (
    <div className="slide-wrap slide-content" style={{ background: t.bgGrad, position: 'relative' }}>
      <BgDecorations theme={theme} />
      <div style={{ position: 'absolute', left: 48, top: 48, width: 5, height: 40, borderRadius: 999, background: t.accentGrad }} />
      <div style={{ position: 'absolute', left: 64, top: 44, width: 630, bottom: 44, display: 'flex', flexDirection: 'column' }}>
        <h2 style={{ fontFamily: t.fontTitle, fontSize: tfs, fontWeight: 600, color: t.text, lineHeight: 1.2, letterSpacing: '0.5px', marginBottom: count <= 2 ? 28 : count <= 3 ? 20 : 14 }}>{slide.title}</h2>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-evenly' }}>
          {slide.bullets?.map((b, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
              <div style={{ flexShrink: 0, width: dotSize, height: dotSize, borderRadius: '50%', background: t.accentGrad, boxShadow: `0 0 10px ${t.primary}99`, marginTop: 4 }} />
              <span style={{ fontFamily: t.fontBody, fontSize: fs, color: t.textSub, lineHeight: 1.6 }}>{b}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="slide-slide-number" style={{ color: t.textSub }}>{String(index+1).padStart(2,'0')}</div>
    </div>
  );
}

// NATURE-GREEN — leaf-shaped bullet markers
function NatureGreenContentSlide({ slide, theme, index }) {
  const t = THEMES[theme];
  const count = slide.bullets?.length || 0;
  const fs = bulletFontSize(count);
  const tfs = count <= 2 ? 34 : count <= 3 ? 30 : count <= 4 ? 28 : 26;
  const leafSize = count <= 3 ? 14 : 12;
  return (
    <div className="slide-wrap slide-content" style={{ background: t.bgGrad, position: 'relative' }}>
      <BgDecorations theme={theme} />
      <div style={{ position: 'absolute', left: 48, top: 48, width: 5, height: 40, borderRadius: '0 999px 999px 0', background: t.accentGrad }} />
      <div style={{ position: 'absolute', left: 64, top: 44, right: 64, bottom: 44, display: 'flex', flexDirection: 'column' }}>
        <h2 style={{ fontFamily: t.fontTitle, fontSize: tfs, fontWeight: 700, color: t.text, lineHeight: 1.25, marginBottom: count <= 2 ? 28 : count <= 3 ? 20 : 14 }}>{slide.title}</h2>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-evenly' }}>
          {slide.bullets?.map((b, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
              <div style={{ flexShrink: 0, width: leafSize, height: leafSize, background: t.accentGrad, borderRadius: '50% 0 50% 0', transform: 'rotate(-15deg)', marginTop: 5 }} />
              <span style={{ fontFamily: t.fontBody, fontSize: fs, color: t.textSub, lineHeight: 1.65 }}>{b}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="slide-slide-number" style={{ color: t.textSub }}>{String(index+1).padStart(2,'0')}</div>
    </div>
  );
}

// TECH-PURPLE — 2-column grid with square tech dots (single col when ≤3 bullets)
function TechPurpleContentSlide({ slide, theme, index }) {
  const t = THEMES[theme];
  const bullets = slide.bullets || [];
  const count = bullets.length;
  const useGrid = count >= 4;
  const half = Math.ceil(count / 2);
  const leftCol = useGrid ? bullets.slice(0, half) : bullets;
  const rightCol = useGrid ? bullets.slice(half) : [];
  const colCount = useGrid ? Math.max(leftCol.length, rightCol.length) : count;
  const fs = useGrid ? (count <= 6 ? 15.5 : 14) : bulletFontSize(count);
  const tfs = titleFontSize(count);
  const dotSize = count <= 3 ? 10 : 8;
  return (
    <div className="slide-wrap slide-content" style={{ background: t.bgGrad, position: 'relative' }}>
      <BgDecorations theme={theme} />
      <div style={{ position: 'absolute', left: 48, top: 48, width: 4, height: 40, background: t.accentGrad }} />
      <div style={{ position: 'absolute', left: 64, top: 44, right: 64, bottom: 44, display: 'flex', flexDirection: 'column' }}>
        <h2 style={{ fontFamily: t.fontTitle, fontSize: tfs, fontWeight: 700, color: t.text, lineHeight: 1.2, letterSpacing: '1px', textTransform: 'uppercase', marginBottom: count <= 2 ? 28 : count <= 3 ? 20 : 14 }}>{slide.title}</h2>
        {useGrid ? (
          <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 40px' }}>
            {[leftCol, rightCol].map((col, ci) => (
              <div key={ci} style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-evenly' }}>
                {col.map((b, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                    <div style={{ flexShrink: 0, width: dotSize, height: dotSize, background: t.accentGrad, marginTop: 5 }} />
                    <span style={{ fontFamily: t.fontBody, fontSize: fs, color: t.textSub, lineHeight: 1.55 }}>{b}</span>
                  </div>
                ))}
              </div>
            ))}
          </div>
        ) : (
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-evenly' }}>
            {leftCol.map((b, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
                <div style={{ flexShrink: 0, width: dotSize, height: dotSize, background: t.accentGrad, marginTop: 5 }} />
                <span style={{ fontFamily: t.fontBody, fontSize: fs, color: t.textSub, lineHeight: 1.6 }}>{b}</span>
              </div>
            ))}
          </div>
        )}
      </div>
      <div className="slide-slide-number" style={{ color: t.textSub }}>{String(index+1).padStart(2,'0')}</div>
    </div>
  );
}

// ─────────────────────────────────────────────
// Slide Type: TITLE
// ─────────────────────────────────────────────
function TitleSlide({ slide, theme }) {
  const t = THEMES[theme] || THEMES['clean-white'];
  return (
    <div className="slide-wrap slide-title" style={{ background: t.bgGrad }}>
      <BgDecorations theme={theme} />
      <div className="slide-title-content">
        <div className="slide-title-badge" style={{ background: t.primary + '22', borderColor: t.primary + '55', color: t.primary, fontFamily: t.fontTitle }}>
          ✦ Presentation
        </div>
        <h1 className="slide-main-title" style={{ color: t.text, fontFamily: t.fontTitle }}>{slide.title}</h1>
        {slide.subtitle && (
          <p className="slide-subtitle" style={{ color: t.textSub, fontFamily: t.fontBody }}>{slide.subtitle}</p>
        )}
        <div className="slide-title-divider" style={{ background: t.accentGrad }} />
      </div>
      <div className="slide-slide-number" style={{ color: t.textSub }}>01</div>
    </div>
  );
}

// ─────────────────────────────────────────────
// Slide Type: CONTENT (Bullet Points)
// ─────────────────────────────────────────────
function ContentSlide({ slide, theme, index }) {
  const t = THEMES[theme] || THEMES['clean-white'];
  const count = slide.bullets?.length || 0;
  const fs = bulletFontSize(count);
  const tfs = titleFontSize(count);
  return (
    <div className="slide-wrap slide-content" style={{ background: t.bgGrad, position: 'relative' }}>
      <BgDecorations theme={theme} />
      <div style={{ position: 'absolute', left: 64, top: 44, right: 64, bottom: 44, display: 'flex', flexDirection: 'column' }}>
        <div className="slide-content-header" style={{ marginBottom: count <= 2 ? 28 : count <= 3 ? 20 : 14 }}>
          <div className="slide-accent-bar" style={{ background: t.accentGrad }} />
          <h2 className="slide-section-title" style={{ color: t.text, fontFamily: t.fontTitle, fontSize: tfs, lineHeight: 1.2 }}>{slide.title}</h2>
        </div>
        <ul className="slide-bullets" style={{ fontFamily: t.fontBody, flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-evenly', margin: 0, padding: 0, listStyle: 'none' }}>
          {slide.bullets?.map((b, i) => (
            <li key={i} className="slide-bullet-item" style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
              <span className="bullet-dot" style={{ background: t.accentGrad, flexShrink: 0, marginTop: (fs * 1.6 - 10) / 2 }} />
              <span style={{ color: t.textSub, fontSize: fs, lineHeight: 1.6 }}>{b}</span>
            </li>
          ))}
        </ul>
      </div>
      <div className="slide-slide-number" style={{ color: t.textSub }}>{String(index + 1).padStart(2, '0')}</div>
    </div>
  );
}

// ─────────────────────────────────────────────
// Slide Type: TWO COLUMN
// ─────────────────────────────────────────────
function TwoColumnSlide({ slide, theme, index }) {
  const t = THEMES[theme] || THEMES['clean-white'];
  const leftPoints = slide.left?.points?.length || 0;
  const rightPoints = slide.right?.points?.length || 0;
  const maxPoints = Math.max(leftPoints, rightPoints);
  const fs = maxPoints <= 3 ? 15 : maxPoints <= 5 ? 13.5 : 12;
  const tfs = titleFontSize(maxPoints);
  return (
    <div className="slide-wrap slide-twocol" style={{ background: t.bgGrad, position: 'relative' }}>
      <BgDecorations theme={theme} />
      <div style={{ position: 'absolute', left: 64, top: 44, right: 64, bottom: 44, display: 'flex', flexDirection: 'column' }}>
        <div className="slide-content-header" style={{ marginBottom: 16 }}>
          <div className="slide-accent-bar" style={{ background: t.accentGrad }} />
          <h2 className="slide-section-title" style={{ color: t.text, fontFamily: t.fontTitle, fontSize: tfs, lineHeight: 1.2 }}>{slide.title}</h2>
        </div>
        <div className="slide-twocol-grid" style={{ flex: 1, gridTemplateColumns: '1fr 1fr', gap: 20 }}>
          {[slide.left, slide.right].map((col, ci) => (
            <div key={ci} className="slide-col-card" style={{ background: t.surface, borderColor: t.surfaceBorder, display: 'flex', flexDirection: 'column', height: '100%', boxSizing: 'border-box' }}>
              <div className="slide-col-heading" style={{ color: t.primary, fontFamily: t.fontTitle, fontSize: 17, marginBottom: 8 }}>{col?.heading}</div>
              <ul className="slide-col-list" style={{ fontFamily: t.fontBody, flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-evenly', margin: 0, padding: 0, listStyle: 'none' }}>
                {col?.points?.map((p, i) => (
                  <li key={i} style={{ color: t.textSub, fontSize: fs, lineHeight: 1.5, display: 'flex', gap: 8 }}>
                    <span style={{ color: t.accent }}>▸</span> {p}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
      <div className="slide-slide-number" style={{ color: t.textSub }}>{String(index + 1).padStart(2, '0')}</div>
    </div>
  );
}

// ─────────────────────────────────────────────
// Slide Type: IMAGE + TEXT
// ─────────────────────────────────────────────
function ImageTextSlide({ slide, theme, index }) {
  const t = THEMES[theme] || THEMES['clean-white'];
  const textLen = (slide.text || '').length;
  const bulletCount = slide.bullets?.length || 0;
  const fs = bulletCount > 0
    ? bulletFontSize(bulletCount)
    : textLen < 120 ? 18.5 : textLen < 250 ? 16 : 14.5;
  const tfs = titleFontSize(bulletCount || 3);
  return (
    <div className="slide-wrap slide-imagetext" style={{ background: t.bgGrad, position: 'relative' }}>
      <BgDecorations theme={theme} />
      <div style={{ position: 'absolute', left: 64, top: 44, right: 64, bottom: 44, display: 'grid', gridTemplateColumns: '1fr 1.2fr', gap: 36, alignItems: 'center' }}>
        <div className="slide-image-box" style={{ background: t.surface, borderColor: t.surfaceBorder, overflow: 'hidden', padding: 0, height: '100%', maxHeight: 380, display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 16 }}>
          {slide.imageUrl ? (
            <img src={resolveAssetUrl(slide.imageUrl)} alt={slide.title} style={{ width: '100%', height: '100%', objectFit: inferImageFit(slide), borderRadius: 'inherit' }} />
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12, padding: 24, textAlign: 'center' }}>
              <div className="slide-image-emoji" style={{ fontSize: 52 }}>{slide.imageEmoji || '🖼️'}</div>
              <div className="slide-image-caption" style={{ background: t.accentGrad, WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', fontFamily: t.fontTitle, fontSize: 16, fontWeight: 700 }}>
                {slide.title}
              </div>
            </div>
          )}
        </div>
        <div className="slide-imagetext-content" style={{ display: 'flex', flexDirection: 'column', height: '100%', justifyContent: 'center' }}>
          <div className="slide-accent-bar" style={{ background: t.accentGrad, marginBottom: 10 }} />
          <h2 className="slide-section-title" style={{ color: t.text, fontFamily: t.fontTitle, fontSize: tfs, lineHeight: 1.2, marginBottom: 14 }}>{slide.title}</h2>
          {slide.bullets && slide.bullets.length > 0 ? (
            <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: bulletGap(bulletCount) }}>
              {slide.bullets.map((b, i) => (
                <li key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 10, fontFamily: t.fontBody, fontSize: fs, color: t.textSub, lineHeight: 1.55 }}>
                  <span style={{ width: 7, height: 7, borderRadius: '50%', background: t.accentGrad, marginTop: 7, flexShrink: 0 }} />
                  <span>{b}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="slide-body-text" style={{ color: t.textSub, fontFamily: t.fontBody, fontSize: fs, lineHeight: 1.65, margin: 0 }}>{slide.text}</p>
          )}
        </div>
      </div>
      <div className="slide-slide-number" style={{ color: t.textSub }}>{String(index + 1).padStart(2, '0')}</div>
    </div>
  );
}

// ─────────────────────────────────────────────
// Slide Type: QUOTE
// ─────────────────────────────────────────────
function QuoteSlide({ slide, theme, index }) {
  const t = THEMES[theme] || THEMES['clean-white'];
  return (
    <div className="slide-wrap slide-quote" style={{ background: t.bgGrad }}>
      <BgDecorations theme={theme} />
      <div className="slide-quote-inner">
        <div className="slide-quote-mark" style={{ background: t.accentGrad, WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', fontFamily: t.fontTitle }}>"</div>
        <blockquote className="slide-quote-text" style={{ color: t.text, fontFamily: t.fontTitle }}>{slide.quote}</blockquote>
        <div className="slide-quote-divider" style={{ background: t.accentGrad }} />
        <div className="slide-quote-author">
          <div className="slide-quote-name" style={{ color: t.primary, fontFamily: t.fontTitle }}>{slide.author}</div>
          {slide.role && <div className="slide-quote-role" style={{ color: t.textSub, fontFamily: t.fontBody }}>{slide.role}</div>}
        </div>
      </div>
      <div className="slide-slide-number" style={{ color: t.textSub }}>{String(index + 1).padStart(2, '0')}</div>
    </div>
  );
}

// ─────────────────────────────────────────────
// Slide Type: THANK YOU
// ─────────────────────────────────────────────
function ThankYouSlide({ slide, theme, index }) {
  const t = THEMES[theme] || THEMES['clean-white'];
  return (
    <div className="slide-wrap slide-thankyou" style={{ background: t.bgGrad }}>
      <BgDecorations theme={theme} />
      <div className="slide-thankyou-content">
        <div className="slide-ty-icon" style={{ background: t.primary + '22', borderColor: t.primary + '44' }}>
          🎉
        </div>
        <h1 className="slide-main-title" style={{ color: t.text, fontFamily: t.fontTitle }}>{slide.title}</h1>
        {slide.subtitle && <p className="slide-subtitle" style={{ color: t.textSub, fontFamily: t.fontBody }}>{slide.subtitle}</p>}
        {slide.contact && (
          <div className="slide-ty-contact" style={{ background: t.surface, borderColor: t.surfaceBorder, color: t.primary, fontFamily: t.fontBody }}>
            ✉ {slide.contact}
          </div>
        )}
        <div className="slide-title-divider" style={{ background: t.accentGrad }} />
      </div>
      <div className="slide-slide-number" style={{ color: t.textSub }}>{String(index + 1).padStart(2, '0')}</div>
    </div>
  );
}

function StructuredSlide({ slide, theme, index }) {
  const t = THEMES[theme] || THEMES['clean-white'];
  const isTable = slide.type === 'table';
  const rowCount = isTable ? (slide.table?.rows?.length || 0) : (slide.chart?.labels?.length || 0);
  // Adaptive title size: shorter when lots of data rows
  const titleFs = rowCount <= 3 ? 36 : rowCount <= 6 ? 32 : 28;
  return (
    <div className="slide-wrap slide-content" style={{ background: t.bgGrad }}>
      <BgDecorations theme={theme} />
      <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', gap: 0, padding: '44px 64px 44px 64px', boxSizing: 'border-box' }}>
        {/* Header accent bar + title */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 20, flexShrink: 0 }}>
          <div style={{ width: 48, height: 4, borderRadius: 999, background: t.accentGrad }} />
          <h2 style={{ fontFamily: t.fontTitle, fontSize: titleFs, fontWeight: 700, color: t.text, lineHeight: 1.2, margin: 0 }}>{slide.title}</h2>
        </div>
        {/* Data visual — fills all remaining space */}
        <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
          {isTable
            ? <TableVisual table={slide.table} theme={t} />
            : <ChartVisual chart={slide.chart} theme={t} />}
        </div>
      </div>
      <div className="slide-slide-number" style={{ color: t.textSub }}>{String(index + 1).padStart(2, '0')}</div>
    </div>
  );
}

// ─────────────────────────────────────────────
// Main Renderer
// ─────────────────────────────────────────────
const SLIDE_COMPONENTS = {
  title: TitleSlide,
  content: ContentSlide,
  twoColumn: TwoColumnSlide,
  imageText: ImageTextSlide,
  table: StructuredSlide,
  chart: StructuredSlide,
  quote: QuoteSlide,
  thankyou: ThankYouSlide,
};

export default function SlideRenderer({ slide, theme = 'clean-white', index = 0, scale = 1 }) {
  if (Array.isArray(slide?.elements) && slide.elements.length) {
    const t = THEMES[theme] || THEMES['clean-white'];
    return (
      <div className="slide-renderer-root" style={{ transform: `scale(${scale})`, transformOrigin: 'top left', background: t.bgGrad || t.bg }} data-theme={theme}>
        {slide.elements.map((element, elementIndex) => (
          <div key={element.id} style={{ position:'absolute', left:element.x, top:element.y, width:element.width, height:element.height, zIndex:elementIndex + 1, transform:`rotate(${element.rotation || 0}deg)`, overflow:'hidden' }}>
            {element.type === 'image'
              ? <AssetImage src={resolveAssetUrl(element.src)} storageUrl={element.storageUrl} assetId={element.assetId} alt="" style={{ width:'100%', height:'100%', objectFit:element.objectFit || inferImageFit(element.src), objectPosition:`${element.objectPositionX ?? 50}% ${element.objectPositionY ?? 50}%` }}/>
              : <div style={{ width:'100%', height:'100%', ...element.style }} dangerouslySetInnerHTML={{ __html: element.content || '' }}/>
            }
          </div>
        ))}
      </div>
    );
  }
  // Use soft-blue specific variants where available
  let Component = SLIDE_COMPONENTS[slide?.type] || ContentSlide;
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
  if (slide?.type === 'title' && theme === 'soft-blue') Component = SoftBlueTitleSlide;
  if (slide?.type === 'content' && contentVariants[theme]) Component = contentVariants[theme];
  return (
    <div
      className="slide-renderer-root"
      style={{ transform: `scale(${scale})`, transformOrigin: 'top left' }}
      data-theme={theme}
    >
      <Component slide={slide} theme={theme} index={index} />
    </div>
  );
}
