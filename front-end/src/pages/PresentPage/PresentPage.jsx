import { useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Maximize2 } from 'lucide-react';
import { FittedSlide } from '../../components/slides/PresenterView';
import SlideTransition from '../../components/slides/SlideTransition';
import { projectService } from '../../services/documentService';
import { isCustomTemplateId } from '../../services/templateService';
import { formatSlideDeck } from '../../utils/slideMapping';
import { parseDeckMaster } from '../../utils/deckMaster';
import './PresentPage.css';

/**
 * The audience's window (opened from the presenter view): just the slide that is on
 * screen, full window, nothing else — drag it to the projector and press F11 (or the
 * button). It has no React state in common with the editor tab; the presenter drives it
 * over a BroadcastChannel scoped to this project (see the "presenting" effect in EditorPage).
 */
export default function PresentPage() {
  const { id } = useParams();
  const [project, setProject] = useState(null);
  const [slides, setSlides] = useState([]);
  const [error, setError] = useState(null);
  const [state, setState] = useState({ index: 0, stage: 0, reveal: false });
  const [connected, setConnected] = useState(false);
  const channelRef = useRef(null);

  useEffect(() => {
    document.title = 'Màn hình khán giả — LecGen';
    let cancelled = false;
    (async () => {
      try {
        const proj = await projectService.getById(id);
        const pages = await projectService.getSlidePages(id);
        if (cancelled) return;
        setProject(proj);
        setSlides(formatSlideDeck(pages || [], proj.presentationMode, isCustomTemplateId(proj.templateId) ? undefined : proj.templateId));
      } catch (err) {
        if (!cancelled) setError(err.message || 'Không tải được bài trình chiếu');
      }
    })();
    return () => { cancelled = true; };
  }, [id]);

  useEffect(() => {
    const channel = new BroadcastChannel(`lecgen-present-${id}`);
    channelRef.current = channel;
    channel.onmessage = (event) => {
      const message = event.data || {};
      if (message.type !== 'goto') return;
      setConnected(true);
      setState({ index: message.index, stage: message.stage || 0, reveal: Boolean(message.reveal) });
    };
    channel.postMessage({ type: 'request-state' });
    const retry = setTimeout(() => channel.postMessage({ type: 'request-state' }), 800);
    return () => {
      clearTimeout(retry);
      channel.close();
    };
  }, [id]);

  useEffect(() => {
    const onKey = (event) => {
      if (['ArrowRight', 'ArrowDown', 'PageDown', ' '].includes(event.key)) channelRef.current?.postMessage({ type: 'next' });
      else if (['ArrowLeft', 'ArrowUp', 'PageUp'].includes(event.key)) channelRef.current?.postMessage({ type: 'prev' });
      else return;
      event.preventDefault();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  if (error) return <div className="aud-page aud-msg">{error}</div>;
  if (!project) return <div className="aud-page aud-msg">Đang tải bài trình chiếu…</div>;

  const deckMaster = parseDeckMaster(project.deckMaster);
  const slide = slides[state.index];

  return (
    <div className="aud-page" onClick={() => channelRef.current?.postMessage({ type: 'next' })}>
      <div className="aud-stage">
        <SlideTransition slideKey={state.index} transition={deckMaster.transition}>
          <FittedSlide
            slide={slide}
            theme={project.templateId}
            index={state.index}
            revealStage={state.reveal ? state.stage : null}
          />
        </SlideTransition>
      </div>
      {!connected && <div className="aud-wait">Đang chờ người thuyết trình…</div>}
      <button
        type="button"
        className="aud-full"
        title="Toàn màn hình"
        onClick={(event) => { event.stopPropagation(); document.documentElement.requestFullscreen?.().catch(() => {}); }}
      >
        <Maximize2 size={16} />
      </button>
    </div>
  );
}
