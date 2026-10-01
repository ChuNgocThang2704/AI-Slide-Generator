import { useEffect, useRef, useState } from 'react';
import { AlertTriangle, HelpCircle } from 'lucide-react';
import { subscribeDialogs } from '../../services/dialogService';
import './DialogHost.css';

/** Mount once near the app root; renders whichever confirm/prompt dialog is currently open. */
export default function DialogHost() {
  const [dialog, setDialog] = useState(null);
  const [value, setValue] = useState('');
  const inputRef = useRef(null);

  useEffect(() => subscribeDialogs((next) => {
    setValue(next.defaultValue || '');
    setDialog(next);
  }), []);

  useEffect(() => {
    if (dialog?.kind === 'prompt') inputRef.current?.select();
  }, [dialog]);

  useEffect(() => {
    if (!dialog) return undefined;
    const onKey = (event) => { if (event.key === 'Escape') finish(false); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  if (!dialog) return null;

  function finish(ok) {
    const isPrompt = dialog.kind === 'prompt';
    dialog.resolve(isPrompt ? (ok ? value : null) : ok);
    setDialog(null);
  }

  const Icon = dialog.danger ? AlertTriangle : HelpCircle;
  return (
    <div className="dlg-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) finish(false); }}>
      <form
        className="dlg"
        role="dialog"
        aria-modal="true"
        aria-label={dialog.title}
        onSubmit={(event) => { event.preventDefault(); finish(true); }}
      >
        <div className="dlg-head">
          <span className={`dlg-icon${dialog.danger ? ' danger' : ''}`}><Icon size={18} /></span>
          <h3>{dialog.title}</h3>
        </div>
        {dialog.message && <p className="dlg-msg">{dialog.message}</p>}
        {dialog.kind === 'prompt' && (
          <input
            ref={inputRef}
            className="dlg-input"
            value={value}
            placeholder={dialog.placeholder}
            onChange={(event) => setValue(event.target.value)}
            maxLength={120}
            autoFocus
          />
        )}
        <div className="dlg-actions">
          <button type="button" className="dlg-btn" onClick={() => finish(false)}>{dialog.cancelLabel}</button>
          <button type="submit" className={`dlg-btn primary${dialog.danger ? ' danger' : ''}`} autoFocus={dialog.kind === 'confirm'}>
            {dialog.confirmLabel}
          </button>
        </div>
      </form>
    </div>
  );
}
