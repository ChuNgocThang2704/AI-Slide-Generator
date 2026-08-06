import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  ArrowRight,
  Check,
  Eye,
  EyeOff,
  KeyRound,
  Lock,
  Mail,
  Sparkles,
} from 'lucide-react';
import { authService } from '../../services/authService';
import { useAuthStore, useUIStore } from '../../store';
import '../AuthPage/AuthPage.css';
import './ForgotPasswordPage.css';

const STEPS = [
  { id: 'email', label: 'Email' },
  { id: 'code', label: 'Xác thực' },
  { id: 'password', label: 'Mật khẩu mới' },
];

export default function ForgotPasswordPage() {
  const [step, setStep] = useState('email');
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [form, setForm] = useState({
    email: '',
    code: '',
    newPassword: '',
    confirmPassword: '',
  });

  const navigate = useNavigate();
  const { setPendingEmail } = useAuthStore();
  const { addToast } = useUIStore();
  const currentStepIndex = STEPS.findIndex((item) => item.id === step);

  const updateField = (event) => {
    const { name, value } = event.target;
    setForm((current) => ({ ...current, [name]: value }));
  };

  const sendResetCode = async () => {
    await authService.forgotPassword(form.email.trim());
    setStep('code');
    addToast('Mã xác thực đã được gửi tới email của bạn.', 'success');
  };

  const verifyCode = async () => {
    await authService.verifyResetCode(form.email.trim(), form.code.trim());
    setStep('password');
    addToast('Xác thực mã thành công.', 'success');
  };

  const changePassword = async () => {
    if (form.newPassword !== form.confirmPassword) {
      throw new Error('Mật khẩu xác nhận không khớp.');
    }

    await authService.resetPassword(
      form.email.trim(),
      form.newPassword,
      form.confirmPassword,
    );
    setPendingEmail(form.email.trim());
    addToast('Đổi mật khẩu thành công. Bạn có thể đăng nhập ngay.', 'success');
    navigate('/login', { replace: true });
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setLoading(true);
    try {
      if (step === 'email') {
        await sendResetCode();
      } else if (step === 'code') {
        await verifyCode();
      } else {
        await changePassword();
      }
    } catch (error) {
      addToast(error.message || 'Không thể xử lý yêu cầu. Vui lòng thử lại.', 'error');
    } finally {
      setLoading(false);
    }
  };

  const resendCode = async () => {
    setLoading(true);
    try {
      await authService.forgotPassword(form.email.trim());
      addToast('Mã xác thực mới đã được gửi.', 'success');
    } catch (error) {
      addToast(error.message || 'Không thể gửi lại mã xác thực.', 'error');
    } finally {
      setLoading(false);
    }
  };

  const goBack = () => {
    if (step === 'password') {
      setStep('code');
    } else if (step === 'code') {
      setStep('email');
    } else {
      navigate('/login');
    }
  };

  const header = step === 'email'
    ? {
        title: 'Quên mật khẩu?',
        description: 'Nhập email đã đăng ký để nhận mã xác thực.',
      }
    : step === 'code'
      ? {
          title: 'Kiểm tra email',
          description: `Nhập mã xác thực đã gửi tới ${form.email}.`,
        }
      : {
          title: 'Tạo mật khẩu mới',
          description: 'Mật khẩu mới cần có ít nhất 6 ký tự.',
        };

  return (
    <main className="auth-page forgot-password-page">
      <div className="auth-bg-glow auth-glow1" />
      <div className="auth-bg-glow auth-glow2" />

      <div className="forgot-password-shell page-enter">
        <Link to="/" className="auth-logo forgot-password-logo">
          <div className="logo-icon"><Sparkles size={20} /></div>
          <span className="forgot-password-brand">
            Lec<span className="gradient-text">Gen</span>
          </span>
        </Link>

        <section className="forgot-password-panel" aria-labelledby="forgot-password-title">
          <button type="button" className="forgot-back-button" onClick={goBack}>
            <ArrowLeft size={17} />
            Quay lại
          </button>

          <div className="forgot-progress" aria-label="Tiến trình đặt lại mật khẩu">
            {STEPS.map((item, index) => {
              const complete = index < currentStepIndex;
              const active = index === currentStepIndex;
              return (
                <React.Fragment key={item.id}>
                  {index > 0 && <span className={`forgot-progress-line ${complete || active ? 'active' : ''}`} />}
                  <div className={`forgot-progress-step ${active ? 'active' : ''} ${complete ? 'complete' : ''}`}>
                    <span className="forgot-progress-dot">
                      {complete ? <Check size={14} /> : index + 1}
                    </span>
                    <span>{item.label}</span>
                  </div>
                </React.Fragment>
              );
            })}
          </div>

          <div className="forgot-heading">
            <div className="forgot-heading-icon">
              {step === 'email' ? <Mail size={23} /> : step === 'code' ? <KeyRound size={23} /> : <Lock size={23} />}
            </div>
            <h1 id="forgot-password-title">{header.title}</h1>
            <p>{header.description}</p>
          </div>

          <form className="auth-form" onSubmit={handleSubmit}>
            {step === 'email' && (
              <div className="form-group">
                <label className="form-label" htmlFor="forgot-email">Email</label>
                <div className="input-wrap">
                  <Mail size={16} className="input-icon" />
                  <input
                    id="forgot-email"
                    name="email"
                    type="email"
                    className="input auth-input"
                    placeholder="email@example.com"
                    value={form.email}
                    onChange={updateField}
                    autoComplete="email"
                    autoFocus
                    required
                  />
                </div>
              </div>
            )}

            {step === 'code' && (
              <div className="form-group">
                <label className="form-label" htmlFor="forgot-code">Mã xác thực</label>
                <div className="input-wrap">
                  <KeyRound size={16} className="input-icon" />
                  <input
                    id="forgot-code"
                    name="code"
                    type="text"
                    className="input auth-input forgot-code-input"
                    placeholder="Nhập mã 8 chữ số"
                    value={form.code}
                    onChange={(event) => {
                      const value = event.target.value.replace(/\D/g, '').slice(0, 8);
                      setForm((current) => ({ ...current, code: value }));
                    }}
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    maxLength={8}
                    autoFocus
                    required
                  />
                </div>
                <button
                  type="button"
                  className="forgot-resend-button"
                  onClick={resendCode}
                  disabled={loading}
                >
                  Gửi lại mã
                </button>
              </div>
            )}

            {step === 'password' && (
              <>
                <div className="form-group">
                  <label className="form-label" htmlFor="new-password">Mật khẩu mới</label>
                  <div className="input-wrap">
                    <Lock size={16} className="input-icon" />
                    <input
                      id="new-password"
                      name="newPassword"
                      type={showPassword ? 'text' : 'password'}
                      className="input auth-input forgot-password-input"
                      placeholder="Tối thiểu 6 ký tự"
                      value={form.newPassword}
                      onChange={updateField}
                      autoComplete="new-password"
                      minLength={6}
                      autoFocus
                      required
                    />
                    <button
                      type="button"
                      className="pass-toggle"
                      onClick={() => setShowPassword((visible) => !visible)}
                      aria-label={showPassword ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
                    >
                      {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                    </button>
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label" htmlFor="confirm-password">Xác nhận mật khẩu</label>
                  <div className="input-wrap">
                    <Lock size={16} className="input-icon" />
                    <input
                      id="confirm-password"
                      name="confirmPassword"
                      type={showPassword ? 'text' : 'password'}
                      className="input auth-input forgot-password-input"
                      placeholder="Nhập lại mật khẩu mới"
                      value={form.confirmPassword}
                      onChange={updateField}
                      autoComplete="new-password"
                      minLength={6}
                      required
                    />
                  </div>
                </div>
              </>
            )}

            <button
              type="submit"
              className="btn btn-primary btn-lg forgot-submit-button"
              disabled={loading}
            >
              {loading ? (
                <>
                  <span className="spinner forgot-spinner" />
                  Đang xử lý...
                </>
              ) : (
                <>
                  {step === 'email' ? 'Gửi mã xác thực' : step === 'code' ? 'Xác thực mã' : 'Đổi mật khẩu'}
                  <ArrowRight size={17} />
                </>
              )}
            </button>
          </form>

          <p className="auth-switch">
            Đã nhớ mật khẩu? <Link to="/login">Đăng nhập</Link>
          </p>
        </section>
      </div>
    </main>
  );
}
