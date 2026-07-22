import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuthStore, useUIStore } from '../../store';
import { authService } from '../../services/authService';
import { Sparkles, Mail, Code, ArrowRight, ArrowLeft, Clock } from 'lucide-react';
import './VerifyCodePage.css';

export default function VerifyCodePage() {
  const { pendingEmail, clearPendingEmail } = useAuthStore();
  const { addToast } = useUIStore();
  const navigate = useNavigate();

  const [code, setCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [resendCountdown, setResendCountdown] = useState(0);

  useEffect(() => {
    if (!pendingEmail) {
      navigate('/register');
      return;
    }

    let timer;
    if (resendCountdown > 0) {
      timer = setTimeout(() => setResendCountdown(resendCountdown - 1), 1000);
    }
    return () => clearTimeout(timer);
  }, [resendCountdown, pendingEmail, navigate]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!code.trim()) {
      addToast('Vui lòng nhập mã xác thực', 'error');
      return;
    }

    setLoading(true);
    try {
      await authService.verifyCode(pendingEmail, code);
      addToast('Xác thực thành công! Bạn có thể đăng nhập ngay bây giờ.', 'success');
      clearPendingEmail();
      navigate('/login');
    } catch (err) {
      addToast(err.message || 'Mã xác thực không đúng hoặc đã hết hạn', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleResend = async () => {
    setLoading(true);
    try {
      // Gọi register lại để gửi mã mới
      await authService.register(pendingEmail, '');
      addToast('Mã xác thực đã được gửi lại. Kiểm tra email của bạn.', 'success');
      setResendCountdown(60);
    } catch (err) {
      addToast('Không thể gửi lại mã. Vui lòng thử lại sau.', 'error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="verify-page">
      <div className="verify-bg-glow verify-glow1" />
      <div className="verify-bg-glow verify-glow2" />

      <div className="verify-container page-enter">
        {/* Left panel */}
        <div className="verify-left">
          <Link to="/" className="verify-logo">
            <div className="logo-icon"><Sparkles size={20} /></div>
            <span style={{ fontFamily: 'Outfit', fontWeight: 800, fontSize: '1.3rem' }}>
              GenSlide<span className="gradient-text">AI</span>
            </span>
          </Link>

          <div className="verify-left-content">
            <h2>Xác thực<br /><span className="gradient-text">tài khoản của bạn</span></h2>
            <p style={{ color: 'rgba(255,255,255,0.55)', marginTop: 16, lineHeight: 1.7 }}>
              Chúng tôi đã gửi mã xác thực 8 chữ số đến email của bạn. Nhập mã để hoàn tất đăng ký.
            </p>

            <div className="verify-info-box">
              <Mail size={16} />
              <span style={{ fontSize: '0.9rem', color: 'rgba(255,255,255,0.7)' }}>
                Email: <strong>{pendingEmail}</strong>
              </span>
            </div>
          </div>

          <div className="verify-slide-preview">
            <div className="asp-slide" style={{ background: 'linear-gradient(135deg,#0d0d1a,#1c1c3a)' }}>
              <div className="asp-deco" />
              <div className="asp-badge">✓ Email Verified</div>
              <div className="asp-title">Tài khoản<br/>đã xác thực</div>
              <div className="asp-bar" />
            </div>
          </div>
        </div>

        {/* Right panel – Form */}
        <div className="verify-right">
          <div className="verify-form-box">
            <div className="verify-form-header">
              <h3>Nhập mã xác thực</h3>
              <p style={{ color: 'rgba(255,255,255,0.5)', fontSize: '0.875rem', marginTop: 6 }}>
                Kiểm tra hộp thư đến hoặc thư spam
              </p>
            </div>

            <form className="verify-form" onSubmit={handleSubmit}>
              <div className="form-group">
                <label className="form-label">Mã xác thực (8 chữ số)</label>
                <div className="input-wrap">
                  <Code size={16} className="input-icon" />
                  <input
                    id="verify-code"
                    type="text"
                    className="input verify-input"
                    placeholder="Ví dụ: 12345678"
                    value={code}
                    onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 8))}
                    maxLength="8"
                    disabled={loading}
                  />
                </div>
              </div>

              <button
                id="verify-submit"
                type="submit"
                className="btn btn-primary btn-lg"
                style={{ width: '100%', justifyContent: 'center' }}
                disabled={loading || code.length !== 8}
              >
                {loading ? (
                  <span className="flex items-center gap-2">
                    <span className="spinner" style={{ width: 18, height: 18, borderWidth: 2 }} />
                    Đang xác thực...
                  </span>
                ) : (
                  <span className="flex items-center gap-2">
                    Xác thực
                    <ArrowRight size={16} />
                  </span>
                )}
              </button>
            </form>

            {/* Resend section */}
            <div className="verify-resend">
              <p style={{ fontSize: '0.875rem', color: 'rgba(255,255,255,0.6)', marginBottom: 12 }}>
                Không nhận được mã?
              </p>
              <button
                className="resend-btn"
                onClick={handleResend}
                disabled={resendCountdown > 0 || loading}
              >
                {resendCountdown > 0 ? (
                  <>
                    <Clock size={14} />
                    Gửi lại trong {resendCountdown}s
                  </>
                ) : (
                  <>
                    <ArrowRight size={14} />
                    Gửi lại mã
                  </>
                )}
              </button>
            </div>

            {/* Back link */}
            <button
              className="verify-back"
              onClick={() => {
                clearPendingEmail();
                navigate('/register');
              }}
            >
              <ArrowLeft size={14} /> Quay lại đăng ký
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
