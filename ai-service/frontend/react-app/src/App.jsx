import { useState, useRef, useCallback, useMemo } from 'react'

const API = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' 
  ? 'http://localhost:8000' 
  : window.location.origin

// ─── Plan config ─────────────────────────────────────────────────────────────
const PLAN_CONFIG = {
  free:  { label: 'Free',  maxSlides: 10, maxImages: 5,  maxChars: 5000,  imgSrc: 'Stock photo (Pexels/Wikimedia)', imgQuality: 'Tiêu chuẩn', textQuality: '8 refines' },
  pro:   { label: 'Pro',   maxSlides: 30, maxImages: 15, maxChars: 20000, imgSrc: 'AI sinh ảnh (SDXL/Flux)',        imgQuality: 'Tiêu chuẩn', textQuality: '8 refines' },
  ultra: { label: 'Ultra', maxSlides: 50, maxImages: 35, maxChars: 50000, imgSrc: 'AI sinh ảnh Premium (steps ×1.3, prompt nghệ thuật)', imgQuality: 'Cao cấp', textQuality: '8 refines' },
}

// ─── Hook: slide generator ────────────────────────────────────────────────────
function useSlideGenerator() {
  const [status, setStatus]       = useState(null)
  const [progress, setProgress]   = useState(null)
  const [downloadUrl, setDownloadUrl] = useState(null)
  const [busy, setBusy]           = useState(false)
  const [activeTaskId, setActiveTaskId] = useState(null)
  const pollRef = useRef(null)

  const stopPoll = () => { if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null } }

  const done = useCallback((url, payload) => {
    stopPoll(); setProgress(null)
    if (url) {
      setStatus({ type: 'success', msg: '✅ Slide đã được tạo thành công!' })
      setDownloadUrl(url)
    } else {
      setStatus({ type: 'success', msg: '✅ JSON Spec đã được tạo thành công!' })
      console.log('JSON Spec Payload:', payload)
    }
    setActiveTaskId(null); setBusy(false)
  }, [])

  const fail = useCallback((msg) => {
    stopPoll(); setProgress(null)
    setStatus({ type: 'error', msg: `❌ ${msg}` })
    setActiveTaskId(null); setBusy(false)
  }, [])

  const startPoll = useCallback((taskId) => {
    pollRef.current = setInterval(async () => {
      try {
        const r = await fetch(`${API}/api/status/${taskId}`)
        const d = await r.json()
        if (d.status === 'completed') {
          if (d.result?.download_url) {
            done(`${API}${d.result.download_url}`, d.result)
          } else {
            done(null, d.result)
          }
        } else if (d.status === 'cancelled') {
          stopPoll(); setProgress(null)
          setStatus({ type: 'info', msg: '⏹️ Đã dừng quá trình tạo slide.' })
          setActiveTaskId(null); setBusy(false)
        } else if (d.status === 'error') {
          const raw = d.result?.error ?? d.result?.message ?? d.detail ?? (typeof d.result === 'string' ? d.result : null)
          fail(typeof raw === 'string' && raw.trim() ? raw.trim() : raw != null ? JSON.stringify(raw) : 'Lỗi không rõ — kiểm tra log API.')
        } else if (d.status === 'pending') {
          setProgress(0)
          const pos = d.queue_position
          const tot = d.queue_total
          if (pos !== undefined && pos > 0) {
            setStatus({ type: 'info', msg: `⏳ Đang xếp hàng đợi: Vị trí ${pos}/${tot}. Vui lòng chờ...` })
          } else {
            setStatus({ type: 'info', msg: '⏳ Đang chờ hệ thống xử lý...' })
          }
        } else {
          const pct = d.progress || 0
          setProgress(pct)
          const chunks = d.result?.chunks
          const images = d.result?.images
          if (chunks?.total && pct >= 20 && pct <= 58)
            setStatus({ type: 'info', msg: `⏳ Đang xử lý nội dung: chunk ${chunks.done}/${chunks.total}` })
          else if (pct >= 68 && pct < 80)
            setStatus({ type: 'info', msg: images?.total ? `🖼️ Đang sinh ảnh: ${images.done}/${images.total} slide` : '🖼️ Đang sinh ảnh minh họa...' })
          else if (pct >= 80 && pct < 100)
            setStatus({ type: 'info', msg: '📊 Đang tạo file PowerPoint...' })
          else if (pct > 0 && pct < 20)
            setStatus({ type: 'info', msg: '⏳ Đang chuẩn bị...' })
        }
      } catch { /* keep polling */ }
    }, 2000)
  }, [done, fail])

  const submit = useCallback(async (formData) => {
    if (busy) return
    setBusy(true)
    setStatus({ type: 'info', msg: '⏳ Đang gửi yêu cầu...' })
    setDownloadUrl(null); setProgress(null)
    try {
      const r = await fetch(`${API}/api/generate-slide-full`, { method: 'POST', body: formData })
      if (!r.ok) {
        let errMsg = `HTTP ${r.status}`
        try { const e = await r.json(); errMsg = e.detail || errMsg } catch {}
        throw new Error(errMsg)
      }
      const d = await r.json()
      if (d.status === 'completed') {
        done(`${API}${d.download_url}`)
      } else if (d.status === 'processing') {
        setActiveTaskId(d.task_id)
        setStatus({ type: 'info', msg: '⏳ Đang xử lý...' })
        setProgress(0)
        startPoll(d.task_id)
      } else {
        throw new Error(d.message || 'Unexpected response')
      }
    } catch (e) { fail(e.message) }
  }, [busy, done, fail, startPoll])

  const cancel = useCallback(async () => {
    if (!activeTaskId) return
    try {
      await fetch(`${API}/api/cancel/${activeTaskId}`, { method: 'POST' })
      stopPoll(); setProgress(null)
      setStatus({ type: 'info', msg: '⏹️ Đã gửi yêu cầu dừng.' })
    } catch {
      setStatus({ type: 'error', msg: '❌ Không thể gửi yêu cầu dừng.' })
    } finally { setActiveTaskId(null); setBusy(false) }
  }, [activeTaskId])

  return { status, progress, downloadUrl, busy, submit, cancel, activeTaskId }
}

