import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Sparkles, Zap, FileText, Download, Palette, CheckCircle, ArrowRight, BarChart3, ChevronRight } from 'lucide-react';
import { useAuthStore } from '../../store';
import ElementCanvas from '../../components/slides/ElementCanvas';
import './LandingPage.css';

const FEATURES = [
  { icon: <Sparkles size={24} />, title: 'AI Tạo Slide Tự Động', desc: 'Nhập yêu cầu hoặc tải tài liệu để hệ thống xây dựng nội dung và bố cục bài trình chiếu.' },
  { icon: <Palette size={24} />, title: 'Nhiều phong cách trình bày', desc: 'Chọn giao diện phù hợp với bài giảng, báo cáo hoặc bài thuyết trình thông thường.' },
  { icon: <Download size={24} />, title: 'Xuất PPTX và PDF', desc: 'Tải bài trình chiếu về để tiếp tục chỉnh sửa hoặc sử dụng ngoại tuyến.' },
  { icon: <FileText size={24} />, title: 'Nhiều Loại Slide', desc: 'Title, Content, Two-Column, Image+Text, Quote, Thank You – đầy đủ cấu trúc bài thuyết trình.' },
  { icon: <Zap size={24} />, title: 'Quy trình tự động', desc: 'Hệ thống xử lý nội dung, lựa chọn bố cục và bổ sung thành phần trực quan theo tiến trình.' },
  { icon: <BarChart3 size={24} />, title: 'Quản Lý Dễ Dàng', desc: 'Lưu trữ toàn bộ bài thuyết trình, chỉnh sửa lại bất cứ lúc nào, không bao giờ mất dữ liệu.' },
];

// Real templates from the editor, rendered with the real slide renderer.
const SHOWCASE_TEMPLATES = [
  { id: 'soft-blue', name: 'Soft Blue', tag: 'Phổ biến' },
  { id: 'royal-purple', name: 'Royal Purple', tag: 'Sang trọng' },
  { id: 'clean-white', name: 'Clean White', tag: 'Tối giản' },
  { id: 'modern-dark', name: 'Modern Dark', tag: 'Hiện đại' },
  { id: 'playful-yellow', name: 'Playful Yellow', tag: 'Vui tươi' },
  { id: 'gradient-border', name: 'Gradient Border', tag: 'Nổi bật' },
  { id: 'blue-planet', name: 'Blue Planet', tag: 'Vũ trụ' },
  { id: 'nature-green', name: 'Nature Green', tag: 'Tươi mát' },
  { id: 'tech-purple', name: 'Tech Purple', tag: 'Công nghệ' },
  { id: 'ocean-teal', name: 'Ocean Teal', tag: 'Dịu mát' },
  { id: 'editorial-paper', name: 'Editorial Paper', tag: 'Biên tập' },
  { id: 'midnight-gold', name: 'Midnight Gold', tag: 'Cao cấp' },
];
const SHOWCASE_SLIDE = {
  id: 'showcase', type: 'title', title: 'Trí tuệ nhân tạo',
  bullets: ['Tương lai của công nghệ và giáo dục'], elements: [],
};

function TemplateThumb({ theme }) {
  const ref = React.useRef(null);
  const [scale, setScale] = React.useState(0.3);
  React.useEffect(() => {
    const node = ref.current;
    if (!node || typeof ResizeObserver === 'undefined') return undefined;
    const observer = new ResizeObserver(() => setScale(node.clientWidth / 960));
    observer.observe(node);
    return () => observer.disconnect();
  }, []);
  return (
    <div className="tpc-slide" ref={ref}>
      <div style={{ width: 960, height: 540, transform: `scale(${scale})`, transformOrigin: 'top left' }}>
        <ElementCanvas slide={SHOWCASE_SLIDE} theme={theme} scale={1} readonly onUpdate={() => {}} />
      </div>
    </div>
  );
}

const CAPABILITIES = [
  { value: 'Prompt & tài liệu', label: 'Nguồn nội dung' },
  { value: 'Text • Ảnh', label: 'Nội dung trực quan' },
  { value: 'Bảng • Biểu đồ', label: 'Dữ liệu có cấu trúc' },
  { value: 'PPTX • PDF', label: 'Định dạng xuất' },
];

