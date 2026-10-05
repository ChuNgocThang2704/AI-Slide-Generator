import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Clapperboard, Download, FileUp, Loader2, Plus, RefreshCw, Sparkles, Trash2, Wand2, X,
} from 'lucide-react';
import { useUIStore } from '../../store';
import { lectureScriptService } from '../../services/lectureScriptService';
import {
  countWords, estimatedMinutes, firstShownNumber, renumberRows, safeFileName, totalWords,
} from '../../utils/lectureScript';
import './ScriptPage.css';

const MAX_FILE_BYTES = 50 * 1024 * 1024;
const DRAFT_KEY = 'lecgen:lecture-script-draft';
const PROMPT_HINTS = [
  'Giảng viên là nữ, xưng "cô" và gọi "các em"',
  'Đây là môn …, video thuộc Chương …',
  'Mỗi slide nói ngắn hơn, khoảng 60 từ',
  'Thêm ví dụ thực tế gần gũi với sinh viên',
];

// What a row is, whatever the user renames it to: the opening, the closing, one slide, or a scene they added.
const kindOf = (row) => {
  if (row.kind) return row.kind;
  if (Number.isInteger(row.slide) && row.scene !== 'Lời mở đầu') return 'slide';
  if (row.scene === 'Lời mở đầu') return 'intro';
  if (row.scene === 'Lời kết') return 'outro';
  return 'extra';
};
const withKinds = (rows) => (rows || []).map((row) => ({ ...row, kind: kindOf(row) }));
const keyOf = (row) => (row.kind === 'slide' ? `slide-${row.slide}` : row.kind);

const readDraft = () => {
  try {
    const draft = JSON.parse(sessionStorage.getItem(DRAFT_KEY) || 'null');
    return draft && Array.isArray(draft.rows) && draft.rows.length ? draft : null;
  } catch {
    return null;
  }
};

function ScriptCell({ value, onChange, label }) {
  const ref = useRef(null);
  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    node.style.height = 'auto';
    node.style.height = `${node.scrollHeight + 2}px`;
  }, [value]);
  return <textarea ref={ref} className="sp-script" value={value} aria-label={label} onChange={(event) => onChange(event.target.value)} />;
}