// ─── Component: PlanBadge ─────────────────────────────────────────────────────
function PlanBadge({ plan }) {
  const cfg = PLAN_CONFIG[plan]
  const colors = { free: '#64748b', pro: '#2563eb', ultra: '#7c3aed' }
  return (
    <div style={{
      border: `2px solid ${colors[plan]}`,
      borderRadius: 10, padding: '10px 14px', marginTop: 10, fontSize: 13,
      background: `${colors[plan]}11`
    }}>
      <strong style={{ color: colors[plan] }}>Gói {cfg.label}</strong>
      <ul style={{ margin: '6px 0 0', padding: '0 0 0 16px', lineHeight: 1.8 }}>
        <li>Slides: {plan === 'free' ? `Cố định ${cfg.maxSlides}` : `Lên đến ${cfg.maxSlides} (Hỗ trợ Auto)`}</li>
        <li>Ảnh tối đa: {cfg.maxImages}</li>
        <li>Input tối đa: {cfg.maxChars.toLocaleString()} ký tự</li>
        <li>Nguồn ảnh: {cfg.imgSrc}</li>
        <li>Chất lượng văn bản: {cfg.textQuality} (tốt nhất)</li>
      </ul>
    </div>
  )
}

// ─── Main App ─────────────────────────────────────────────────────────────────
export default function App() {
  const [tab, setTab]               = useState('text')
  const [text, setText]             = useState('')
  const [file, setFile]             = useState(null)
  const [plan, setPlan]             = useState('pro')
  const [autoSlide, setAutoSlide]   = useState(true)
  const [slideCount, setSlideCount] = useState(10)
  const [slideTheme, setSlideTheme] = useState('modern')
  const [genImages, setGenImages]   = useState(true)
  const [checkMsg, setCheckMsg]     = useState('')
  const { status, progress, downloadUrl, busy, submit, cancel, activeTaskId } = useSlideGenerator()

  const cfg = PLAN_CONFIG[plan]

  const charCount = text.trim().length
  const charOverLimit = charCount > cfg.maxChars
  const charHint = useMemo(() => {
    if (!charCount) return null
    if (charOverLimit) return { kind: 'err', text: `~${charCount} ký tự — vượt giới hạn gói ${cfg.label} (tối đa ${cfg.maxChars.toLocaleString()}). Rút ngắn hoặc đổi gói.` }
    if (charCount < 500) return { kind: 'warn', text: `~${charCount} ký tự — hơi ít, slide có thể chung chung. Nên từ 500+ ký tự.` }
    return { kind: 'ok', text: `~${charCount} ký tự — OK (giới hạn gói: ${cfg.maxChars.toLocaleString()})` }
  }, [charCount, charOverLimit, cfg])

  const handlePlanChange = (p) => {
    setPlan(p)
    const c = PLAN_CONFIG[p]
    setSlideCount(Math.min(slideCount, c.maxSlides))
  }

  const buildFormData = (extraEntry) => {
    const fd = new FormData()
    if (extraEntry) fd.append(...extraEntry)
    fd.append('plan', plan)
    fd.append('slide_theme', slideTheme)
    fd.append('generate_images', genImages ? 'true' : 'false')
    fd.append('image_limit', String(cfg.maxImages))
    if (plan !== 'free') {
      fd.append('slide_count', autoSlide ? '0' : String(slideCount))
    }
    return fd
  }

  const handleTextSubmit = (e) => {
    e.preventDefault()
    if (!text.trim() || charOverLimit) return
    submit(buildFormData(['text', text]))
  }

  const handleFileSubmit = (e) => {
    e.preventDefault()
    if (!file) return
    const fd = buildFormData()
    fd.append('file', file)
    submit(fd)
  }

  const handleCheck = async () => {
    setCheckMsg('Đang kiểm tra...')
    try {
      const [r1, r2] = await Promise.all([
        fetch(`${API}/`).then(r => r.json()).catch(() => null),
        fetch(`${API}/api/vllm-status`).then(r => r.json()).catch(() => null),
      ])
      const be = r1 ? '✅ Backend OK' : '❌ Backend FAIL'
      const vm = r2?.models?.[0] || r2?.model || ''
      const vllm = r2?.ok ? `✅ vLLM OK (${vm || 'no id'})` : '❌ vLLM FAIL'
      setCheckMsg(`${be} • ${vllm}`)
    } catch { setCheckMsg('❌ Không kết nối được') }
  }

  return (
    <div className="page">
      <div className="card">
        <div className="header">
          <h1>🤖 AI Slide Generator</h1>
          <p>Tạo slide PowerPoint tự động với AI — Môi trường test</p>
        </div>

        <div className="body">
          {/* Status bar */}
          <div className="topbar">
            <button className="mini-btn" onClick={handleCheck} type="button">Check kết nối</button>
            <span className="hint">{checkMsg || 'Backend: chưa check • vLLM: chưa check'}</span>
          </div>

          {/* ── Plan selector ── */}
          <div className="field" style={{ marginTop: 12 }}>
            <label><strong>Gói dịch vụ:</strong></label>
            <div style={{ display: 'flex', gap: 8, marginTop: 6 }}>
              {['free', 'pro', 'ultra'].map(p => {
                const colors = { free: '#64748b', pro: '#2563eb', ultra: '#7c3aed' }
                const active = plan === p
                return (
                  <button key={p} type="button"
                    onClick={() => handlePlanChange(p)}
                    style={{
                      flex: 1, padding: '8px 0', border: `2px solid ${colors[p]}`,
                      borderRadius: 8, cursor: 'pointer', fontWeight: active ? 700 : 400,
                      background: active ? colors[p] : 'transparent',
                      color: active ? '#fff' : colors[p], fontSize: 14, transition: 'all .15s'
                    }}>
                    {PLAN_CONFIG[p].label}
                  </button>
                )
              })}
            </div>
            <PlanBadge plan={plan} />
          </div>

          {/* ── Số slide (Pro/Ultra) ── */}
          {plan !== 'free' && (
            <div className="field" style={{ marginTop: 10 }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                <input type="checkbox" checked={autoSlide} onChange={e => setAutoSlide(e.target.checked)} />
                Tự động nhận diện số slide (đọc từ prompt hoặc AI tự quyết định)
              </label>
              {!autoSlide && (
                <div style={{ marginTop: 8, display: 'flex', alignItems: 'center', gap: 10 }}>
                  <label style={{ minWidth: 80 }}>Số slide:</label>
                  <input type="number" min={4} max={cfg.maxSlides} value={slideCount}
                    onChange={e => setSlideCount(Math.max(4, Math.min(cfg.maxSlides, Number(e.target.value) || 10)))}
                    style={{ width: 80 }} />
                  <span style={{ fontSize: 12, color: '#888' }}>(tối đa {cfg.maxSlides})</span>
                </div>
              )}
            </div>
          )}
          {/* ── Theme & Images ── */}
          <div style={{ display: 'flex', gap: 12, marginTop: 10, flexWrap: 'wrap' }}>
            <div className="field" style={{ flex: 1, minWidth: 160 }}>
              <label>Giao diện (theme):</label>
              <select value={slideTheme} onChange={e => setSlideTheme(e.target.value)}>
                <option value="corporate">Corporate — navy</option>
                <option value="modern">Modern — indigo</option>
                <option value="minimal">Minimal — trắng</option>
              </select>
            </div>
            <div className="field" style={{ flex: 1, minWidth: 200, paddingTop: 22 }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                <input type="checkbox" checked={genImages} onChange={e => setGenImages(e.target.checked)} />
                Sinh ảnh minh họa
              </label>
              {plan === 'free' && genImages && (
                <p className="field-hint" style={{ margin: '4px 0 0' }}>Free: chỉ dùng ảnh Stock (Pexels/Wikimedia), không gọi GPU AI.</p>
              )}
              {plan === 'ultra' && genImages && (
                <p className="field-hint" style={{ margin: '4px 0 0', color: '#7c3aed' }}>Ultra: AI sinh ảnh ở chế độ premium (steps ×1.3 + prompt nghệ thuật).</p>
              )}
            </div>
          </div>

          {/* ── Tabs Input ── */}
          <div className="tabs" style={{ marginTop: 14 }}>
            <button className={`tab${tab === 'text' ? ' active' : ''}`} onClick={() => setTab('text')}>Nhập Text</button>
            <button className={`tab${tab === 'file' ? ' active' : ''}`} onClick={() => setTab('file')}>Upload File</button>
          </div>

          {tab === 'text' && (
            <form onSubmit={handleTextSubmit}>
              <div className="field">
                <label>Nội dung:</label>
                <textarea value={text} onChange={e => setText(e.target.value)}
                  placeholder="Nhập nội dung bài thuyết trình..." rows={10} required />
                {charHint && (
                  <p className="field-hint" style={{
                    color: charHint.kind === 'err' ? '#dc2626' : charHint.kind === 'warn' ? '#d97706' : '#16a34a'
                  }}>{charHint.text}</p>
                )}
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <button className="btn" type="submit" disabled={busy || charOverLimit}>
                  {busy ? 'Đang xử lý...' : 'Tạo Slide'}
                </button>
                {busy && activeTaskId && (
                  <button className="btn" type="button" onClick={cancel} style={{ background: '#dc2626' }}>Dừng</button>
                )}
              </div>
            </form>
          )}

          {tab === 'file' && (
            <form onSubmit={handleFileSubmit}>
              <div className="field">
                <label>Chọn file (DOCX, PDF, TXT):</label>
                <input type="file" accept=".docx,.pdf,.txt"
                  onChange={e => setFile(e.target.files[0] || null)} required />
                {file && <span className="file-name">📄 {file.name}</span>}
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <button className="btn" type="submit" disabled={busy}>
                  {busy ? 'Đang xử lý...' : 'Tạo Slide'}
                </button>
                {busy && activeTaskId && (
                  <button className="btn" type="button" onClick={cancel} style={{ background: '#dc2626' }}>Dừng</button>
                )}
              </div>
            </form>
          )}

          {/* ── Progress ── */}
          {progress !== null && (
            <div className="progress" style={{ marginTop: 14 }}>
              <div className="progress-bar">
                <div className="progress-fill" style={{ width: `${progress}%` }}>{progress}%</div>
              </div>
            </div>
          )}

          {/* ── Status ── */}
          {status && <div className={`status ${status.type}`}>{status.msg}</div>}

          {/* ── Download ── */}
          {downloadUrl && (
            <a className="download-btn" href={downloadUrl} target="_blank" rel="noreferrer" download>
              📥 Tải slide về
            </a>
          )}
        </div>
      </div>
    </div>
  )
}
