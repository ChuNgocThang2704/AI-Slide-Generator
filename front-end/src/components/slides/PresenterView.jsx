import { useEffect, useRef, useState } from 'react';
import { ChevronLeft, ChevronRight, Clock, ExternalLink, Pause, Play, RotateCcw, X } from 'lucide-react';
import ElementCanvas from './ElementCanvas';
import { isCustomTemplateId } from '../../services/templateService';
import './PresenterView.css';

// ElementCanvas always renders at a fixed 960x540 CSS px and relies on its parent to scale it
// down with a CSS transform, so this measures the box it is given and keeps the slide fitted.
export function FittedSlide({ slide, theme, index, revealStage = null }) {
  const frameRef = useRef(null);
  const [scale, setScale] = useState(0.3);

  useEffect(() => {
    const node = frameRef.current;
    if (!node) return undefined;
    const update = () => setScale(Math.max(0.05, node.clientWidth / 960));
    update();
    const observer = new ResizeObserver(update);
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  return (
    <div className="pvw-frame" ref={frameRef}>
      {slide && (
        <div style={{ width: 960, height: 540, transform: `scale(${scale})`, transformOrigin: 'top left' }}>
          <ElementCanvas
            slide={slide}
            theme={theme}
            index={index}
            scale={1}
            readonly
            preserveTemplateStyles={isCustomTemplateId(theme)}
            revealStage={revealStage}
          />
        </div>
      )}
    </div>
  );
}

const pad2 = (value) => String(value).padStart(2, '0');
const formatElapsed = (seconds) => {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${h > 0 ? `${pad2(h)}:` : ''}${pad2(m)}:${pad2(seconds % 60)}`;
};

/**
 * The presenter's own screen, like PowerPoint's Presenter View: the slide on screen, what
 * comes next, the speaker notes and a running clock. The audience only ever sees the plain
 * slide, in its own window (see PresentPage) kept in step over the editor's BroadcastChannel.
 */
export default function PresenterView({
  slides, activeIdx, revealStage, revealEnabled, revealTotal, theme,
  audienceOpen, onNext, onPrev, onOpenAudience, onExit,
}) {
  const [elapsed, setElapsed] = useState(0);
  const [running, setRunning] = useState(true);

  useEffect(() => {
    if (!running) return undefined;
    const timer = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(timer);
  }, [running]);

  const slide = slides[activeIdx];
  const next = slides[activeIdx + 1];
  const atEnd = activeIdx >= slides.length - 1 && (!revealEnabled || revealStage >= revealTotal);
  const atStart = activeIdx === 0 && revealStage === 0;

  return (
    <div className="pvw" onClick={(event) => event.stopPropagation()}>
      <header className="pvw-top">
        <strong>Chế độ diễn giả</strong>
        <span className="pvw-count">Slide {activeIdx + 1} / {slides.length}</span>
        <div className="pvw-clock">
          <Clock size={15} />
          <span>{formatElapsed(elapsed)}</span>
          <button type="button" onClick={() => setRunning((r) => !r)} title={running ? 'Tạm dừng' : 'Tiếp tục'}>
            {running ? <Pause size={13} /> : <Play size={13} />}
          </button>
          <button type="button" onClick={() => { setElapsed(0); setRunning(true); }} title="Đặt lại đồng hồ"><RotateCcw size={13} /></button>
        </div>
        <button type="button" className="pvw-audience" onClick={onOpenAudience}>
          <ExternalLink size={14} /> {audienceOpen ? 'Đã kết nối màn hình khán giả' : 'Mở màn hình khán giả'}
        </button>
        <button type="button" className="pvw-exit" onClick={onExit} title="Thoát (Esc)"><X size={16} /> Kết thúc</button>
      </header>

      <div className="pvw-body">
        <section className="pvw-main">
          <span className="pvw-label">Đang hiển thị</span>
          <FittedSlide slide={slide} theme={theme} index={activeIdx} revealStage={revealEnabled ? revealStage : null} />
          <div className="pvw-nav">
            <button type="button" onClick={onPrev} disabled={atStart}><ChevronLeft size={18} /> Lùi</button>
            {revealEnabled && revealTotal > 0 && <span className="pvw-step">Ý {Math.min(revealStage, revealTotal)}/{revealTotal}</span>}
            <button type="button" className="primary" onClick={onNext} disabled={atEnd}>Tiếp <ChevronRight size={18} /></button>
          </div>
        </section>

        <aside className="pvw-side">
          <div className="pvw-next">
            <span className="pvw-label">Slide tiếp theo</span>
            {next
              ? <FittedSlide slide={next} theme={theme} index={activeIdx + 1} />
              : <div className="pvw-end">Đây là slide cuối cùng</div>}
          </div>
          <div className="pvw-notes">
            <span className="pvw-label">Ghi chú diễn giả</span>
            <div className="pvw-notes-body">{slide?.notes?.trim() || 'Slide này chưa có ghi chú. Bạn thêm ghi chú ở thẻ "Thông tin" khi soạn slide.'}</div>
          </div>
        </aside>
      </div>
    </div>
  );
}