export default function LandingPage() {
  const { isAuthenticated } = useAuthStore();
  const navigate = useNavigate();

  return (
    <div className="landing">
      {/* ── HERO ── */}
      <section className="hero">
        <div className="hero-glow" />
        <div className="container">
          <div className="hero-content page-enter">
            <div className="hero-badge">
              <Sparkles size={13} />
              <span>AI-Powered Presentation Generator</span>
            </div>
            <h1 className="hero-title">
              Tạo Slide Thuyết Trình<br />
              <span className="gradient-text">Chuyên Nghiệp Với AI</span>
            </h1>
            <p className="hero-desc">
              Nhập yêu cầu hoặc tải tài liệu, chọn template và để AI xây dựng nội dung slide.
              Bạn có thể chỉnh sửa, trình chiếu và xuất tệp ngay trên hệ thống.
            </p>
            <div className="hero-actions">
              <button
                className="btn btn-primary btn-lg"
                onClick={() => navigate(isAuthenticated ? '/generate' : '/register')}
              >
                <Sparkles size={18} />
                Tạo slide miễn phí
              </button>
              <Link to="/pricing" className="btn btn-secondary btn-lg">
                Xem bảng giá <ArrowRight size={16} />
              </Link>
            </div>
            <div className="hero-trust">
              <CheckCircle size={15} color="#2ecc71" />
              <span>Hỗ trợ prompt, PDF và DOCX</span>
            </div>
          </div>

          {/* Mock slide preview */}
          <div className="hero-preview">
            <div className="preview-card preview-main">
              <div className="preview-slide" style={{ background: 'linear-gradient(135deg,#0d0d1a,#1c1c3a)' }}>
                <div className="ps-deco1" />
                <div className="ps-deco2" />
                <div className="ps-badge">✦ Presentation</div>
                <div className="ps-title">Trí Tuệ<br/>Nhân Tạo</div>
                <div className="ps-sub">Tương lai của công nghệ</div>
                <div className="ps-bar" />
              </div>
            </div>
            <div className="preview-card preview-sm preview-sm1">
              <div className="preview-slide small" style={{ background: 'linear-gradient(135deg,#1a0533,#3a0ca3)' }}>
                <div className="ps-label" style={{color:'#f72585'}}>02</div>
                <div className="ps-mini-title">Ứng dụng AI</div>
                <div className="ps-mini-dots">
                  {['Machine Learning','Deep Learning','NLP'].map(b=>(
                    <div key={b} className="ps-mini-dot"><span/>{b}</div>
                  ))}
                </div>
              </div>
            </div>
            <div className="preview-card preview-sm preview-sm2">
              <div className="preview-slide small" style={{ background: 'linear-gradient(135deg,#001f4d,#003080)' }}>
                <div className="ps-label" style={{color:'#0077e6'}}>03</div>
                <div className="ps-mini-title">So sánh</div>
                <div className="ps-mini-cols">
                  <div className="ps-mini-col">
                    <div className="ps-mini-col-h" style={{color:'#0077e6'}}>Hiện tại</div>
                    <div className="ps-mini-col-p">▸ Data AI</div>
                    <div className="ps-mini-col-p">▸ Cloud</div>
                  </div>
                  <div className="ps-mini-col">
                    <div className="ps-mini-col-h" style={{color:'#00c2ff'}}>Tương lai</div>
                    <div className="ps-mini-col-p">▸ AGI</div>
                    <div className="ps-mini-col-p">▸ Edge</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── STATS ── */}
      <section className="stats-section">
        <div className="container">
          <div className="stats-grid">
            {CAPABILITIES.map((s, i) => (
              <div key={i} className="stat-item">
                <div className="stat-value gradient-text">{s.value}</div>
                <div className="stat-label">{s.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── FEATURES ── */}
      <section className="section" id="features">
        <div className="container">
          <div className="section-header">
            <div className="section-badge">Tính năng</div>
            <h2>Mọi thứ bạn cần để tạo<br /><span className="gradient-text">slide hoàn hảo</span></h2>
            <p>Nền tảng AI toàn diện giúp bạn tạo bài thuyết trình chuyên nghiệp nhanh chóng</p>
          </div>
          <div className="features-grid">
            {FEATURES.map((f, i) => (
              <div key={i} className="feature-card">
                <div className="feature-icon">{f.icon}</div>
                <h3 className="feature-title">{f.title}</h3>
                <p className="feature-desc">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── TEMPLATES SHOWCASE ── */}
      <section className="section templates-section">
        <div className="container">
          <div className="section-header">
            <div className="section-badge">Templates</div>
            <h2>{SHOWCASE_TEMPLATES.length} Template <span className="gradient-text">Đẹp Mắt</span></h2>
            <p>Mỗi template được thiết kế tỉ mỉ cho từng phong cách thuyết trình khác nhau</p>
          </div>
          <div className="templates-showcase">
            {SHOWCASE_TEMPLATES.map((t) => (
              <div key={t.id} className="template-preview-card">
                <TemplateThumb theme={t.id} />
                <div className="tpc-info">
                  <span className="tpc-name">{t.name}</span>
                  <span className="tpc-tag">{t.tag}</span>
                </div>
              </div>
            ))}
          </div>
          <div className="templates-cta">
            <button className="btn btn-primary btn-lg" onClick={() => navigate(isAuthenticated ? '/generate' : '/register')}>
              <Sparkles size={18} /> Thử ngay – Miễn phí
            </button>
          </div>
        </div>
      </section>

      {/* ── HOW IT WORKS ── */}
      <section className="section how-section">
        <div className="container">
          <div className="section-header">
            <div className="section-badge">Quy trình</div>
            <h2>Tạo slide chỉ trong <span className="gradient-text">3 bước</span></h2>
          </div>
          <div className="steps-grid">
            {[
              { num: '01', title: 'Nhập yêu cầu', desc: 'Mô tả chủ đề, số lượng slide và nội dung mong muốn hoặc chọn tài liệu đã tải lên' },
              { num: '02', title: 'Chọn template', desc: 'Lựa chọn 1 trong 12 template thiết kế đẹp phù hợp với nội dung' },
              { num: '03', title: 'Hoàn thiện', desc: 'Chỉnh sửa, trình chiếu trực tiếp hoặc xuất bài dưới dạng PPTX và PDF' },
            ].map((s, i) => (
              <div key={i} className="step-card">
                <div className="step-num gradient-text">{s.num}</div>
                <h3 className="step-title">{s.title}</h3>
                <p className="step-desc">{s.desc}</p>
                {i < 2 && <ChevronRight size={28} className="step-arrow" />}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA ── */}
      <section className="cta-section">
        <div className="container">
          <div className="cta-box">
            <div className="cta-glow" />
            <div className="cta-badge"><Sparkles size={13} /> Tạo bài trình chiếu với AI</div>
            <h2>Bắt đầu tạo slide<br /><span className="gradient-text">ngay hôm nay</span></h2>
            <p>Bắt đầu với gói miễn phí. Không cần thẻ tín dụng.</p>
            <div className="flex gap-4 justify-center" style={{flexWrap:'wrap'}}>
              <button className="btn btn-primary btn-lg" onClick={() => navigate(isAuthenticated ? '/generate' : '/register')}>
                <Sparkles size={18} /> Tạo slide miễn phí
              </button>
              <Link to="/pricing" className="btn btn-secondary btn-lg">Xem bảng giá</Link>
            </div>
            <div className="cta-checks">
              {['Có gói miễn phí', 'Không cần thẻ tín dụng', 'Xuất PPTX và PDF'].map(c => (
                <span key={c} className="cta-check"><CheckCircle size={14} color="#2ecc71" /> {c}</span>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── FOOTER ── */}
      <footer className="footer">
        <div className="container">
          <div className="footer-top">
            <div className="footer-brand">
              <div className="navbar-logo" style={{display:'flex',alignItems:'center',gap:10}}>
                <div className="logo-icon"><Sparkles size={16}/></div>
                <span style={{fontFamily:'Be Vietnam Pro',fontWeight:800,fontSize:'1.1rem',color:'white'}}>
                  Lec<span className="gradient-text">Gen</span>
                </span>
              </div>
              <p style={{color:'rgba(255,255,255,0.45)',fontSize:'0.875rem',maxWidth:240,marginTop:12}}>
                Nền tảng tạo slide thuyết trình bằng AI, nhanh chóng và chuyên nghiệp.
              </p>
            </div>
            <div className="footer-links">
              <div className="footer-col">
                <div className="footer-col-title">Sản phẩm</div>
                <Link to="/generate">Tạo slide</Link>
                <Link to="/pricing">Bảng giá</Link>
                <a href="#features">Tính năng</a>
              </div>
              <div className="footer-col">
                <div className="footer-col-title">Tài khoản</div>
                <Link to="/login">Đăng nhập</Link>
                <Link to="/register">Đăng ký</Link>
                <Link to="/dashboard">Dashboard</Link>
              </div>
            </div>
          </div>
          <div className="footer-bottom">
            <span>© 2026 LecGen. Developed at PTIT.</span>
            <div className="flex gap-4">
              <a href="#">Điều khoản</a>
              <a href="#">Bảo mật</a>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
