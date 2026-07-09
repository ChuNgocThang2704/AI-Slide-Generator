import { useCallback, useMemo, useRef, useState } from 'react'

const API =
  window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? 'http://localhost:8000'
    : window.location.origin

const DEFAULT_PLAN = 'pro'

const PLAN_CONFIG = {
  free: { label: 'Free', maxSlides: 10, maxImages: 5, maxChars: 10000 },
  pro: { label: 'Pro', maxSlides: 30, maxImages: 15, maxChars: 50000 },
  ultra: { label: 'Ultra', maxSlides: 50, maxImages: 35, maxChars: 100000 },
}

function SlidePreview({ deck }) {
  const slides = deck?.slides || []
  if (!slides.length) {
    return (
      <div className="empty-preview">
        Chua co JSON spec. Tao slide xong preview se hien o day.
      </div>
    )
  }

  return (
    <div className="preview">
      <div className="preview-header">
        <div>
          <span className="eyebrow">JSON Spec Preview</span>
          <h2>{deck.title || 'Bai thuyet trinh'}</h2>
        </div>
        <span className="count">{slides.length} slides</span>
      </div>
      <div className="slide-grid">
        {slides.map((slide, idx) => (
          <article className="slide-card" key={`${idx}-${slide.title}`}>
            <div className="slide-top">
              <span>Slide {idx + 1}</span>
              <small>{slide.layout || 'text_only'}</small>
            </div>
            <h3>{slide.title || `Slide ${idx + 1}`}</h3>
            <ul>
              {(slide.bullets || []).map((b, i) => (
                <li key={i}>{b}</li>
              ))}
            </ul>
            {slide.image?.url && <SlideImage image={slide.image} />}
            {slide.notes && <p className="notes">{slide.notes}</p>}
          </article>
        ))}
      </div>
    </div>
  )
}

function SlideImage({ image }) {
  const [failed, setFailed] = useState(false)
  const src = image?.url?.startsWith('http') ? image.url : `${API}${image?.url || ''}`
  if (!image?.url) return null
  if (failed) {
    return <div className="image-chip">Image unavailable: {image.url}</div>
  }
  return (
    <div className="slide-image">
      <img alt="Slide visual" loading="lazy" onError={() => setFailed(true)} src={src} />
    </div>
  )
}

