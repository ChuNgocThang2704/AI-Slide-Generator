import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Sparkles, Zap, FileText, Download, Palette, CheckCircle, ArrowRight, Star, Users, BarChart3, ChevronRight } from 'lucide-react';
import { useAuthStore } from '../../store';
import './LandingPage.css';

const FEATURES = [
  { icon: <Sparkles size={24} />, title: 'AI Tạo Slide Tự Động', desc: 'Chỉ cần nhập chủ đề, AI sẽ tạo toàn bộ nội dung và bố cục slide chuyên nghiệp trong vài giây.' },
  { icon: <Palette size={24} />, title: '6 Template Đẹp', desc: 'Modern Dark, Corporate Blue, Creative Minimal... Mỗi template với màu sắc và font riêng biệt.' },
  { icon: <Download size={24} />, title: 'Xuất PDF Dễ Dàng', desc: 'Tải slide về dạng PDF chất lượng cao chỉ với một cú click, sẵn sàng trình bày ngay.' },
  { icon: <FileText size={24} />, title: 'Nhiều Loại Slide', desc: 'Title, Content, Two-Column, Image+Text, Quote, Thank You – đầy đủ cấu trúc bài thuyết trình.' },
  { icon: <Zap size={24} />, title: 'Sinh Slide Siêu Nhanh', desc: 'Không cần kỹ năng thiết kế. AI xử lý mọi thứ từ nội dung đến bố cục trong dưới 5 giây.' },
  { icon: <BarChart3 size={24} />, title: 'Quản Lý Dễ Dàng', desc: 'Lưu trữ toàn bộ presentation, chỉnh sửa lại bất cứ lúc nào, không bao giờ mất dữ liệu.' },
];

const TEMPLATES_PREVIEW = [
  { id: 'modern-dark', name: 'Modern Dark', tag: 'Phổ biến', grad: 'linear-gradient(135deg,#0d0d1a,#1c1c3a)', accent: '#6c63ff' },
  { id: 'vibrant-gradient', name: 'Vibrant Gradient', tag: 'Nổi bật', grad: 'linear-gradient(135deg,#f72585,#7209b7,#3a0ca3)', accent: '#f72585' },
  { id: 'corporate-blue', name: 'Corporate Blue', tag: 'Doanh nghiệp', grad: 'linear-gradient(135deg,#001f4d,#003080)', accent: '#0077e6' },
  { id: 'tech-purple', name: 'Tech Purple', tag: 'Công nghệ', grad: 'linear-gradient(135deg,#0a0015,#160026)', accent: '#e056fd' },
  { id: 'nature-green', name: 'Nature Green', tag: 'Tươi mát', grad: 'linear-gradient(135deg,#0a2318,#0f3426)', accent: '#27ae60' },
  { id: 'creative-minimal', name: 'Creative Minimal', tag: 'Sáng tạo', grad: 'linear-gradient(135deg,#f8f8f8,#fff)', accent: '#ff4757' },
];

const STATS = [
  { value: '10K+', label: 'Slide đã tạo' },
  { value: '500+', label: 'Người dùng' },
  { value: '6', label: 'Templates đẹp' },
  { value: '99%', label: 'Hài lòng' },
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
              Nhập chủ đề, chọn template, AI sẽ tự động tạo toàn bộ nội dung slide
              đẹp mắt trong vài giây. Không cần kỹ năng thiết kế.
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
              {[...Array(5)].map((_, i) => <Star key={i} size={14} fill="#fbbf24" color="#fbbf24" />)}
              <span>4.9/5 từ 500+ người dùng</span>
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
            {STATS.map((s, i) => (
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
            <h2>6 Template <span className="gradient-text">Đẹp Mắt</span></h2>
            <p>Mỗi template được thiết kế tỉ mỉ cho từng phong cách thuyết trình khác nhau</p>
          </div>
          <div className="templates-showcase">
            {TEMPLATES_PREVIEW.map((t) => (
              <div key={t.id} className="template-preview-card">
                <div className="tpc-slide" style={{ background: t.grad }}>
                  <div className="tpc-deco" style={{ background: t.accent + '25' }} />
                  <div className="tpc-badge" style={{ color: t.accent, borderColor: t.accent + '55', background: t.accent + '15' }}>
                    ✦ Slide
                  </div>
                  <div className="tpc-title" style={{ color: t.id === 'creative-minimal' ? '#1a1a1a' : 'white' }}>
                    {t.name}
                  </div>
                  <div className="tpc-bar" style={{ background: t.accent }} />
                </div>
                <div className="tpc-info">
                  <span className="tpc-name">{t.name}</span>
                  <span className="tpc-tag" style={{ color: t.accent, background: t.accent + '18' }}>{t.tag}</span>
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
              { num: '01', title: 'Nhập chủ đề', desc: 'Gõ chủ đề bài thuyết trình và chọn số lượng slide mong muốn' },
              { num: '02', title: 'Chọn template', desc: 'Lựa chọn 1 trong 6 template thiết kế đẹp phù hợp với nội dung' },
              { num: '03', title: 'Tải về PDF', desc: 'AI tạo slide trong vài giây, xuất PDF và sẵn sàng trình bày' },
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
            <div className="cta-badge"><Users size={13} /> Tham gia 500+ người dùng</div>
            <h2>Bắt đầu tạo slide<br /><span className="gradient-text">ngay hôm nay</span></h2>
            <p>Miễn phí 5 slides đầu tiên. Không cần thẻ tín dụng.</p>
            <div className="flex gap-4 justify-center" style={{flexWrap:'wrap'}}>
              <button className="btn btn-primary btn-lg" onClick={() => navigate(isAuthenticated ? '/generate' : '/register')}>
                <Sparkles size={18} /> Tạo slide miễn phí
              </button>
              <Link to="/pricing" className="btn btn-secondary btn-lg">Xem bảng giá</Link>
            </div>
            <div className="cta-checks">
              {['Miễn phí 5 slides', 'Không cần thẻ tín dụng', 'Xuất PDF ngay'].map(c => (
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
                <span style={{fontFamily:'Outfit',fontWeight:800,fontSize:'1.1rem',color:'white'}}>
                  PSlide<span className="gradient-text">AI</span>
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
            <span>© 2026 PSlideAI. Developed at PTIT.</span>
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
