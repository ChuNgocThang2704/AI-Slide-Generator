import { motion } from 'framer-motion';
import './SlideRenderer.css';
import { ChartVisual, TableVisual } from './StructuredVisual';
import './StructuredVisual.css';
import { resolveAssetUrl } from '../../utils/assetUrl';
import AssetImage from './AssetImage';

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
function BgDecorations({ theme }) {
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
  return (
    <div className="slide-wrap slide-content" style={{ background: t.bgGrad, position: 'relative' }}>
      <BgDecorations theme={theme} />
      <div style={{ position: 'absolute', left: 48, top: 48, width: 5, height: 40, borderRadius: 999, background: t.accentGrad }} />
      <div style={{ position: 'absolute', left: 64, top: 46, width: 832, display: 'flex', flexDirection: 'column', gap: 28 }}>
        <h2 style={{ fontFamily: t.fontTitle, fontSize: 34, fontWeight: 700, color: t.text, lineHeight: 1.2 }}>{slide.title}</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: bulletGap(count) }}>
          {slide.bullets?.map((b, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 16 }}>
              <div style={{ flexShrink: 0, width: 28, height: 28, borderRadius: '50%', background: t.accentGrad, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 700, color: '#fff', fontFamily: t.fontTitle, marginTop: 1 }}>{String(i + 1).padStart(2, '0')}</div>
              <span style={{ fontFamily: t.fontBody, fontSize: 16.5, color: t.textSub, lineHeight: 1.55, fontWeight: 400 }}>{b}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="slide-slide-number" style={{ color: t.textSub }}>{String(index + 1).padStart(2, '0')}</div>
    </div>
  );
}

// Helper: compute gap between bullet items based on count
// Fewer items → more spacing to avoid large blank area at bottom
function bulletGap(count) {
  if (count <= 2) return 36;
  if (count <= 3) return 28;
  if (count <= 4) return 20;
  if (count <= 5) return 14;
  return 10;
}

// ─────────────────────────────────────────────
// Template-specific CONTENT slide variants
// ─────────────────────────────────────────────

