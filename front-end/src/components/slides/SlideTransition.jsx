import './SlideTransition.css';

/**
 * Plays a slide-change effect when `slideKey` changes (the child is re-mounted, so the CSS
 * animation runs once per slide). With transition 'none', the PowerPoint default, it adds
 * nothing at all.
 */
export default function SlideTransition({ slideKey, transition = 'none', children }) {
  const effect = ['fade', 'push', 'zoom'].includes(transition) ? transition : 'none';
  return (
    <div key={slideKey} className={effect === 'none' ? undefined : `slide-tx slide-tx-${effect}`}>
      {children}
    </div>
  );
}