function useSpecTasks() {
  const [status, setStatus] = useState(null)
  const [progress, setProgress] = useState(null)
  const [busy, setBusy] = useState(false)
  const [activeTaskId, setActiveTaskId] = useState(null)
  const [spec, setSpec] = useState(null)
  const pollRef = useRef(null)

  const stopPoll = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }

  const fail = useCallback((msg) => {
    stopPoll()
    setProgress(null)
    setBusy(false)
    setActiveTaskId(null)
    setStatus({ type: 'error', msg: msg || 'Co loi xay ra' })
  }, [])

  const complete = useCallback((payload, message) => {
    stopPoll()
    setProgress(null)
    setBusy(false)
    setActiveTaskId(null)
    setSpec(payload)
    setStatus({ type: 'success', msg: message })
  }, [])

  const startPoll = useCallback(
    (taskId, message) => {
      stopPoll()
      pollRef.current = setInterval(async () => {
        try {
          const r = await fetch(`${API}/api/status/${taskId}`)
          const d = await r.json()
          if (d.status === 'completed') {
            complete(d.result, message)
            return
          }
          if (d.status === 'error') {
            const raw = d.result?.error || d.result?.message || d.detail
            fail(typeof raw === 'string' ? raw : JSON.stringify(raw || 'Unknown error'))
            return
          }
          if (d.status === 'cancelled') {
            fail('Task da bi huy')
            return
          }
          const pct = d.progress || 0
          setProgress(pct)
          if (d.status === 'pending') {
            setStatus({ type: 'info', msg: 'Dang cho xu ly...' })
          } else if (d.result?.chunks?.total) {
            setStatus({
              type: 'info',
              msg: `Dang xu ly noi dung: chunk ${d.result.chunks.done}/${d.result.chunks.total}`,
            })
          } else if (d.result?.images?.total) {
            setStatus({
              type: 'info',
              msg: `Dang sinh anh: ${d.result.images.done}/${d.result.images.total}`,
            })
          } else {
            setStatus({ type: 'info', msg: 'Dang tao JSON spec...' })
          }
        } catch {
          // Keep polling while the backend is busy.
        }
      }, 2000)
    },
    [complete, fail],
  )

  const submitSpec = useCallback(
    async (formData) => {
      if (busy) return
      setBusy(true)
      setSpec(null)
      setProgress(0)
      setStatus({ type: 'info', msg: 'Dang gui yeu cau tao JSON spec...' })
      try {
        const r = await fetch(`${API}/api/generate-slide-spec`, { method: 'POST', body: formData })
        if (!r.ok) {
          const e = await r.json().catch(() => null)
          throw new Error(e?.detail || `HTTP ${r.status}`)
        }
        const d = await r.json()
        setActiveTaskId(d.task_id)
        startPoll(d.task_id, 'Da tao JSON spec thanh cong')
      } catch (e) {
        fail(e.message)
      }
    },
    [busy, fail, startPoll],
  )

  const reviseSpec = useCallback(
    async (formData) => {
      if (busy) return
      setBusy(true)
      setProgress(0)
      setStatus({ type: 'info', msg: 'Dang gui yeu cau sua slide...' })
      try {
        const r = await fetch(`${API}/api/revise-slide-spec`, { method: 'POST', body: formData })
        if (!r.ok) {
          const e = await r.json().catch(() => null)
          throw new Error(e?.detail || `HTTP ${r.status}`)
        }
        const d = await r.json()
        setActiveTaskId(d.task_id)
        const scope = d.revision_scope === 'slide' ? `slide ${(d.target_slide_indices || []).map((x) => x + 1).join(', ')}` : 'toan deck'
        startPoll(d.task_id, `Da sua ${scope} thanh cong`)
      } catch (e) {
        fail(e.message)
      }
    },
    [busy, fail, startPoll],
  )

  const cancel = useCallback(async () => {
    if (!activeTaskId) return
    await fetch(`${API}/api/cancel/${activeTaskId}`, { method: 'POST' }).catch(() => null)
    stopPoll()
    setBusy(false)
    setProgress(null)
    setActiveTaskId(null)
    setStatus({ type: 'info', msg: 'Da gui yeu cau dung task' })
  }, [activeTaskId])

  return { activeTaskId, busy, cancel, progress, reviseSpec, spec, status, submitSpec }
}

