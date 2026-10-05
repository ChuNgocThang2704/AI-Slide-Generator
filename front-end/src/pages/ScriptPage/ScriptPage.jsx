import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle, ArrowLeft, Check, Clapperboard, Cloud, CloudOff, Download, FileUp, FolderOpen, Languages, Loader2, Plus, RotateCw,
  Search, Sparkles, Trash2, Wand2, X,
} from 'lucide-react';
import { useUIStore } from '../../store';
import { confirmDialog } from '../../services/dialogService';
import { lectureScriptService } from '../../services/lectureScriptService';
import {
  byFileName, countWords, englishStatus, estimatedMinutes, firstShownNumber, renumberRows, rowsToTranslate, safeFileName,
  sheetNameFromFile, suggestedSetName, totalWords,
} from '../../utils/lectureScript';
import './ScriptPage.css';

const MAX_FILE_BYTES = 50 * 1024 * 1024;
const MAX_FILES = 20;
const PARALLEL_FILES = 2;       // files written at the same time; the rest wait their turn
const OPEN_SET_KEY = 'lecgen:lecture-script-open-set';
const SAVE_DELAY_MS = 1200;
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
const newId = () => `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;

// The set being worked on is reopened after a reload of the tab.
const rememberedSetId = () => {
  try {
    return sessionStorage.getItem(OPEN_SET_KEY) || null;
  } catch {
    return null;
  }
};
const rememberSetId = (id) => {
  try {
    if (id) sessionStorage.setItem(OPEN_SET_KEY, id);
    else sessionStorage.removeItem(OPEN_SET_KEY);
  } catch {
    // storage is a convenience only
  }
};
const savedItems = (items) => items.map(({ id, fileName, sheet, title, rows, slides, missing }) => ({
  id, fileName, sheet, title, rows, slides, missing: missing || [],
}));
const formatDate = (value) => {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleString('vi-VN', { dateStyle: 'short', timeStyle: 'short' });
};

function ScriptCell({ value, onChange, label, className = 'sp-script' }) {
  const ref = useRef(null);
  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    node.style.height = 'auto';
    node.style.height = `${node.scrollHeight + 2}px`;
  }, [value]);
  return <textarea ref={ref} className={className} value={value} aria-label={label} onChange={(event) => onChange(event.target.value)} />;
}

export default function ScriptPage() {
  const { addToast } = useUIStore();
  const [picked, setPicked] = useState([]);                 // files chosen, not yet started
  const [prompt, setPrompt] = useState('');
  const [dragging, setDragging] = useState(false);
  const [autoEnglish, setAutoEnglish] = useState(true);      // translate each script into English as soon as it is written
  const [firstVideo, setFirstVideo] = useState(false);       // the first file opens the course: welcome, lecturer, course
  const [items, setItems] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [revisePrompt, setRevisePrompt] = useState('');
  const [exporting, setExporting] = useState(false);
  const [withEnglish, setWithEnglish] = useState(true);       // the English column goes into the Excel when there is English
  // Saved sets: the list, and the one open in the workspace.
  const [sets, setSets] = useState([]);
  const [setsLoading, setSetsLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [opening, setOpening] = useState(() => Boolean(rememberedSetId()));
  const [setName, setSetName] = useState('');
  const [savedText, setSavedText] = useState('');           // what the server holds, as sent
  const [saving, setSaving] = useState(false);
  const [saveFailed, setSaveFailed] = useState(false);
  const setIdRef = useRef(null);
  const savingRef = useRef(false);
  const sessionRef = useRef(0);         // bumped by "start over": answers of an older run are dropped
  const itemsRef = useRef([]);          // the latest items, for work that outlives a render
  const filesRef = useRef(new Map());   // id -> File, kept in memory so a failed file can be retried
  const autoEnglishRef = useRef(true);
  const firstRef = useRef(new Set());   // ids of the file that opens the course
  const queueRef = useRef([]);          // ids waiting for a free slot
  const runningRef = useRef(0);
  const promptRef = useRef(prompt);
  const inputRef = useRef(null);
  const addInputRef = useRef(null);

  useEffect(() => { promptRef.current = prompt; }, [prompt]);
  useEffect(() => { itemsRef.current = items; }, [items]);
  useEffect(() => { autoEnglishRef.current = autoEnglish; }, [autoEnglish]);
  useEffect(() => () => { sessionRef.current += 1; }, []);

  const started = items.length > 0 || opening;
  const active = items.find((item) => item.id === activeId) || items[0] || null;
  const done = useMemo(() => items.filter((item) => item.status === 'done'), [items]);
  const working = items.some((item) => item.status === 'queued' || item.status === 'writing' || item.revising || item.translating);
  const anyEnglish = done.some((item) => item.rows.some((row) => String(row.en || '').trim()));
  const rows = useMemo(() => (active?.status === 'done' ? active.rows : []), [active]);
  const words = useMemo(() => totalWords(rows), [rows]);
  const minutes = useMemo(() => estimatedMinutes(rows), [rows]);
  const firstNumber = useMemo(() => firstShownNumber(rows), [rows]);
  const emptyRows = done.reduce((sum, item) => sum + item.rows.filter((row) => !String(row.script || '').trim()).length, 0);

  // What is kept on the server: the finished scripts only (a file still being read cannot be resumed).
  const payload = useMemo(() => (done.length
    ? { name: setName.trim() || suggestedSetName(done), prompt, items: savedItems(done) }
    : null), [done, setName, prompt]);
  const payloadText = useMemo(() => (payload ? JSON.stringify(payload) : ''), [payload]);
  const unsaved = Boolean(payloadText) && payloadText !== savedText;

  const refreshSets = useCallback(async () => {
    try {
      setSets(await lectureScriptService.listSets());
    } catch {
      // the list is not worth an error toast on its own; opening or saving will report a real problem
    } finally {
      setSetsLoading(false);
    }
  }, []);

  const saveNow = useCallback(async (body, text) => {
    if (savingRef.current) return false;
    const session = sessionRef.current;
    savingRef.current = true;
    setSaving(true);
    try {
      const row = await lectureScriptService.saveSet(setIdRef.current, body);
      if (sessionRef.current !== session) return true;
      setIdRef.current = row.id;
      rememberSetId(row.id);
      setSavedText(text);
      setSaveFailed(false);
      return true;
    } catch {
      if (sessionRef.current === session) setSaveFailed(true);
      return false;
    } finally {
      savingRef.current = false;
      if (sessionRef.current === session) setSaving(false);
    }
  }, []);

  // Changes are saved by themselves a moment after the last one.
  useEffect(() => {
    if (!unsaved || saving) return undefined;
    const timer = setTimeout(() => { saveNow(payload, payloadText); }, SAVE_DELAY_MS);
    return () => clearTimeout(timer);
  }, [unsaved, saving, payload, payloadText, saveNow]);

  const openSet = useCallback(async (id) => {
    // (The caller shows the "opening" state: on mount it is already on.)
    const session = sessionRef.current;
    try {
      const set = await lectureScriptService.getSet(id);
      if (sessionRef.current !== session) return;
      const opened = (set.items || []).filter((item) => item?.rows?.length).map((item) => ({
        ...item, status: 'done', progress: 100, error: '', canRetry: false, revising: false, translating: false, rows: withKinds(item.rows),
      }));
      setIdRef.current = set.id;
      rememberSetId(set.id);
      setSetName(set.name || '');
      setPrompt(set.prompt || '');
      setItems(opened);
      setActiveId(opened[0]?.id || null);
      // What was just loaded is what the server holds: opening a set must not save it again.
      setSavedText(JSON.stringify({ name: set.name || suggestedSetName(opened), prompt: set.prompt || '', items: savedItems(opened) }));
      setSaveFailed(false);
    } catch (error) {
      if (sessionRef.current !== session) return;
      rememberSetId(null);
      addToast(error.message || 'Không mở được bộ kịch bản', 'error');
      refreshSets();
    } finally {
      if (sessionRef.current === session) setOpening(false);
    }
  }, [addToast, refreshSets]);

  // On arrival: the set that was open before a reload comes back, otherwise the list is shown.
  useEffect(() => {
    const timer = setTimeout(() => {
      const remembered = rememberedSetId();
      if (remembered) openSet(remembered);
      else refreshSets();
    }, 0);
    return () => clearTimeout(timer);
  }, [openSet, refreshSets]);

  const patchItem = useCallback((id, patch) => {
    setItems((current) => current.map((item) => (item.id === id ? { ...item, ...(typeof patch === 'function' ? patch(item) : patch) } : item)));
  }, []);

  const accept = (list) => {
    const good = [];
    for (const candidate of Array.from(list || [])) {
      if (!/\.(pptx|pdf)$/i.test(candidate.name)) addToast(`${candidate.name}: chỉ hỗ trợ file .pptx hoặc .pdf`, 'error');
      else if (candidate.size > MAX_FILE_BYTES) addToast(`${candidate.name}: dung lượng tối đa là 50 MB`, 'error');
      else good.push(candidate);
    }
    return good;
  };

  const choose = (list) => {
    const good = accept(list);
    if (!good.length) return;
    setPicked((current) => {
      const names = new Set(current.map((file) => file.name));
      const merged = [...current, ...good.filter((file) => !names.has(file.name))].sort((a, b) => byFileName(a.name, b.name));
      if (merged.length > MAX_FILES) addToast(`Mỗi lần tối đa ${MAX_FILES} file`, 'warning');
      return merged.slice(0, MAX_FILES);
    });
  };

  // Only refs and the stable patchItem are used, so a run started by an older render stays correct.
  function pump() {
    while (runningRef.current < PARALLEL_FILES && queueRef.current.length) {
      const id = queueRef.current.shift();
      const file = filesRef.current.get(id);
      if (!file) continue;
      const session = sessionRef.current;
      runningRef.current += 1;
      patchItem(id, { status: 'writing', progress: 3, error: '' });
      (async () => {
        try {
          const { task_id: taskId } = await lectureScriptService.start(file, promptRef.current, firstRef.current.has(id));
          const result = await lectureScriptService.waitFor(
            taskId,
            (value) => { if (sessionRef.current === session) patchItem(id, { progress: value }); },
            () => sessionRef.current !== session,
          );
          if (sessionRef.current !== session) return;
          const written = withKinds(result.script.rows);
          const sheet = sheetNameFromFile(file.name);
          patchItem(id, {
            status: 'done', progress: 100, slides: result.slides || [],
            title: result.script.title || sheet,
            rows: written,
            missing: result.script.missing || [],
          });
          // The English subtitle lines follow right behind the Vietnamese script.
          if (autoEnglishRef.current) translateItem(id, { rows: written, sheet });
        } catch (error) {
          if (sessionRef.current === session && error.message !== 'cancelled') {
            patchItem(id, { status: 'error', error: error.message || 'Không tạo được kịch bản' });
          }
        } finally {
          if (sessionRef.current === session) {
            runningRef.current -= 1;
            pump();
          }
        }
      })();
    }
  }

  const enqueue = (files, opensCourse = false) => {
    const fresh = files.map((file, index) => {
      const id = newId();
      filesRef.current.set(id, file);
      if (opensCourse && index === 0) firstRef.current.add(id);
      return { id, fileName: file.name, sheet: sheetNameFromFile(file.name), status: 'queued', progress: 0, error: '', title: '', rows: [], slides: [], canRetry: true };
    });
    if (!fresh.length) return;
    setItems((current) => [...current, ...fresh].slice(0, MAX_FILES));
    setActiveId((current) => current || fresh[0].id);
    queueRef.current.push(...fresh.map((item) => item.id));
    pump();
  };

  const startAll = () => {
    if (!picked.length) return;
    enqueue(picked, firstVideo);
    setPicked([]);
  };

  const addMore = (list) => {
    const have = new Set(items.map((item) => item.fileName));
    const good = accept(list).filter((file) => !have.has(file.name)).sort((a, b) => byFileName(a.name, b.name));
    const room = MAX_FILES - items.length;
    if (good.length > room) addToast(`Mỗi lần tối đa ${MAX_FILES} file`, 'warning');
    enqueue(good.slice(0, Math.max(0, room)));
  };

  const retry = (id) => {
    if (!filesRef.current.get(id)) return;
    patchItem(id, { status: 'queued', progress: 0, error: '' });
    queueRef.current.push(id);
    pump();
  };

  const removeItem = (id) => {
    queueRef.current = queueRef.current.filter((queued) => queued !== id);
    filesRef.current.delete(id);
    const next = items.filter((item) => item.id !== id);
    setItems(next);
    if (id === active?.id) setActiveId(next[0]?.id || null);
  };

  const backToList = async () => {
    if (working && !(await confirmDialog({
      title: 'Về danh sách',
      message: 'Còn file đang viết dở. Về danh sách bây giờ thì các file đó bị bỏ; các file đã xong vẫn được lưu.',
      confirmLabel: 'Về danh sách',
    }))) return;
    if (unsaved) await saveNow(payload, payloadText);
    sessionRef.current += 1;
    queueRef.current = [];
    runningRef.current = 0;
    savingRef.current = false;
    filesRef.current.clear();
    firstRef.current.clear();
    setIdRef.current = null;
    rememberSetId(null);
    setSetName('');
    setSavedText('');
    setSaving(false);
    setSaveFailed(false);
    setItems([]);
    setActiveId(null);
    setPicked([]);
    setPrompt('');
    setRevisePrompt('');
    setSetsLoading(true);
    refreshSets();
  };

  const deleteSet = async (set) => {
    if (!(await confirmDialog({
      title: 'Xoá bộ kịch bản',
      message: `Xoá “${set.name}” (${set.itemCount} kịch bản)? Không khôi phục lại được.`,
      confirmLabel: 'Xoá',
      danger: true,
    }))) return;
    try {
      await lectureScriptService.deleteSet(set.id);
      setSets((current) => current.filter((item) => item.id !== set.id));
      addToast('Đã xoá bộ kịch bản', 'success');
    } catch (error) {
      addToast(error.message || 'Không xoá được', 'error');
    }
  };

  const shownSets = sets.filter((set) => set.name.toLowerCase().includes(search.trim().toLowerCase()));

  const reviseActive = async () => {
    const target = active;
    const request = revisePrompt.trim();
    if (!target || target.status !== 'done' || target.revising || !request) return;
    const session = sessionRef.current;
    patchItem(target.id, { revising: true, progress: 3 });
    // The server recognises the opening and closing by their standard names, whatever they are called here.
    const sent = target.rows.filter((row) => row.kind !== 'extra').map((row) => ({
      scene: row.kind === 'intro' ? 'Lời mở đầu' : row.kind === 'outro' ? 'Lời kết' : `Slide ${row.slide}`,
      slide: row.kind === 'slide' ? row.slide : null,
      script: row.script,
      note: row.note || '',
    }));
    try {
      const { task_id: taskId } = await lectureScriptService.revise({ slides: target.slides, rows: sent, prompt: request, filename: target.fileName });
      const result = await lectureScriptService.waitFor(
        taskId,
        (value) => { if (sessionRef.current === session) patchItem(target.id, { progress: value }); },
        () => sessionRef.current !== session,
      );
      if (sessionRef.current !== session) return;
      // Labels, notes and the scenes the user added stay; only the spoken text is replaced.
      const rewritten = new Map(withKinds(result.script.rows).map((row) => [keyOf(row), row.script]));
      patchItem(target.id, (item) => ({
        revising: false,
        rows: item.rows.map((row) => (row.kind !== 'extra' && rewritten.get(keyOf(row)) ? { ...row, script: rewritten.get(keyOf(row)) } : row)),
      }));
      setRevisePrompt('');
      addToast(`Đã viết lại “${target.sheet}” theo yêu cầu`, 'success');
    } catch (error) {
      if (sessionRef.current !== session) return;
      patchItem(target.id, { revising: false });
      if (error.message !== 'cancelled') addToast(error.message || 'Không viết lại được', 'error');
    }
  };

  // English subtitles: the Vietnamese rows that have none (or changed since) are translated paragraph by paragraph.
  // `fresh` is for a script that was only just written: the items ref has not caught up with it yet.
  async function translateItem(id, fresh) {
    const target = fresh ? { rows: fresh.rows, sheet: fresh.sheet }
      : itemsRef.current.find((item) => item.id === id && item.status === 'done' && !item.translating && !item.revising);
    if (!target) return 0;
    const needed = rowsToTranslate(target.rows);
    if (!needed.length) return 0;
    const session = sessionRef.current;
    patchItem(id, { translating: true, progress: 3 });
    try {
      const { task_id: taskId } = await lectureScriptService.translate(needed.map((row) => row.script));
      const result = await lectureScriptService.waitFor(
        taskId,
        (value) => { if (sessionRef.current === session) patchItem(id, { progress: value }); },
        () => sessionRef.current !== session,
      );
      if (sessionRef.current !== session) return 0;
      const english = new Map((result.items || []).map((entry) => [needed[entry.i]?.i, { en: entry.en, enFor: needed[entry.i]?.script }]));
      patchItem(id, (item) => ({
        translating: false,
        rows: item.rows.map((row, index) => (english.has(index) ? { ...row, ...english.get(index) } : row)),
      }));
      if (result.failed?.length) addToast(`“${target.sheet}”: ${result.failed.length} dòng chưa dịch được, bấm dịch lại để thử tiếp`, 'warning');
      return english.size;
    } catch (error) {
      if (sessionRef.current !== session) return 0;
      patchItem(id, { translating: false });
      if (error.message !== 'cancelled') addToast(error.message || 'Không dịch được', 'error');
      return 0;
    }
  }

  const translateActive = async () => {
    if (!active) return;
    const count = await translateItem(active.id);
    if (count) addToast(`Đã dịch ${count} dòng sang tiếng Anh`, 'success');
  };

  const translateAll = async () => {
    const ids = done.map((item) => item.id);
    let total = 0;
    const queue = [...ids];
    const worker = async () => {
      while (queue.length) total += await translateItem(queue.shift());
    };
    await Promise.all([worker(), worker()]);     // two files at a time
    if (total) addToast(`Đã dịch ${total} dòng sang tiếng Anh`, 'success');
  };

  const exportXlsx = async (list) => {
    if (!list.length || exporting) return;
    setExporting(true);
    try {
      const blob = await lectureScriptService.exportXlsx(list.map((item) => ({
        title: item.title, sheet: item.sheet, durationMinutes: estimatedMinutes(item.rows), rows: item.rows, withEnglish,
      })));
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = safeFileName(list.length === 1 ? list[0].title : (setName.trim() || suggestedSetName(list)));
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 2000);
      addToast(list.length === 1 ? 'Đã xuất file Excel' : `Đã xuất file Excel gồm ${list.length} sheet`, 'success');
    } catch (error) {
      addToast(error.message || 'Không xuất được file Excel', 'error');
    } finally {
      setExporting(false);
    }
  };

  const setRows = (update) => active && patchItem(active.id, (item) => ({ rows: typeof update === 'function' ? update(item.rows) : update }));
  const updateRow = (index, patch) => setRows((current) => current.map((row, position) => (position === index ? { ...row, ...patch } : row)));
  const removeRow = (index) => setRows((current) => current.filter((_, position) => position !== index));
  const addRowAfter = (index) => setRows((current) => [
    ...current.slice(0, index + 1),
    { scene: 'Lời tiếp theo', slide: null, kind: 'extra', script: '', note: '' },
    ...current.slice(index + 1),
  ]);

  return (
    <div className="sp-page page-enter">
      <div className="container sp-container">
        <header className="sp-header">
          <div>
            <h1 className="sp-title"><Clapperboard size={26} /> Kịch bản <span className="gradient-text">bài giảng</span></h1>
            <p className="sp-desc">Tải slide có sẵn lên (một hoặc nhiều file), AI viết lời thoại cho từng slide. Bạn xem và sửa trước, ưng rồi mới xuất file Excel.</p>
          </div>
          {started && !opening && (
            <button type="button" className="btn btn-ghost btn-sm" onClick={backToList}>
              <ArrowLeft size={14} /> Danh sách kịch bản
            </button>
          )}
        </header>

        {opening && (
          <section className="sp-card sp-wait"><Loader2 size={28} className="spin" /><p>Đang mở bộ kịch bản…</p></section>
        )}

        {!started && (
          <section className="sp-card sp-upload">
            <div
              className={`sp-drop${dragging ? ' dragging' : ''}${picked.length ? ' chosen' : ''}`}
              onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={(event) => { event.preventDefault(); setDragging(false); choose(event.dataTransfer.files); }}
              onClick={() => inputRef.current?.click()}
              role="button"
              tabIndex={0}
              onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') inputRef.current?.click(); }}
            >
              <input ref={inputRef} type="file" accept=".pptx,.pdf" multiple hidden onChange={(event) => { choose(event.target.files); event.target.value = ''; }} />
              <FileUp size={30} />
              <strong>{picked.length ? 'Kéo thả hoặc bấm để thêm file' : 'Kéo thả hoặc bấm để chọn file slide'}</strong>
              <span>.pptx hoặc .pdf · chọn được nhiều file cùng lúc (tối đa {MAX_FILES}) · mỗi file tối đa 50 MB, 80 slide</span>
            </div>

            {picked.length > 0 && (
              <ul className="sp-files">
                {picked.map((file) => (
                  <li key={file.name}>
                    <span title={file.name}>{file.name}</span>
                    <small>{(file.size / 1024 / 1024).toFixed(1)} MB</small>
                    <button type="button" title="Bỏ file này" onClick={() => setPicked((current) => current.filter((item) => item !== file))}><X size={14} /></button>
                  </li>
                ))}
              </ul>
            )}

            <label className="sp-label" htmlFor="sp-prompt">Mô tả thêm <em>(không bắt buộc{picked.length > 1 ? ', dùng chung cho mọi file' : ''})</em></label>
            <textarea
              id="sp-prompt"
              className="sp-prompt"
              rows={3}
              maxLength={1500}
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              placeholder="Ví dụ: Môn An toàn và Bảo mật HTTT, video thuộc Chương 2. Giảng viên xưng thầy, giọng gần gũi, có câu hỏi gợi mở cho sinh viên."
            />
            <label className="sp-check">
              <input type="checkbox" checked={autoEnglish} onChange={(event) => setAutoEnglish(event.target.checked)} />
              <span>
                <strong>Dịch luôn sang tiếng Anh (làm phụ đề)</strong>
                <small>Mỗi kịch bản có thêm lời thoại tiếng Anh dịch từ tiếng Việt, đối chiếu từng đoạn. Cột tiếng Anh nằm ở cột D trong file Excel; bỏ tick thì dịch sau bằng nút trong từng kịch bản.</small>
              </span>
            </label>
            <label className="sp-check">
              <input type="checkbox" checked={firstVideo} onChange={(event) => setFirstVideo(event.target.checked)} />
              <span>
                <strong>File đầu tiên là video mở đầu học phần</strong>
                <small>Chỉ video này chào mừng, giới thiệu giảng viên và học phần (theo slide bìa). Các video còn lại chỉ chào ngắn rồi nói phần này học gì.</small>
              </span>
            </label>
            <div className="sp-hints">
              {PROMPT_HINTS.map((hint) => (
                <button key={hint} type="button" onClick={() => setPrompt((current) => (current.trim() ? `${current.trim()}. ${hint}` : hint))}>
                  + {hint}
                </button>
              ))}
            </div>

            <button type="button" className="btn btn-primary btn-lg sp-go" disabled={!picked.length} onClick={startAll}>
              <Sparkles size={18} /> {picked.length > 1 ? `Tạo kịch bản cho ${picked.length} file` : 'Tạo kịch bản'}
            </button>
            <p className="sp-note">Mặc định theo văn phong bài giảng video: giảng viên xưng “thầy”, gọi “các em”, mỗi slide khoảng 80–110 từ. Nhiều file được viết song song, mỗi file thành một sheet trong cùng một file Excel. File slide không được lưu lại; kịch bản và phần chữ đọc từ slide được lưu vào tài khoản của bạn để mở lại sau.</p>
          </section>
        )}

        {!started && (
          <section className="sp-card sp-sets">
            <div className="sp-sets-head">
              <h2><FolderOpen size={18} /> Bộ kịch bản đã lưu {sets.length > 0 && <small>{sets.length}</small>}</h2>
              {sets.length > 4 && (
                <label className="sp-search">
                  <Search size={14} />
                  <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Tìm theo tên…" aria-label="Tìm bộ kịch bản" />
                </label>
              )}
            </div>
            {setsLoading && <p className="sp-sets-empty"><Loader2 size={16} className="spin" /> Đang tải…</p>}
            {!setsLoading && sets.length === 0 && (
              <p className="sp-sets-empty">Chưa có bộ nào. Kịch bản bạn tạo sẽ tự lưu ở đây để mở lại, sửa tiếp hoặc xuất Excel lần nữa.</p>
            )}
            {!setsLoading && sets.length > 0 && shownSets.length === 0 && <p className="sp-sets-empty">Không có bộ nào khớp “{search}”.</p>}
            {!setsLoading && shownSets.length > 0 && (
              <ul className="sp-setlist">
                {shownSets.map((set) => (
                  <li key={set.id}>
                    <button type="button" className="sp-set" onClick={() => { setOpening(true); openSet(set.id); }} title="Mở bộ này">
                      <strong>{set.name}</strong>
                      <span>{set.itemCount} kịch bản · ≈ {set.totalMinutes} phút · {Number(set.totalWords || 0).toLocaleString('vi-VN')} từ</span>
                      <small>Sửa lần cuối {formatDate(set.updatedAt)}</small>
                    </button>
                    <button type="button" className="sp-set-del" title="Xoá bộ này" onClick={() => deleteSet(set)}><Trash2 size={15} /></button>
                  </li>
                ))}
              </ul>
            )}
          </section>
        )}

        {started && !opening && (
          <>
            <section className="sp-setbar">
              <label htmlFor="sp-setname">Tên bộ</label>
              <input
                id="sp-setname"
                value={setName}
                maxLength={200}
                placeholder={done.length ? suggestedSetName(done) : 'Ví dụ: Chương 2'}
                onChange={(event) => setSetName(event.target.value)}
              />
              <span className={`sp-save${saveFailed ? ' failed' : ''}`}>
                {!done.length && 'Sẽ tự lưu khi có kịch bản đầu tiên'}
                {done.length > 0 && saving && <><Loader2 size={13} className="spin" /> Đang lưu…</>}
                {done.length > 0 && !saving && saveFailed && (
                  <button type="button" onClick={() => saveNow(payload, payloadText)}><CloudOff size={13} /> Lưu lỗi · bấm để thử lại</button>
                )}
                {done.length > 0 && !saving && !saveFailed && unsaved && <><Cloud size={13} /> Chưa lưu</>}
                {done.length > 0 && !saving && !saveFailed && !unsaved && <><Cloud size={13} /> Đã lưu</>}
              </span>
            </section>

            <nav className="sp-tabs" aria-label="Các file">
              {items.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={`sp-tab ${item.status}${item.id === active?.id ? ' active' : ''}`}
                  onClick={() => setActiveId(item.id)}
                  title={item.fileName}
                >
                  {item.status === 'done' && !item.revising && <Check size={13} />}
                  {(item.status === 'writing' || item.revising) && <Loader2 size={13} className="spin" />}
                  {item.status === 'queued' && <i className="sp-dot" />}
                  {item.status === 'error' && <AlertTriangle size={13} />}
                  <span>{item.sheet}</span>
                  {item.status === 'writing' && <small>{item.progress}%</small>}
                </button>
              ))}
              {items.length < MAX_FILES && (
                <button type="button" className="sp-tab add" onClick={() => addInputRef.current?.click()} title="Thêm file slide">
                  <Plus size={14} /> Thêm file
                </button>
              )}
              <input ref={addInputRef} type="file" accept=".pptx,.pdf" multiple hidden onChange={(event) => { addMore(event.target.files); event.target.value = ''; }} />
            </nav>

            {active && active.status !== 'done' && (
              <section className="sp-card sp-wait">
                {active.status === 'error' ? (
                  <>
                    <AlertTriangle size={28} className="err" />
                    <strong>{active.fileName}</strong>
                    <p>{active.error}</p>
                    <div className="sp-wait-actions">
                      {active.canRetry && <button type="button" className="btn btn-secondary btn-sm" onClick={() => retry(active.id)}><RotateCw size={14} /> Thử lại</button>}
                      <button type="button" className="btn btn-ghost btn-sm" onClick={() => removeItem(active.id)}><Trash2 size={14} /> Bỏ file này</button>
                    </div>
                  </>
                ) : (
                  <>
                    <Loader2 size={28} className="spin" />
                    <strong>{active.fileName}</strong>
                    <p>{active.status === 'queued' ? 'Đang chờ tới lượt (mỗi lúc viết 2 file)…' : `Đang viết kịch bản… ${active.progress}%`}</p>
                    <div className="sp-bar"><i style={{ width: `${Math.max(4, active.progress)}%` }} /></div>
                    {done.length > 0 && <small>Bạn có thể mở các file đã xong ở thanh phía trên trong lúc chờ.</small>}
                  </>
                )}
              </section>
            )}

            {active?.status === 'done' && (
              <>
                <section className="sp-card sp-meta">
                  <div className="sp-field sp-field-title">
                    <label htmlFor="sp-title">Tên video / bài giảng</label>
                    <input id="sp-title" value={active.title} maxLength={200} onChange={(event) => patchItem(active.id, { title: event.target.value })} />
                  </div>
                  <div className="sp-field sp-field-sheet">
                    <label htmlFor="sp-sheet">Tên sheet</label>
                    <input id="sp-sheet" value={active.sheet} maxLength={31} onChange={(event) => patchItem(active.id, { sheet: event.target.value.replace(/[[\]:*?/\\]/g, '') })} />
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
                    <button type="button" title="Bỏ file này khỏi danh sách" onClick={() => removeItem(active.id)}><Trash2 size={14} /></button>
                  </div>
                </section>

                {active.missing?.length > 0 && rows.some((row) => !String(row.script || '').trim()) && (
                  <p className="sp-missing"><AlertTriangle size={14} /> Chưa viết được {active.missing.join(', ')} (slide không có chữ để đọc). Bạn tự điền hoặc xoá phân cảnh đó.</p>
                )}

                <section className="sp-card sp-revise">
                  <Wand2 size={18} />
                  <input
                    value={revisePrompt}
                    maxLength={1500}
                    disabled={active.revising}
                    onChange={(event) => setRevisePrompt(event.target.value)}
                    onKeyDown={(event) => { if (event.key === 'Enter') reviseActive(); }}
                    placeholder={`Muốn chỉnh gì ở “${active.sheet}”? Ví dụ: viết ngắn hơn, thêm ví dụ thực tế, đổi xưng hô thành cô – các bạn…`}
                    aria-label="Yêu cầu chỉnh sửa kịch bản"
                  />
                  <button type="button" className="btn btn-secondary btn-sm" disabled={!revisePrompt.trim() || active.revising} onClick={reviseActive}>
                    {active.revising ? <><Loader2 size={14} className="spin" /> {active.progress}%</> : 'Viết lại theo yêu cầu'}
                  </button>
                </section>

                {(() => {
                  const status = englishStatus(rows);
                  const need = status.missing + status.stale;
                  return (
                    <section className="sp-card sp-en">
                      <Languages size={18} />
                      <div className="sp-en-text">
                        <strong>Lời thoại tiếng Anh (phụ đề)</strong>
                        <small>
                          {status.translated === 0 && 'Dịch từ lời thoại tiếng Việt, từng đoạn đối chiếu với đoạn tiếng Việt. Xuất Excel sẽ có thêm cột tiếng Anh.'}
                          {status.translated > 0 && need === 0 && `Đã dịch đủ ${status.translated} dòng. Bạn vẫn sửa được từng câu tiếng Anh bên dưới.`}
                          {status.translated > 0 && need > 0 && `Đã dịch ${status.translated} dòng${status.stale ? ` · ${status.stale} dòng đã sửa tiếng Việt nên cần dịch lại` : ''}${status.missing ? ` · ${status.missing} dòng chưa dịch` : ''}.`}
                        </small>
                      </div>
                      <div className="sp-en-actions">
                        <button type="button" className="btn btn-secondary btn-sm" disabled={active.translating || active.revising || need === 0} onClick={translateActive}>
                          {active.translating
                            ? <><Loader2 size={14} className="spin" /> {active.progress}%</>
                            : status.translated === 0 ? 'Dịch sang tiếng Anh' : need === 0 ? 'Đã dịch đủ' : `Dịch ${need} dòng còn lại`}
                        </button>
                        {done.length > 1 && (
                          <button type="button" className="btn btn-ghost btn-sm" disabled={working} onClick={translateAll}>Dịch cả {done.length} file</button>
                        )}
                      </div>
                    </section>
                  );
                })()}

                <section className={`sp-card sp-table${active.revising || active.translating ? ' dim' : ''}`}>
                  <div className="sp-row sp-head">
                    <div>PHÂN CẢNH</div>
                    <div>LỜI THOẠI</div>
                    <div>LƯU Ý DỰNG</div>
                    <div />
                  </div>
                  {rows.map((row, index) => (
                    <div className="sp-row" key={`${active.id}-${keyOf(row)}-${index}`}>
                      <div>
                        <input className="sp-scene" value={row.scene} maxLength={60} aria-label="Phân cảnh" onChange={(event) => updateRow(index, { scene: event.target.value })} />
                        <small className={countWords(row.script) ? '' : 'warn'}>{countWords(row.script) ? `${countWords(row.script)} từ` : 'Chưa có lời thoại'}</small>
                      </div>
                      <div>
                        <ScriptCell value={row.script} label={`Lời thoại ${row.scene}`} onChange={(value) => updateRow(index, { script: value })} />
                        {String(row.en || '').trim() && (
                          <div className="sp-en-row">
                            <span>EN{row.enFor !== String(row.script || '').trim() && <em title="Tiếng Việt đã đổi sau khi dịch"> · cần dịch lại</em>}</span>
                            <ScriptCell className="sp-script sp-script-en" value={row.en} label={`English ${row.scene}`} onChange={(value) => updateRow(index, { en: value })} />
                          </div>
                        )}
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
              </>
            )}

            {done.length > 0 && (
              <footer className="sp-footer">
                <span>
                  {working && <><Loader2 size={14} className="spin" /> Đã xong {done.length}/{items.length} file. </>}
                  {!working && emptyRows > 0 && <><AlertTriangle size={14} /> Còn {emptyRows} phân cảnh chưa có lời thoại. </>}
                  {!working && emptyRows === 0 && (done.length > 1
                    ? `Kiểm tra xong thì xuất: một file Excel gồm ${done.length} sheet, mỗi file slide một sheet.`
                    : 'Kiểm tra xong thì xuất file. File Excel có 3 cột như trên, đúng mẫu kịch bản dựng.')}
                </span>
                <div className="sp-footer-actions">
                  {anyEnglish && (
                    <label className="sp-footer-check">
                      <input type="checkbox" checked={withEnglish} onChange={(event) => setWithEnglish(event.target.checked)} />
                      <span>Kèm cột tiếng Anh</span>
                    </label>
                  )}
                  {done.length > 1 && active?.status === 'done' && (
                    <button type="button" className="btn btn-ghost" disabled={exporting} onClick={() => exportXlsx([active])}>Chỉ sheet này</button>
                  )}
                  <button type="button" className="btn btn-primary btn-lg" disabled={exporting} onClick={() => exportXlsx(done)}>
                    {exporting ? <Loader2 size={18} className="spin" /> : <Download size={18} />}
                    {done.length > 1 ? `Xuất Excel (${done.length} sheet)` : 'Xuất Excel'}
                  </button>
                </div>
              </footer>
            )}
          </>
        )}
      </div>
    </div>
  );
}
