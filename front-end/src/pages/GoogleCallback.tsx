import React, { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { authApi } from '../api/auth';
import toast from 'react-hot-toast';
import { Loader2 } from 'lucide-react';

const GoogleCallback: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { login } = useAuth();

  useEffect(() => {
    const code = searchParams.get('code');
    console.log('[Google Auth] Code received:', code);
    
    if (code) {
      handleGoogleAuth(code);
    } else {
      const error = searchParams.get('error');
      toast.error(error || 'Không tìm thấy mã xác thực từ Google');
      navigate('/login');
    }
  }, [searchParams]);

  const handleGoogleAuth = async (code: string) => {
    try {
      const res = await authApi.googleRedirect(code);
      login(res.data.data.token, res.data.data.user);
      toast.success('Đăng nhập Google thành công!');
      navigate('/'); // Chuyển về trang chủ
    } catch (error: any) {
      console.error('[Google Auth Error]', error);
      toast.error(error.response?.data?.message || 'Đăng nhập Google thất bại');
      navigate('/login');
    }
  };

  return (
    <div className="loading-full" style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '20px' }}>
      <Loader2 className="spinner" size={48} color="var(--primary)" />
      <h2>Đang xác thực với Google...</h2>
      <p style={{ color: 'var(--text-muted)' }}>Vui lòng đợi trong giây lát</p>
    </div>
  );
};

export default GoogleCallback;