export default function App() {
  const [tab, setTab] = useState('text')
  const [text, setText] = useState('')
  const [file, setFile] = useState(null)
  const [checkMsg, setCheckMsg] = useState('')
  const [revisionPrompt, setRevisionPrompt] = useState('')
  const { activeTaskId, busy, cancel, progress, reviseSpec, spec, status, submitSpec } = useSpecTasks()

  const cfg = PLAN_CONFIG[DEFAULT_PLAN]
  const deck = spec?.deck
  const sourceTaskId = spec?.task_id
  const charCount = text.trim().length
  const charOverLimit = charCount > cfg.maxChars

  const charHint = useMemo(() => {
    if (!charCount) return ''
    if (charOverLimit) {
      return `${charCount} ky tu - vuot gioi han ${cfg.maxChars.toLocaleString()} cua goi ${cfg.label}`
    }
    return `${charCount} ky tu / ${cfg.maxChars.toLocaleString()}`
  }, [cfg, charCount, charOverLimit])

  const buildBaseForm = () => {
    const fd = new FormData()
    fd.append('plan', DEFAULT_PLAN)
    fd.append('generate_images', 'true')
    return fd
  }

  const submitText = (e) => {
    e.preventDefault()
    if (!text.trim() || charOverLimit) return
    const fd = buildBaseForm()
    fd.append('text', text)
    submitSpec(fd)
  }

  const submitFile = (e) => {
    e.preventDefault()
    if (!file) return
    const fd = buildBaseForm()
    fd.append('file', file)
    if (text.trim()) fd.append('text', text)
    submitSpec(fd)
  }

  const submitRevision = (e) => {
    e.preventDefault()
    if (!sourceTaskId || !revisionPrompt.trim()) return
    const fd = new FormData()
    fd.append('source_task_id', sourceTaskId)
    fd.append('revision_prompt', revisionPrompt)
    fd.append('revision_scope', 'auto')
    fd.append('plan', DEFAULT_PLAN)
    fd.append('generate_images', 'true')
    reviseSpec(fd)
  }

  const checkConnection = async () => {
    setCheckMsg('Dang kiem tra...')
    try {
      const [root, vllm] = await Promise.all([
        fetch(`${API}/`).then((r) => r.json()).catch(() => null),
        fetch(`${API}/api/vllm-status`).then((r) => r.json()).catch(() => null),
      ])
      setCheckMsg(`${root ? 'Backend OK' : 'Backend FAIL'} | ${vllm?.ok ? `vLLM OK (${vllm.models?.[0] || 'model'})` : 'vLLM FAIL'}`)
    } catch {
      setCheckMsg('Khong ket noi duoc backend')
    }
  }

  return (
    <div className="page">
      <main className="shell">
        <section className="panel control-panel">
          <div className="header">
            <span className="eyebrow">AI Service Test</span>
            <h1>Spec-first Slide Generator</h1>
            <p>Tao JSON spec, preview tren FE, sua dung slide theo prompt.</p>
          </div>

          <div className="topbar">
            <button className="mini-btn" type="button" onClick={checkConnection}>
              Check ket noi
            </button>
            <span>{checkMsg || 'Backend chua check | vLLM chua check'}</span>
          </div>

          <div className="tabs">
            <button className={tab === 'text' ? 'active' : ''} onClick={() => setTab('text')} type="button">
              Nhap text
            </button>
            <button className={tab === 'file' ? 'active' : ''} onClick={() => setTab('file')} type="button">
              Upload file
            </button>
          </div>

          {tab === 'text' ? (
            <form onSubmit={submitText}>
              <div className="field">
                <label>Noi dung / prompt</label>
                <textarea
                  onChange={(e) => setText(e.target.value)}
                  placeholder="Nhap noi dung bai thuyet trinh..."
                  rows={8}
                  value={text}
                />
                {charHint && <p className={charOverLimit ? 'hint error-text' : 'hint'}>{charHint}</p>}
              </div>
              <div className="actions">
                <button className="btn" disabled={busy || !text.trim() || charOverLimit} type="submit">
                  Tao JSON spec
                </button>
                {busy && activeTaskId && (
                  <button className="btn danger" onClick={cancel} type="button">
                    Dung
                  </button>
                )}
              </div>
            </form>
          ) : (
            <form onSubmit={submitFile}>
              <div className="field">
                <label>File nguon</label>
                <input accept=".docx,.pdf,.txt" onChange={(e) => setFile(e.target.files?.[0] || null)} type="file" />
              </div>
              <div className="field">
                <label>Lenh dieu huong tuy chon</label>
                <textarea
                  onChange={(e) => setText(e.target.value)}
                  placeholder="Vi du: tap trung vao chuong 2, viet bang tieng Anh..."
                  rows={3}
                  value={text}
                />
              </div>
              <div className="actions">
                <button className="btn" disabled={busy || !file} type="submit">
                  Tao JSON spec
                </button>
                {busy && activeTaskId && (
                  <button className="btn danger" onClick={cancel} type="button">
                    Dung
                  </button>
                )}
              </div>
            </form>
          )}

          {progress !== null && (
            <div className="progress">
              <div style={{ width: `${progress}%` }}>{progress}%</div>
            </div>
          )}
          {status && <div className={`status ${status.type}`}>{status.msg}</div>}

          <form className="revision" onSubmit={submitRevision}>
            <div className="revision-head">
              <div>
                <span className="eyebrow">Prompt lai</span>
                <h2>Sua JSON spec</h2>
              </div>
              <span>{sourceTaskId ? `source: ${sourceTaskId.slice(0, 8)}...` : 'chua co task'}</span>
            </div>
            <div className="field">
              <label>Yeu cau chinh sua</label>
              <textarea
                onChange={(e) => setRevisionPrompt(e.target.value)}
                placeholder="Vi du: sua slide 3 ngan hon, doi bullet 2 thanh..., hoac lam toan bo deck chuyen nghiep hon."
                rows={3}
                value={revisionPrompt}
              />
            </div>
            <button className="btn secondary" disabled={busy || !sourceTaskId || !revisionPrompt.trim()} type="submit">
              Sua spec
            </button>
          </form>
        </section>

        <section className="panel">
          <SlidePreview deck={deck} />
        </section>
      </main>
    </div>
  )
}
