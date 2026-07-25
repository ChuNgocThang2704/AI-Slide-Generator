import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { useAuthStore, useUIStore } from './store';
import { authService } from './services/authService';

import Navbar from './components/layout/Navbar';
import ToastContainer from './components/common/Toast';

import LandingPage from './pages/LandingPage/LandingPage';
import AuthPage from './pages/AuthPage/AuthPage';
import VerifyCodePage from './pages/VerifyCodePage/VerifyCodePage';
import DashboardPage from './pages/DashboardPage/DashboardPage';
import GeneratePage from './pages/GeneratePage/GeneratePage';
import EditorPage from './pages/EditorPage/EditorPage';
import PricingPage from './pages/PricingPage/PricingPage';
import DocumentsPage from './pages/DocumentsPage/DocumentsPage';
import AdminPage from './pages/AdminPage/AdminPage';
import SettingsPage from './pages/SettingsPage/SettingsPage';
import PaymentResultPage from './pages/PaymentResultPage/PaymentResultPage';

function PrivateRoute({ children }) {
  const { isAuthenticated } = useAuthStore();
  return isAuthenticated ? children : <Navigate to="/login" replace />;
}

function PublicOnlyRoute({ children }) {
  const { isAuthenticated } = useAuthStore();
  return !isAuthenticated ? children : <Navigate to="/dashboard" replace />;
}

function Layout({ children, hideNav }) {
  return (
    <>
      {!hideNav && <Navbar />}
      {children}
      <ToastContainer />
    </>
  );
}

function ScrollToTop() {
  const { pathname } = useLocation();

  React.useEffect(() => {
    if ('scrollRestoration' in window.history) {
      window.history.scrollRestoration = 'manual';
    }
  }, []);

  React.useLayoutEffect(() => {
    const root = document.documentElement;
    const previousBehavior = root.style.scrollBehavior;
    root.style.scrollBehavior = 'auto';
    window.scrollTo(0, 0);
    root.scrollTop = 0;
    document.body.scrollTop = 0;
    const frame = window.requestAnimationFrame(() => {
      root.style.scrollBehavior = previousBehavior;
    });
    return () => {
      window.cancelAnimationFrame(frame);
      root.style.scrollBehavior = previousBehavior;
    };
  }, [pathname]);

  return null;
}

function GoogleCallback() {
  const location = useLocation();
  const navigate = useNavigate();
  const { login } = useAuthStore();
  const { addToast } = useUIStore();
  const [error, setError] = React.useState(null);
  const hasRun = React.useRef(false);

  React.useEffect(() => {
    const params = new URLSearchParams(location.search);
    const code = params.get('code');
    
    console.log('GoogleCallback mounted. Search:', location.search);
    
    if (!code) {
      console.warn('GoogleCallback: No code parameter found in URL');
      setError('Không tìm thấy mã xác thực Google');
      addToast('Mã xác thực Google không hợp lệ', 'error');
      navigate('/login', { replace: true });
      return;
    }

    if (hasRun.current) {
      console.log('GoogleCallback: Login already in progress or completed, skipping re-run.');
      return;
    }
    
    hasRun.current = true;

    const processLogin = async () => {
      try {
        console.log('GoogleCallback: Sending code to backend for token exchange...', code);
        const result = await authService.loginWithGoogle(code);
        console.log('GoogleCallback: Backend exchange successful, result:', result);
        
        login(result.user, result.token, result.refreshToken);
        addToast('Đăng nhập bằng Google thành công! 👋', 'success');
        
        console.log('GoogleCallback: Navigating to /dashboard');
        navigate('/dashboard', { replace: true });
      } catch (err) {
        console.error('GoogleCallback: Login process failed. Error detail:', err);
        setError(err.message || 'Đăng nhập Google thất bại');
        addToast(err.message || 'Đăng nhập Google thất bại', 'error');
        navigate('/login', { replace: true });
      }
    };

    processLogin();
  }, [location.search, navigate, login, addToast]);

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      height: '100vh',
      background: '#0d0d1a',
      color: 'white',
      fontFamily: 'sans-serif'
    }}>
      {error ? (
        <div style={{ textAlign: 'center' }}>
          <h2 style={{ color: '#ff6584', marginBottom: 16 }}>Đăng nhập thất bại</h2>
          <p>{error}</p>
        </div>
      ) : (
        <>
          <div className="spinner" style={{ marginBottom: 20, width: 50, height: 50, borderWidth: 4 }}></div>
          <h2>Đang xử lý đăng nhập Google...</h2>
          <p style={{ color: 'rgba(255,255,255,0.5)', marginTop: 8 }}>Vui lòng đợi trong giây lát</p>
        </>
      )}
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <ScrollToTop />
      <Routes>
        {/* Public */}
        <Route path="/" element={<Layout><LandingPage /></Layout>} />
        <Route path="/pricing" element={<Layout><PricingPage /></Layout>} />
        <Route path="/success" element={<PrivateRoute><Layout><PaymentResultPage /></Layout></PrivateRoute>} />
        <Route path="/cancel" element={<PrivateRoute><Layout><PaymentResultPage cancelled /></Layout></PrivateRoute>} />

        {/* Auth only for non-logged-in */}
        <Route path="/login" element={
          <PublicOnlyRoute>
            <Layout hideNav><AuthPage mode="login" /></Layout>
          </PublicOnlyRoute>
        } />
        <Route path="/register" element={
          <PublicOnlyRoute>
            <Layout hideNav><AuthPage mode="register" /></Layout>
          </PublicOnlyRoute>
        } />
        <Route path="/verify-code" element={
          <Layout hideNav><VerifyCodePage /></Layout>
        } />
        <Route path="/api/v1/auth/google/redirect" element={
          <GoogleCallback />
        } />

        {/* Private */}
        <Route path="/dashboard" element={
          <PrivateRoute>
            <Layout><DashboardPage /></Layout>
          </PrivateRoute>
        } />
        <Route path="/generate" element={
          <PrivateRoute>
            <Layout><GeneratePage /></Layout>
          </PrivateRoute>
        } />
        <Route path="/editor/:id" element={
          <PrivateRoute>
            <Layout><EditorPage /></Layout>
          </PrivateRoute>
        } />
        <Route path="/documents" element={
          <PrivateRoute>
            <Layout><DocumentsPage /></Layout>
          </PrivateRoute>
        } />
        <Route path="/settings" element={
          <PrivateRoute>
            <Layout><SettingsPage /></Layout>
          </PrivateRoute>
        } />
        <Route path="/admin" element={
          <PrivateRoute>
            <Layout><AdminPage /></Layout>
          </PrivateRoute>
        } />

        {/* Fallback */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
