import React from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  LayoutDashboard,
  CirclePlus,
  FileText,
  LogOut,
  Sparkles,
  ChevronRight,
  Settings, UserIcon
} from 'lucide-react';
import './Layout.css';

const Layout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user, logout, isAdmin, roles } = useAuth();
  useNavigate();
  const location = useLocation();

  const menuItems = [
    { icon: <LayoutDashboard size={20} />, label: 'Dự án của tôi', path: '/' },
    { icon: <CirclePlus size={20} />, label: 'Tạo mới', path: '/create' },
    { icon: <FileText size={20} />, label: 'Tài liệu nguồn', path: '/documents' },
  ];

  if (isAdmin) {
    menuItems.push({ icon: <Settings size={20} />, label: 'Cấu hình AI', path: '/admin/configs' });
  }

  return (
    <div className="app-layout">
      <aside className="sidebar glass">
        <div className="sidebar-header">
          <Sparkles color="var(--primary)" size={28} />
          <span>AI Slide</span>
        </div>

        <nav className="sidebar-nav">
          {menuItems.map((item) => (
            <Link 
              key={item.path} 
              to={item.path} 
              className={`nav-item ${location.pathname === item.path ? 'active' : ''}`}
            >
              {item.icon}
              <span>{item.label}</span>
              {location.pathname === item.path && <div className="active-indicator" />}
            </Link>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="user-profile">
            <div className="user-avatar">
              <UserIcon size={20} />
            </div>
            <div className="user-info">
              <span className="username">{user?.username}</span>
              <span className="user-role">{roles[0] || 'User'}</span>
            </div>
          </div>
          <button className="logout-btn" onClick={logout} title="Đăng xuất">
            <LogOut size={20} />
          </button>
        </div>
      </aside>

      <main className="main-content">
        <header className="main-header glass">
          <div className="breadcrumb">
            <span>Ứng dụng</span>
            <ChevronRight size={16} />
            <span className="current">
              {menuItems.find(i => i.path === location.pathname)?.label || 'Chi tiết'}
            </span>
          </div>
        </header>
        <div className="page-content">
          {children}
        </div>
      </main>
    </div>
  );
};

export default Layout;
