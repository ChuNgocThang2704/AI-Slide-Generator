import React from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '../../store';
import { authService } from '../../services/authService';
import {
  Sparkles, LayoutDashboard, LogOut, User, CreditCard,
  ChevronDown, Menu, X, FileText, ShieldAlert
} from 'lucide-react';
import './Navbar.css';

export default function Navbar() {
  const { user, isAuthenticated, logout } = useAuthStore();
  const navigate = useNavigate();
  const location = useLocation();
  const [menuOpen, setMenuOpen] = React.useState(false);
  const [dropdownOpen, setDropdownOpen] = React.useState(false);
  const dropRef = React.useRef(null);

  React.useEffect(() => {
    const handler = (e) => {
      if (dropRef.current && !dropRef.current.contains(e.target)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const handleLogout = async () => {
    try {
      await authService.logout();
    } catch (err) {
      console.error('Lỗi khi gọi API đăng xuất:', err);
    } finally {
      logout();
      navigate('/');
      setDropdownOpen(false);
    }
  };

  const isActive = (path) => location.pathname === path;

  return (
    <nav className="navbar">
      <div className="navbar-inner">
        {/* Logo */}
        <Link to="/" className="navbar-logo">
          <div className="logo-icon">
            <Sparkles size={18} />
          </div>
          <span className="logo-text">Lec<span className="logo-accent">Gen</span></span>
        </Link>

        {/* Desktop Nav Links */}
        {!isAuthenticated && (
          <div className="navbar-links">
            <Link to="/" className={`nav-link ${isActive('/') ? 'active' : ''}`}>Trang chủ</Link>
            <Link to="/pricing" className={`nav-link ${isActive('/pricing') ? 'active' : ''}`}>Bảng giá</Link>
            <a href="#features" className="nav-link">Tính năng</a>
          </div>
        )}

        {isAuthenticated && (
          <div className="navbar-links">
            <Link to="/dashboard" className={`nav-link ${isActive('/dashboard') ? 'active' : ''}`}>
              <LayoutDashboard size={15} /> Dashboard
            </Link>
            <Link to="/generate" className={`nav-link ${isActive('/generate') ? 'active' : ''}`}>
              <Sparkles size={15} /> Tạo slide
            </Link>
            <Link to="/documents" className={`nav-link ${isActive('/documents') ? 'active' : ''}`}>
              <FileText size={15} /> Tài liệu
            </Link>
            {user?.roles?.some(r => r.name === 'ADMIN' || r.code === 'ADMIN' || r.name === 'ROLE_ADMIN' || user?.email === 'admin@aislide.com') && (
              <Link to="/admin" className={`nav-link ${isActive('/admin') ? 'active' : ''}`}>
                <ShieldAlert size={15} /> Admin
              </Link>
            )}
            <Link to="/pricing" className={`nav-link ${isActive('/pricing') ? 'active' : ''}`}>Bảng giá</Link>
          </div>
        )}

        {/* Right section */}
        <div className="navbar-actions">
          {isAuthenticated ? (
            <div className="user-menu" ref={dropRef}>
              <button className="user-btn" onClick={() => setDropdownOpen(!dropdownOpen)}>
                <img src={user?.avatar} alt={user?.name} className="user-avatar" />
                <span className="user-name">{user?.name}</span>
                <ChevronDown size={14} className={`chevron ${dropdownOpen ? 'open' : ''}`} />
              </button>
              {dropdownOpen && (
                <div className="user-dropdown">
                  <div className="dropdown-header">
                    <img src={user?.avatar} alt={user?.name} className="dropdown-avatar" />
                    <div className="dropdown-user-copy">
                      <div className="dropdown-name">{user?.name}</div>
                      <div className="dropdown-email">{user?.email}</div>
                    </div>
                  </div>
                  <div className="dropdown-divider" />
                  <Link to="/dashboard" className="dropdown-item" onClick={() => setDropdownOpen(false)}>
                    <LayoutDashboard size={15} /> Dashboard
                  </Link>
                  <Link to="/documents" className="dropdown-item" onClick={() => setDropdownOpen(false)}>
                    <FileText size={15} /> Tài liệu
                  </Link>
                  {user?.roles?.some(r => r.name === 'ADMIN' || r.code === 'ADMIN' || r.name === 'ROLE_ADMIN' || user?.email === 'admin@aislide.com') && (
                    <Link to="/admin" className="dropdown-item" onClick={() => setDropdownOpen(false)}>
                      <ShieldAlert size={15} /> Quản trị Admin
                    </Link>
                  )}
                  <Link to="/settings" className="dropdown-item" onClick={() => setDropdownOpen(false)}>
                    <User size={15} /> Tài khoản
                  </Link>
                  <Link to="/pricing" className="dropdown-item" onClick={() => setDropdownOpen(false)}>
                    <CreditCard size={15} /> Nâng cấp gói
                  </Link>
                  <div className="dropdown-divider" />
                  <button className="dropdown-item danger" onClick={handleLogout}>
                    <LogOut size={15} /> Đăng xuất
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div className="flex gap-3 items-center">
              <Link to="/login" className="btn btn-ghost btn-sm">Đăng nhập</Link>
              <Link to="/register" className="btn btn-primary btn-sm">
                <Sparkles size={14} /> Dùng thử miễn phí
              </Link>
            </div>
          )}

          {/* Mobile hamburger */}
          <button className="mobile-menu-btn" onClick={() => setMenuOpen(!menuOpen)}>
            {menuOpen ? <X size={22} /> : <Menu size={22} />}
          </button>
        </div>
      </div>

      {/* Mobile menu */}
      {menuOpen && (
        <div className="mobile-menu">
          <Link to="/" className="mobile-link" onClick={() => setMenuOpen(false)}>Trang chủ</Link>
          <Link to="/pricing" className="mobile-link" onClick={() => setMenuOpen(false)}>Bảng giá</Link>
          {isAuthenticated ? (
            <>
              <Link to="/dashboard" className="mobile-link" onClick={() => setMenuOpen(false)}>Dashboard</Link>
              <Link to="/generate" className="mobile-link" onClick={() => setMenuOpen(false)}>Tạo slide</Link>
              <Link to="/documents" className="mobile-link" onClick={() => setMenuOpen(false)}>Tài liệu</Link>
              {user?.roles?.some(r => r.name === 'ADMIN' || r.code === 'ADMIN' || r.name === 'ROLE_ADMIN' || user?.email === 'admin@aislide.com') && (
                <Link to="/admin" className="mobile-link" onClick={() => setMenuOpen(false)}>Admin</Link>
              )}
              <button className="mobile-link danger-link" onClick={handleLogout}>Đăng xuất</button>
            </>
          ) : (
            <>
              <Link to="/login" className="mobile-link" onClick={() => setMenuOpen(false)}>Đăng nhập</Link>
              <Link to="/register" className="mobile-link" onClick={() => setMenuOpen(false)}>Đăng ký</Link>
            </>
          )}
        </div>
      )}
    </nav>
  );
}
