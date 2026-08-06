import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuthStore, useUIStore } from '../../store';
import { authService } from '../../services/authService';
import { Sparkles, Mail, Lock, User, Eye, EyeOff, ArrowRight } from 'lucide-react';
import './AuthPage.css';

export default function AuthPage({ mode = 'login' }) {
  const [isLogin, setIsLogin] = useState(mode === 'login');
  const [showPass, setShowPass] = useState(false);
  const [loading, setLoading] = useState(false);
  const { pendingEmail } = useAuthStore();
  const [form, setForm] = useState({ name: '', email: pendingEmail || '', password: '' });

  const { login, setPendingEmail } = useAuthStore();
  const { addToast } = useUIStore();
  const navigate = useNavigate();

  React.useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get('code');
    if (code) {
      handleGoogleCallback(code);
    }
  }, []);

  const handleGoogleCallback = async (authCode) => {
    setLoading(true);
    addToast('Đang đăng nhập bằng tài khoản Google...', 'info');
    try {
      const result = await authService.loginWithGoogle(authCode);
      login(result.user, result.token, result.refreshToken);
      addToast('Đăng nhập Google thành công! 👋', 'success');
      navigate('/dashboard');
    } catch (err) {
      addToast(err.message || 'Đăng nhập Google thất bại', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleLoginClick = async () => {
    try {
      setLoading(true);
      const data = await authService.getGoogleAuthUrl();
      if (data && data.url) {
        window.location.href = data.url;
      } else {
        addToast('Không lấy được URL đăng nhập Google', 'error');
      }
    } catch (err) {
      addToast(err.message || 'Lỗi kết nối Google Auth', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (e) => setForm({ ...form, [e.target.name]: e.target.value });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      let result;
      if (isLogin) {
        result = await authService.login(form.email, form.password);
        login(result.user, result.token, result.refreshToken);
        addToast('Đăng nhập thành công! Chào mừng bạn 👋', 'success');
        navigate('/dashboard');
      } else {
        await authService.register(form.email, form.password);
        setPendingEmail(form.email);
        addToast('Đăng ký thành công! Vui lòng kiểm tra email để lấy mã xác thực.', 'success');
        navigate('/verify-code');
      }
    } catch (err) {
      addToast(err.message || 'Có lỗi xảy ra, vui lòng thử lại', 'error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-bg-glow auth-glow1" />
      <div className="auth-bg-glow auth-glow2" />

      <div className="auth-container page-enter">
        {/* Left panel */}
        <div className="auth-left">
          <Link to="/" className="auth-logo">
            <div className="logo-icon"><Sparkles size={20} /></div>
            <span style={{ fontFamily: 'Outfit', fontWeight: 800, fontSize: '1.3rem' }}>
              Lec<span className="gradient-text">Gen</span>
            </span>
          </Link>

          <div className="auth-left-content">
            <h2>Tạo slide thuyết trình<br /><span className="gradient-text">chuyên nghiệp</span><br />với AI</h2>
            <p style={{ color: 'rgba(255,255,255,0.55)', marginTop: 16, lineHeight: 1.7 }}>
              Nhập chủ đề, chọn template yêu thích và để AI làm phần còn lại. Slide đẹp trong vài giây.
            </p>

            <div className="auth-features">
              {['Miễn phí 5 slides đầu tiên', '6 template thiết kế đẹp', 'Xuất PDF chất lượng cao', 'Không cần kỹ năng thiết kế'].map((f) => (
                <div key={f} className="auth-feat-item">
                  <div className="auth-feat-dot" />
                  <span>{f}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="auth-slide-preview">
            <div className="asp-slide" style={{ background: 'linear-gradient(135deg,#0d0d1a,#1c1c3a)' }}>
              <div className="asp-deco" />
              <div className="asp-badge">✦ AI Presentation</div>
              <div className="asp-title">Slide thuyết trình<br/>chuyên nghiệp</div>
              <div className="asp-bar" />
            </div>
          </div>
        </div>

        {/* Right panel – Form */}
        <div className="auth-right">
          <div className="auth-form-box">
            {/* Tab switcher */}
            <div className="auth-tabs">
              <button
                className={`auth-tab ${isLogin ? 'active' : ''}`}
                onClick={() => setIsLogin(true)}
              >
                Đăng nhập
              </button>
              <button
                className={`auth-tab ${!isLogin ? 'active' : ''}`}
                onClick={() => setIsLogin(false)}
              >
                Đăng ký
              </button>
            </div>

            <div className="auth-form-header">
              <h3>{isLogin ? 'Chào mừng trở lại!' : 'Tạo tài khoản mới'}</h3>
              <p style={{ color: 'rgba(255,255,255,0.5)', fontSize: '0.875rem', marginTop: 6 }}>
                {isLogin ? 'Đăng nhập để tiếp tục tạo slide' : 'Bắt đầu miễn phí, không cần thẻ tín dụng'}
              </p>
            </div>

            <form className="auth-form" onSubmit={handleSubmit}>
              {!isLogin && (
                <div className="form-group">
                  <label className="form-label">Họ và tên</label>
                  <div className="input-wrap">
                    <User size={16} className="input-icon" />
                    <input
                      id="auth-name"
                      name="name"
                      type="text"
                      className="input auth-input"
                      placeholder="Nguyễn Văn A"
                      value={form.name}
                      onChange={handleChange}
                      required={!isLogin}
                    />
                  </div>
                </div>
              )}

              <div className="form-group">
                <label className="form-label">Email</label>
                <div className="input-wrap">
                  <Mail size={16} className="input-icon" />
                  <input
                    id="auth-email"
                    name="email"
                    type="email"
                    className="input auth-input"
                    placeholder="email@example.com"
                    value={form.email}
                    onChange={handleChange}
                    required
                  />
                </div>
              </div>

              <div className="form-group">
                <div className="flex justify-between items-center">
                  <label className="form-label">Mật khẩu</label>
                  {isLogin && (
                    <button
                      type="button"
                      className="forgot-link"
                      onClick={() => navigate('/forgot-password')}
                    >
                      Quên mật khẩu?
                    </button>
                  )}
                </div>
                <div className="input-wrap">
                  <Lock size={16} className="input-icon" />
                  <input
                    id="auth-password"
                    name="password"
                    type={showPass ? 'text' : 'password'}
                    className="input auth-input"
                    placeholder="Tối thiểu 6 ký tự"
                    value={form.password}
                    onChange={handleChange}
                    required
                  />
                  <button type="button" className="pass-toggle" onClick={() => setShowPass(!showPass)}>
                    {showPass ? <EyeOff size={15} /> : <Eye size={15} />}
                  </button>
                </div>
              </div>

              <button id="auth-submit" type="submit" className="btn btn-primary btn-lg" style={{ width: '100%', justifyContent: 'center' }} disabled={loading}>
                {loading ? (
                  <span className="flex items-center gap-2">
                    <span className="spinner" style={{ width: 18, height: 18, borderWidth: 2 }} />
                    Đang xử lý...
                  </span>
                ) : (
                  <span className="flex items-center gap-2">
                    {isLogin ? 'Đăng nhập' : 'Tạo tài khoản'}
                    <ArrowRight size={16} />
                  </span>
                )}
              </button>
            </form>

            <div className="auth-divider">
              <span>Hoặc</span>
            </div>

            <button
              type="button"
              className="btn btn-google"
              onClick={handleGoogleLoginClick}
              disabled={loading}
              style={{ width: '100%', justifyContent: 'center', marginTop: 12, background: '#fff', color: '#1a1a1a', border: '1px solid rgba(255,255,255,0.1)' }}
            >
              <svg style={{ width: 16, height: 16, marginRight: 8 }} viewBox="0 0 24 24">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l3.66-2.85z"/>
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.85c.87-2.6 3.3-4.53 6.16-4.53z"/>
              </svg>
              Đăng nhập bằng Google
            </button>

            {/* Quick demo */}
            <div className="auth-demo" style={{ flexDirection: 'column', gap: '8px', alignItems: 'center' }}>
              <span style={{ fontSize: '0.78rem', color: 'rgba(255,255,255,0.4)' }}>Dùng thử nhanh tài khoản:</span>
              <div style={{ display: 'flex', gap: '16px', marginTop: 4 }}>
                <button
                  type="button"
                  className="demo-btn"
                  onClick={() => {
                    setForm({ name: 'Demo User', email: 'demo@lecgen.ai', password: '123456' });
                    setTimeout(() => document.getElementById('auth-submit')?.click(), 100);
                  }}
                >
                  Thành viên <ArrowRight size={13} />
                </button>
                <button
                  type="button"
                  className="demo-btn"
                  onClick={() => {
                    setForm({ name: 'Admin User', email: 'admin@aislide.com', password: 'admin123' });
                    setTimeout(() => document.getElementById('auth-submit')?.click(), 100);
                  }}
                  style={{ color: '#ff6584' }}
                >
                  Quản trị Admin <ArrowRight size={13} />
                </button>
              </div>
            </div>

            <p className="auth-switch">
              {isLogin ? 'Chưa có tài khoản? ' : 'Đã có tài khoản? '}
              <button className="auth-switch-btn" onClick={() => setIsLogin(!isLogin)}>
                {isLogin ? 'Đăng ký ngay' : 'Đăng nhập'}
              </button>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