// ROYAL-PURPLE — gradient-bordered cards
function RoyalPurpleContentSlide({ slide, theme, index }) {
  const t = THEMES[theme];
  const count = slide.bullets?.length || 0;
  return (
    <div className="slide-wrap slide-content" style={{ background: t.bgGrad, position: 'relative' }}>
      <BgDecorations theme={theme} />
      <div style={{ position: 'absolute', left: 48, top: 48, width: 5, height: 44, borderRadius: 999, background: t.accentGrad }} />
      <div style={{ position: 'absolute', left: 64, top: 44, width: 832, display: 'flex', flexDirection: 'column', gap: 28 }}>
        <h2 style={{ fontFamily: t.fontTitle, fontSize: 34, fontWeight: 700, color: t.text, lineHeight: 1.2 }}>{slide.title}</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: bulletGap(count) }}>
          {slide.bullets?.map((b, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 0, borderLeft: '3px solid', borderImage: `${t.accentGrad} 1`, background: 'rgba(153,72,255,0.07)', borderRadius: '0 10px 10px 0', padding: '10px 16px 10px 14px' }}>
              <span style={{ color: t.accent, fontWeight: 700, fontFamily: t.fontTitle, fontSize: 13, marginRight: 10, marginTop: 2, flexShrink: 0 }}>{String(i+1).padStart(2,'0')}.</span>
              <span style={{ fontFamily: t.fontBody, fontSize: 16, color: t.textSub, lineHeight: 1.5 }}>{b}</span>
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
  const padV = count <= 3 ? 20 : count <= 5 ? 14 : 10;
  return (
    <div className="slide-wrap slide-content" style={{ background: t.bgGrad, position: 'relative' }}>
      <BgDecorations theme={theme} />
      <div style={{ position: 'absolute', left: 48, top: 48, width: 4, height: 40, borderRadius: 999, background: t.accentGrad }} />
      <div style={{ position: 'absolute', left: 64, top: 46, width: 832, display: 'flex', flexDirection: 'column', gap: 28 }}>
        <h2 style={{ fontFamily: t.fontTitle, fontSize: 36, fontWeight: 400, color: t.text, lineHeight: 1.2, letterSpacing: '-0.3px' }}>{slide.title}</h2>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {slide.bullets?.map((b, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 20, padding: `${padV}px 0`, borderBottom: i < (count-1) ? '1px solid #e5e5e5' : 'none' }}>
              <span style={{ color: t.accent, fontFamily: t.fontTitle, fontWeight: 800, fontSize: 26, lineHeight: 1, minWidth: 36, paddingTop: 2 }}>{i+1}</span>
              <span style={{ fontFamily: t.fontBody, fontSize: 16, color: t.textSub, lineHeight: 1.6 }}>{b}</span>
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
  return (
    <div className="slide-wrap slide-content" style={{ background: t.bgGrad, position: 'relative' }}>
      <BgDecorations theme={theme} />
      <div style={{ position: 'absolute', left: 48, top: 48, width: 5, height: 40, borderRadius: 999, background: t.accentGrad }} />
      <div style={{ position: 'absolute', left: 64, top: 44, width: 832, display: 'flex', flexDirection: 'column', gap: 28 }}>
        <h2 style={{ fontFamily: t.fontTitle, fontSize: 34, fontWeight: 600, color: t.text, lineHeight: 1.2, letterSpacing: '-0.5px' }}>{slide.title}</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: bulletGap(count) }}>
          {slide.bullets?.map((b, i) => (
            <div key={i} style={{ background: 'rgba(255,255,255,0.05)', backdropFilter: 'blur(10px)', border: '1px solid rgba(108,99,255,0.2)', borderRadius: 10, padding: '12px 18px', display: 'flex', alignItems: 'flex-start', gap: 12 }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: t.accentGrad, flexShrink: 0, marginTop: 7 }} />
              <span style={{ fontFamily: t.fontBody, fontSize: 16, color: t.textSub, lineHeight: 1.5 }}>{b}</span>
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
  return (
    <div className="slide-wrap slide-content" style={{ background: t.bgGrad, position: 'relative' }}>
      <BgDecorations theme={theme} />
      <div style={{ position: 'absolute', left: 64, top: 44, width: 832, display: 'flex', flexDirection: 'column', gap: 28 }}>
        <h2 style={{ fontFamily: t.fontTitle, fontSize: 38, fontWeight: 400, color: t.text, lineHeight: 1.2 }}>{slide.title}</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: bulletGap(count) }}>
          {slide.bullets?.map((b, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
              <div style={{ flexShrink: 0, width: 28, height: 28, borderRadius: '50%', background: colors[i % colors.length], display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, fontWeight: 700, color: '#fff', fontFamily: t.fontTitle, marginTop: 2 }}>{i+1}</div>
              <span style={{ fontFamily: t.fontBody, fontSize: 16, color: t.textSub, lineHeight: 1.55 }}>{b}</span>
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
  return (
    <div className="slide-wrap slide-content" style={{ background: t.bgGrad, position: 'relative' }}>
      <BgDecorations theme={theme} />
      <div style={{ position: 'absolute', left: 64, top: 44, width: 832, display: 'flex', flexDirection: 'column', gap: 28 }}>
        <h2 style={{ fontFamily: t.fontTitle, fontSize: 34, fontWeight: 700, color: t.text, lineHeight: 1.2 }}>{slide.title}</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: bulletGap(count) }}>
          {slide.bullets?.map((b, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 0, background: i%2===0 ? 'rgba(108,99,255,0.05)' : 'rgba(56,189,248,0.04)', borderRadius: '0 10px 10px 0', overflow: 'hidden' }}>
              <div style={{ width: 4, flexShrink: 0, alignSelf: 'stretch', background: t.accentGrad }} />
              <span style={{ fontFamily: t.fontBody, fontSize: 16, color: t.textSub, lineHeight: 1.5, padding: '12px 16px' }}>{b}</span>
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
  return (
    <div className="slide-wrap slide-content" style={{ background: t.bgGrad, position: 'relative' }}>
      <BgDecorations theme={theme} />
      <div style={{ position: 'absolute', left: 48, top: 48, width: 5, height: 40, borderRadius: 999, background: t.accentGrad }} />
      <div style={{ position: 'absolute', left: 64, top: 44, width: 630, display: 'flex', flexDirection: 'column', gap: 28 }}>
        <h2 style={{ fontFamily: t.fontTitle, fontSize: 32, fontWeight: 600, color: t.text, lineHeight: 1.2, letterSpacing: '0.5px' }}>{slide.title}</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: bulletGap(count) }}>
          {slide.bullets?.map((b, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
              <div style={{ flexShrink: 0, width: 10, height: 10, borderRadius: '50%', background: t.accentGrad, boxShadow: `0 0 8px ${t.primary}88`, marginTop: 7 }} />
              <span style={{ fontFamily: t.fontBody, fontSize: 16, color: t.textSub, lineHeight: 1.55 }}>{b}</span>
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
  return (
    <div className="slide-wrap slide-content" style={{ background: t.bgGrad, position: 'relative' }}>
      <BgDecorations theme={theme} />
      <div style={{ position: 'absolute', left: 48, top: 48, width: 5, height: 40, borderRadius: '0 999px 999px 0', background: t.accentGrad }} />
      <div style={{ position: 'absolute', left: 64, top: 44, width: 832, display: 'flex', flexDirection: 'column', gap: 28 }}>
        <h2 style={{ fontFamily: t.fontTitle, fontSize: 32, fontWeight: 700, color: t.text, lineHeight: 1.25 }}>{slide.title}</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: bulletGap(count) }}>
          {slide.bullets?.map((b, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
              <div style={{ flexShrink: 0, width: 12, height: 12, background: t.accentGrad, borderRadius: '50% 0 50% 0', transform: 'rotate(-15deg)', marginTop: 6 }} />
              <span style={{ fontFamily: t.fontBody, fontSize: 16, color: t.textSub, lineHeight: 1.6 }}>{b}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="slide-slide-number" style={{ color: t.textSub }}>{String(index+1).padStart(2,'0')}</div>
    </div>
  );
}

// TECH-PURPLE — 2-column grid with square tech dots
function TechPurpleContentSlide({ slide, theme, index }) {
  const t = THEMES[theme];
  const bullets = slide.bullets || [];
  const half = Math.ceil(bullets.length / 2);
  const left = bullets.slice(0, half);
  const right = bullets.slice(half);
  const rowGap = bulletGap(Math.max(left.length, right.length));
  return (
    <div className="slide-wrap slide-content" style={{ background: t.bgGrad, position: 'relative' }}>
      <BgDecorations theme={theme} />
      <div style={{ position: 'absolute', left: 48, top: 48, width: 4, height: 40, background: t.accentGrad }} />
      <div style={{ position: 'absolute', left: 64, top: 44, width: 832, display: 'flex', flexDirection: 'column', gap: 28 }}>
        <h2 style={{ fontFamily: t.fontTitle, fontSize: 34, fontWeight: 700, color: t.text, lineHeight: 1.2, letterSpacing: '1px', textTransform: 'uppercase' }}>{slide.title}</h2>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: `0 40px` }}>
          {[left, right].map((col, ci) => (
            <div key={ci} style={{ display: 'flex', flexDirection: 'column', gap: rowGap }}>
              {col.map((b, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                  <div style={{ flexShrink: 0, width: 8, height: 8, background: t.accentGrad, marginTop: 7 }} />
                  <span style={{ fontFamily: t.fontBody, fontSize: 15.5, color: t.textSub, lineHeight: 1.5 }}>{b}</span>
                </div>
              ))}
            </div>
          ))}
        </div>
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
  return (
    <div className="slide-wrap slide-content" style={{ background: t.bgGrad }}>
      <BgDecorations theme={theme} />
      <div className="slide-content-inner">
        <div className="slide-content-header">
          <div className="slide-accent-bar" style={{ background: t.accentGrad }} />
          <h2 className="slide-section-title" style={{ color: t.text, fontFamily: t.fontTitle }}>{slide.title}</h2>
        </div>
        <ul className="slide-bullets" style={{ fontFamily: t.fontBody }}>
          {slide.bullets?.map((b, i) => (
            <li key={i} className="slide-bullet-item">
              <span className="bullet-dot" style={{ background: t.accentGrad }} />
              <span style={{ color: t.textSub }}>{b}</span>
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
  return (
    <div className="slide-wrap slide-twocol" style={{ background: t.bgGrad }}>
      <BgDecorations theme={theme} />
      <div className="slide-twocol-inner">
        <div className="slide-content-header">
          <div className="slide-accent-bar" style={{ background: t.accentGrad }} />
          <h2 className="slide-section-title" style={{ color: t.text, fontFamily: t.fontTitle }}>{slide.title}</h2>
        </div>
        <div className="slide-twocol-grid">
          {[slide.left, slide.right].map((col, ci) => (
            <div key={ci} className="slide-col-card" style={{ background: t.surface, borderColor: t.surfaceBorder }}>
              <div className="slide-col-heading" style={{ color: t.primary, fontFamily: t.fontTitle }}>{col?.heading}</div>
              <ul className="slide-col-list" style={{ fontFamily: t.fontBody }}>
                {col?.points?.map((p, i) => (
                  <li key={i} style={{ color: t.textSub }}>
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
// Helper to resolve remote /outputs/ URLs to localhost:8000 for local development setup
function ImageTextSlide({ slide, theme, index }) {
  const t = THEMES[theme] || THEMES['clean-white'];
  return (
    <div className="slide-wrap slide-imagetext" style={{ background: t.bgGrad }}>
      <BgDecorations theme={theme} />
      <div className="slide-imagetext-inner">
        <div className="slide-image-box" style={{ background: t.surface, borderColor: t.surfaceBorder, overflow: 'hidden', padding: 0 }}>
          {slide.imageUrl ? (
            <img src={resolveAssetUrl(slide.imageUrl)} alt={slide.title} style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: 'inherit' }} />
          ) : (
            <>
              <div className="slide-image-emoji">{slide.imageEmoji || '🖼️'}</div>
              <div className="slide-image-caption" style={{ background: t.accentGrad, WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', fontFamily: t.fontTitle }}>
                {slide.title}
              </div>
            </>
          )}
        </div>
        <div className="slide-imagetext-content">
          <div className="slide-accent-bar" style={{ background: t.accentGrad }} />
          <h2 className="slide-section-title" style={{ color: t.text, fontFamily: t.fontTitle }}>{slide.title}</h2>
          <p className="slide-body-text" style={{ color: t.textSub, fontFamily: t.fontBody }}>{slide.text}</p>
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
  return (
    <div className="slide-wrap slide-content" style={{ background: t.bgGrad }}>
      <BgDecorations theme={theme} />
      <div className="slide-content-inner" style={{ gap: 18 }}>
        <div className="slide-bar" style={{ background: t.accentGrad }} />
        <h2 className="slide-section-title" style={{ color: t.text, fontFamily: t.fontTitle }}>{slide.title}</h2>
        <div style={{ flex: 1, minHeight: 0 }}>
          {slide.type === 'table'
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
              ? <AssetImage src={resolveAssetUrl(element.src)} storageUrl={element.storageUrl} assetId={element.assetId} alt="" style={{ width:'100%', height:'100%', objectFit:element.objectFit || 'cover', objectPosition:`${element.objectPositionX ?? 50}% ${element.objectPositionY ?? 50}%` }}/>
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
