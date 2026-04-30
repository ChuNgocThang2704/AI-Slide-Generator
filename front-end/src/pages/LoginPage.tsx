import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { authApi } from '../api/auth';
import toast from 'react-hot-toast';
import { LogIn, UserPlus, Sparkles } from 'lucide-react';
import './Auth.css';

const LoginPage: React.FC = () => {
  const [step, setStep] = useState<'LOGIN' | 'REGISTER' | 'VERIFY'>('LOGIN');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [otp, setOtp] = useState('');
  const [loading, setLoading] = useState(false);
  
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleAuth = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    console.log(`[Auth] Step: ${step}`, { email });

    try {
      if (step === 'LOGIN') {
        const res = await authApi.login({ email, password });
        login(res.data.data.token, res.data.data.user);
        toast.success('Đăng nhập thành công!');
        navigate('/');
      } else if (step === 'REGISTER') {
        await authApi.register({ email, password });
        toast.success('Đã gửi mã OTP đến email của bạn!');
        setStep('VERIFY');
      } else if (step === 'VERIFY') {
        await authApi.verifyCode({ email, code: otp });
        toast.success('Xác thực thành công! Hãy đăng nhập.');
        setStep('LOGIN');
      }
    } catch (error: any) {
      console.error('[Auth Error]', error.response?.data || error);
      const message = error.response?.data?.message || 'Có lỗi xảy ra, vui lòng thử lại';
      toast.error(message);
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleLogin = async () => {
    try {
      const res = await authApi.getGoogleAuthUrl();
      window.location.href = res.data.data.url;
    } catch (error) {
      toast.error('Không thể khởi tạo đăng nhập Google');
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card glass">
        <div className="auth-header">
          <div className="logo-icon">
            <Sparkles size={32} color="var(--primary)" />
          </div>
          <h1>
            {step === 'LOGIN' ? 'Chào mừng trở lại' : 
             step === 'REGISTER' ? 'Tạo tài khoản mới' : 'Xác thực OTP'}
          </h1>
          <p>
            {step === 'LOGIN' ? 'Nhập thông tin để tiếp tục' : 
             step === 'REGISTER' ? 'Bắt đầu hành trình cùng AI' : `Mã đã được gửi tới ${email}`}
          </p>
        </div>

        <form onSubmit={handleAuth} className="auth-form">
          {step !== 'VERIFY' ? (
            <>
              <div className="input-group">
                <label>Email</label>
                <input 
                  type="email" 
                  value={email} 
                  onChange={(e) => setEmail(e.target.value)} 
                  required 
                  placeholder="example@gmail.com"
                />
              </div>

              <div className="input-group">
                <label>Mật khẩu</label>
                <input 
                  type="password" 
                  value={password} 
                  onChange={(e) => setPassword(e.target.value)} 
                  required 
                  placeholder="••••••••"
                />
              </div>
            </>
          ) : (
            <div className="input-group">
              <label>Mã xác thực (OTP)</label>
              <input 
                type="text" 
                value={otp} 
                onChange={(e) => setOtp(e.target.value)} 
                required 
                placeholder="Nhập 8 chữ số"
                maxLength={8}
                style={{ textAlign: 'center', fontSize: '24px', letterSpacing: '4px' }}
              />
            </div>
          )}

          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? 'Đang xử lý...' : 
             step === 'LOGIN' ? 'Đăng nhập' : 
             step === 'REGISTER' ? 'Đăng ký' : 'Xác thực ngay'}
            {step === 'LOGIN' ? <LogIn size={20} /> : <UserPlus size={20} />}
          </button>
        </form>

        {step === 'LOGIN' && (
          <div className="auth-divider">
            <span>hoặc</span>
          </div>
        )}

        {step === 'LOGIN' && (
          <button className="btn-google" onClick={handleGoogleLogin}>
            <img src="https://www.gstatic.com/firebasejs/ui/2.0.0/images/auth/google.svg" alt="Google" />
            Đăng nhập với Google
          </button>
        )}

        <div className="auth-footer">
          <p>
            {step === 'LOGIN' && (
              <>
                Chưa có tài khoản? 
                <button onClick={() => setStep('REGISTER')}>Đăng ký ngay</button>
              </>
            )}
            {step === 'REGISTER' && (
              <>
                Đã có tài khoản? 
                <button onClick={() => setStep('LOGIN')}>Đăng nhập ngay</button>
              </>
            )}
            {step === 'VERIFY' && (
              <>
                Sai email? 
                <button onClick={() => setStep('REGISTER')}>Quay lại</button>
              </>
            )}
          </p>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