export default function ScriptPage() {
  const { addToast } = useUIStore();
  const [initialDraft] = useState(readDraft);
  const [file, setFile] = useState(null);
  const [prompt, setPrompt] = useState('');
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(null);            // 'write' | 'revise' | 'export' | null
  const [progress, setProgress] = useState(0);
  const [title, setTitle] = useState(initialDraft?.title || '');
  const [rows, setRows] = useState(() => withKinds(initialDraft?.rows));
  const [slides, setSlides] = useState(initialDraft?.slides || []);
  const [fileName, setFileName] = useState(initialDraft?.fileName || '');
  const [revisePrompt, setRevisePrompt] = useState('');
  const runRef = useRef(0);
  const inputRef = useRef(null);

  const hasScript = rows.length > 0;
  const words = useMemo(() => totalWords(rows), [rows]);
  const minutes = useMemo(() => estimatedMinutes(rows), [rows]);
  const firstNumber = useMemo(() => firstShownNumber(rows), [rows]);
  const emptyRows = rows.filter((row) => !String(row.script || '').trim()).length;

  useEffect(() => () => { runRef.current += 1; }, []);

  // A reviewed script survives an accidental reload of the tab.
  useEffect(() => {
    try {
      if (hasScript) sessionStorage.setItem(DRAFT_KEY, JSON.stringify({ title, rows, slides, fileName }));
      else sessionStorage.removeItem(DRAFT_KEY);
    } catch {
      // storage is a convenience only
    }
  }, [hasScript, title, rows, slides, fileName]);

  const chooseFile = (candidate) => {
    if (!candidate) return;
    if (!/\.(pptx|pdf)$/i.test(candidate.name)) {
      addToast('Chỉ hỗ trợ file .pptx hoặc .pdf', 'error');
      return;
    }
    if (candidate.size > MAX_FILE_BYTES) {
      addToast('Dung lượng file tối đa là 50 MB', 'error');
      return;
    }
    setFile(candidate);
  };

  const run = async (kind, start) => {
    const token = runRef.current + 1;
    runRef.current = token;
    setBusy(kind);
    setProgress(3);
    try {
      const { task_id: taskId } = await start();
      const result = await lectureScriptService.waitFor(taskId, setProgress, () => runRef.current !== token);
      if (runRef.current !== token) return null;
      return result;
    } catch (error) {
      if (runRef.current === token && error.message !== 'cancelled') addToast(error.message || 'Không tạo được kịch bản', 'error');
      return null;
    } finally {
      if (runRef.current === token) setBusy(null);
    }
  };

  const writeScript = async () => {
    if (!file || busy) return;
    const result = await run('write', () => lectureScriptService.start(file, prompt));
    if (!result?.script) return;
    setTitle(result.script.title || file.name.replace(/\.(pptx|pdf)$/i, ''));
    setRows(withKinds(result.script.rows));
    setSlides(result.slides || []);
    setFileName(file.name);
    setRevisePrompt('');
    if (result.script.missing?.length) addToast(`Chưa viết được: ${result.script.missing.join(', ')}. Bạn có thể tự điền hoặc yêu cầu viết lại.`, 'warning');
  };

  const reviseScript = async () => {
    if (!revisePrompt.trim() || busy) return;
    // The server recognises the opening and closing by their standard names, whatever they are called here.
    const sent = rows.filter((row) => row.kind !== 'extra').map((row) => ({
      scene: row.kind === 'intro' ? 'Lời mở đầu' : row.kind === 'outro' ? 'Lời kết' : `Slide ${row.slide}`,
      slide: row.kind === 'slide' ? row.slide : null,
      script: row.script,
      note: row.note || '',
    }));
    const result = await run('revise', () => lectureScriptService.revise({ slides, rows: sent, prompt: revisePrompt, filename: fileName }));
    if (!result?.script) return;
    // Labels, notes and the scenes the user added stay; only the spoken text is replaced.
    const rewritten = new Map(withKinds(result.script.rows).map((row) => [keyOf(row), row.script]));
    setRows((current) => current.map((row) => (
      row.kind !== 'extra' && rewritten.get(keyOf(row)) ? { ...row, script: rewritten.get(keyOf(row)) } : row
    )));
    setRevisePrompt('');
    addToast('Đã viết lại theo yêu cầu', 'success');
  };

  const exportXlsx = async () => {
    if (!hasScript || busy) return;
    setBusy('export');
    try {
      const blob = await lectureScriptService.exportXlsx({ title, durationMinutes: minutes, rows });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = safeFileName(title);
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 2000);
      addToast('Đã xuất file Excel', 'success');
    } catch (error) {
      addToast(error.message || 'Không xuất được file Excel', 'error');
    } finally {
      setBusy(null);
    }
  };

  const updateRow = (index, patch) => setRows((current) => current.map((row, position) => (position === index ? { ...row, ...patch } : row)));
  const removeRow = (index) => setRows((current) => current.filter((_, position) => position !== index));
  const addRowAfter = (index) => setRows((current) => [
    ...current.slice(0, index + 1),
    { scene: 'Lời tiếp theo', slide: null, kind: 'extra', script: '', note: 'Hình ảnh GV' },
    ...current.slice(index + 1),
  ]);

  const startOver = () => {
    runRef.current += 1;
    setBusy(null);
    setRows([]);
    setSlides([]);
    setTitle('');
    setFile(null);
    setFileName('');
    setRevisePrompt('');
  };

  const working = busy === 'write' || busy === 'revise';

  return (
    <div className="sp-page page-enter">
      <div className="container sp-container">
        <header className="sp-header">
          <div>
            <h1 className="sp-title"><Clapperboard size={26} /> Kịch bản <span className="gradient-text">bài giảng</span></h1>
            <p className="sp-desc">Tải slide có sẵn lên, AI viết lời thoại cho từng slide. Bạn xem và sửa trước, ưng rồi mới xuất file Excel.</p>
          </div>
          {hasScript && (
            <button type="button" className="btn btn-ghost btn-sm" onClick={startOver}>
              <RefreshCw size={14} /> Làm file khác
            </button>
          )}
        </header>

        {!hasScript && (
          <section className="sp-card sp-upload">
            <div
              className={`sp-drop${dragging ? ' dragging' : ''}${file ? ' chosen' : ''}`}
              onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={(event) => { event.preventDefault(); setDragging(false); chooseFile(event.dataTransfer.files?.[0]); }}
              onClick={() => !working && inputRef.current?.click()}
              role="button"
              tabIndex={0}
              onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') inputRef.current?.click(); }}
            >
              <input ref={inputRef} type="file" accept=".pptx,.pdf" hidden onChange={(event) => { chooseFile(event.target.files?.[0]); event.target.value = ''; }} />
              <FileUp size={30} />
              {file ? (
                <>
                  <strong>{file.name}</strong>
                  <span>{(file.size / 1024 / 1024).toFixed(1)} MB · bấm để chọn file khác</span>
                </>
              ) : (
                <>
                  <strong>Kéo thả hoặc bấm để chọn file slide</strong>
                  <span>.pptx hoặc .pdf · tối đa 50 MB, 80 slide</span>
                </>
              )}
            </div>

            <label className="sp-label" htmlFor="sp-prompt">Mô tả thêm <em>(không bắt buộc)</em></label>
            <textarea
              id="sp-prompt"
              className="sp-prompt"
              rows={3}
              maxLength={1500}
              value={prompt}
              disabled={working}
              onChange={(event) => setPrompt(event.target.value)}
              placeholder="Ví dụ: Môn An toàn và Bảo mật HTTT, video thuộc Chương 2. Giảng viên xưng thầy, giọng gần gũi, có câu hỏi gợi mở cho sinh viên."
            />
            <div className="sp-hints">
              {PROMPT_HINTS.map((hint) => (
                <button key={hint} type="button" disabled={working} onClick={() => setPrompt((current) => (current.trim() ? `${current.trim()}. ${hint}` : hint))}>
                  + {hint}
                </button>
              ))}
            </div>

            <button type="button" className="btn btn-primary btn-lg sp-go" disabled={!file || working} onClick={writeScript}>
              {working ? <><Loader2 size={18} className="spin" /> Đang viết kịch bản… {progress}%</> : <><Sparkles size={18} /> Tạo kịch bản</>}
            </button>
            {working && <div className="sp-bar"><i style={{ width: `${Math.max(4, progress)}%` }} /></div>}
            <p className="sp-note">Mặc định theo văn phong bài giảng video: giảng viên xưng “thầy”, gọi “các em”, mỗi slide khoảng 80–110 từ. File chỉ được đọc để viết kịch bản, không lưu lại.</p>
          </section>
        )}

        {hasScript && (
          <>
            <section className="sp-card sp-meta">
              <div className="sp-field sp-field-title">
                <label htmlFor="sp-title">Tên video / bài giảng</label>
                <input id="sp-title" value={title} maxLength={200} onChange={(event) => setTitle(event.target.value)} />
              </div>
              <div className="sp-field sp-field-num">
                <label htmlFor="sp-first">Slide bắt đầu từ số</label>
                <input
                  id="sp-first"
                  type="number"
                  min={1}
                  max={999}
                  value={firstNumber ?? ''}
                  disabled={firstNumber === null}
                  title="Dùng khi video là một phần của bộ slide dài (ví dụ video này bắt đầu từ Slide 27)"
                  onChange={(event) => {
                    const next = Number.parseInt(event.target.value, 10);
                    if (Number.isInteger(next) && next >= 1) setRows((current) => renumberRows(current, next));
                  }}
                />
              </div>
              <div className="sp-stats">
                <span><b>{rows.length}</b> phân cảnh</span>
                <span><b>{words.toLocaleString('vi-VN')}</b> từ</span>
                <span>≈ <b>{minutes}</b> phút</span>
              </div>
            </section>

            <section className="sp-card sp-revise">
              <Wand2 size={18} />
              <input
                value={revisePrompt}
                maxLength={1500}
                disabled={Boolean(busy)}
                onChange={(event) => setRevisePrompt(event.target.value)}
                onKeyDown={(event) => { if (event.key === 'Enter') reviseScript(); }}
                placeholder="Muốn chỉnh gì? Ví dụ: viết ngắn hơn, thêm ví dụ thực tế, đổi xưng hô thành cô – các bạn…"
                aria-label="Yêu cầu chỉnh sửa kịch bản"
              />
              <button type="button" className="btn btn-secondary btn-sm" disabled={!revisePrompt.trim() || Boolean(busy)} onClick={reviseScript}>
                {busy === 'revise' ? <><Loader2 size={14} className="spin" /> {progress}%</> : 'Viết lại theo yêu cầu'}
              </button>
            </section>

            <section className={`sp-card sp-table${busy === 'revise' ? ' dim' : ''}`}>
              <div className="sp-row sp-head">
                <div>PHÂN CẢNH</div>
                <div>LỜI THOẠI</div>
                <div>LƯU Ý DỰNG</div>
                <div />
              </div>
              {rows.map((row, index) => (
                <div className="sp-row" key={`${keyOf(row)}-${index}`}>
                  <div>
                    <input className="sp-scene" value={row.scene} maxLength={60} aria-label="Phân cảnh" onChange={(event) => updateRow(index, { scene: event.target.value })} />
                    <small className={countWords(row.script) ? '' : 'warn'}>{countWords(row.script) ? `${countWords(row.script)} từ` : 'Chưa có lời thoại'}</small>
                  </div>
                  <div>
                    <ScriptCell value={row.script} label={`Lời thoại ${row.scene}`} onChange={(value) => updateRow(index, { script: value })} />
                  </div>
                  <div>
                    <input className="sp-notecell" value={row.note || ''} maxLength={200} aria-label="Lưu ý dựng" placeholder="—" onChange={(event) => updateRow(index, { note: event.target.value })} />
                  </div>
                  <div className="sp-rowtools">
                    <button type="button" title="Thêm phân cảnh bên dưới" onClick={() => addRowAfter(index)}><Plus size={14} /></button>
                    <button type="button" title="Xoá phân cảnh này" disabled={rows.length <= 1} onClick={() => removeRow(index)}><Trash2 size={14} /></button>
                  </div>
                </div>
              ))}
            </section>

            <footer className="sp-footer">
              <span>
                {emptyRows > 0
                  ? <><X size={14} /> Còn {emptyRows} phân cảnh chưa có lời thoại</>
                  : 'Kiểm tra xong thì xuất file. File Excel có 3 cột như trên, đúng mẫu kịch bản dựng.'}
              </span>
              <button type="button" className="btn btn-primary btn-lg" disabled={Boolean(busy)} onClick={exportXlsx}>
                {busy === 'export' ? <Loader2 size={18} className="spin" /> : <Download size={18} />} Xuất Excel
              </button>
            </footer>
          </>
        )}
      </div>
    </div>
  );
}
