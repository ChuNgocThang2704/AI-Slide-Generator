import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore, useUIStore } from '../../store';
import { adminService } from '../../services/adminService';
import { 
  Users, Settings, ShieldAlert, Trash2, Plus, 
  Check, AlertTriangle, ShieldCheck, Loader2,
  TrendingUp, DollarSign, BarChart3, Activity,
  Calendar, RefreshCw, Zap, AlertCircle,
  ArrowUpRight, ArrowDownRight, Sparkles, Clock, CreditCard
} from 'lucide-react';
import './AdminPage.css';

export default function AdminPage() {
  const { user } = useAuthStore();
  const { addToast } = useUIStore();
  const navigate = useNavigate();

  const [activeTab, setActiveTab] = useState('revenue-stats');
  const [loading, setLoading] = useState(false);

  // Date Filter State (default last 30 days)
  const [startDate, setStartDate] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() - 30);
    return d.toISOString().split('T')[0];
  });
  const [endDate, setEndDate] = useState(() => new Date().toISOString().split('T')[0]);

  // Dashboard Data States
  const [revenueData, setRevenueData] = useState(null);
  const [usersDashboardData, setUsersDashboardData] = useState(null);

  // States for management tabs
  const [usersList, setUsersList] = useState([]);
  const [rolesList, setRolesList] = useState([]);
  const [permsList, setPermsList] = useState([]);
  const [aiConfigs, setAiConfigs] = useState([
    {
      roleCode: 'USER_FREE',
      configName: 'Gói Miễn Phí',
      language: 'Vietnamese',
      tone: 'Professional',
      maxProjectsPerDay: 3,
      minPagesPerProject: 5,
      maxPagesPerProject: 10
    },
    {
      roleCode: 'USER_PRO',
      configName: 'Gói Chuyên Nghiệp',
      language: 'Vietnamese',
      tone: 'Professional',
      maxProjectsPerDay: 20,
      minPagesPerProject: 5,
      maxPagesPerProject: 25
    }
  ]);

  // Privilege Check & Initial Load
  useEffect(() => {
    const isAdmin = user?.roles?.some(r => r.name === 'ADMIN' || r.code === 'ADMIN' || r.name === 'ROLE_ADMIN') || user?.email === 'admin@aislide.com';
    if (!isAdmin) {
      addToast('Bạn không có quyền truy cập trang quản trị!', 'error');
      navigate('/dashboard');
    } else {
      loadTabData();
    }
  }, [activeTab]);

  const loadTabData = async (customStart = startDate, customEnd = endDate) => {
    setLoading(true);
    try {
      if (activeTab === 'revenue-stats') {
        try {
          const data = await adminService.getRevenueDashboard(customStart, customEnd);
          if (data && data.summary) {
            setRevenueData(data);
          } else {
            setRevenueData(getMockRevenueData());
          }
        } catch (e) {
          console.warn('[AdminPage] Gọi API Revenue Dashboard thất bại, chuyển dùng Mock data:', e);
          setRevenueData(getMockRevenueData());
        }
      } else if (activeTab === 'user-stats') {
        try {
          const data = await adminService.getUsersDashboard(customStart, customEnd);
          if (data && data.summary) {
            setUsersDashboardData(data);
          } else {
            setUsersDashboardData(getMockUsersDashboardData());
          }
        } catch (e) {
          console.warn('[AdminPage] Gọi API Users Dashboard thất bại, chuyển dùng Mock data:', e);
          setUsersDashboardData(getMockUsersDashboardData());
        }
      } else if (activeTab === 'users') {
        const data = await adminService.getUsers(0, 100);
        if (data && (data.items || data.content)) {
          setUsersList(data.items || data.content || []);
        } else {
          setUsersList(getMockUsers());
        }
      } else if (activeTab === 'roles') {
        const rolesData = await adminService.getRoles();
        const permsData = await adminService.getPermissions();
        setRolesList(rolesData || getMockRoles());
        setPermsList(permsData || getMockPermissions());
      } else if (activeTab === 'configs') {
        try {
          const configs = await adminService.getAIConfigs();
          if (configs && configs.length > 0) {
            setAiConfigs(configs);
          }
        } catch (e) {
          console.log('Sử dụng cấu hình mặc định cho gói AI');
        }
      }
    } catch (err) {
      console.error(err);
      if (activeTab === 'users') setUsersList(getMockUsers());
      if (activeTab === 'roles') {
        setRolesList(getMockRoles());
        setPermsList(getMockPermissions());
      }
    } finally {
      setLoading(false);
    }
  };

  // Quick Preset Date Selectors
  const handleApplyPreset = (days) => {
    const end = new Date().toISOString().split('T')[0];
    let start;
    if (days === 'year') {
      start = `${new Date().getFullYear()}-01-01`;
    } else {
      const d = new Date();
      d.setDate(d.getDate() - days);
      start = d.toISOString().split('T')[0];
    }
    setStartDate(start);
    setEndDate(end);
    loadTabData(start, end);
  };

  const handleSyncConfigs = async () => {
    setLoading(true);
    try {
      await adminService.syncAIConfigs(aiConfigs);
      addToast('🎉 Đồng bộ cấu hình AI thành công!', 'success');
    } catch (err) {
      addToast(err.message || 'Đồng bộ cấu hình thất bại', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleConfigChange = (index, field, value) => {
    setAiConfigs(prev => {
      const updated = [...prev];
      updated[index] = { ...updated[index], [field]: value };
      return updated;
    });
  };

  const handleDeleteUser = async (userId) => {
    if (!window.confirm('Bạn có chắc muốn xóa tài khoản này?')) return;
    try {
      await adminService.deleteUser(userId);
      setUsersList(prev => prev.filter(u => u.id !== userId));
      addToast('Xóa người dùng thành công', 'success');
    } catch (err) {
      addToast(err.message || 'Xóa người dùng thất bại', 'error');
    }
  };

  // Helper formatting functions
  const formatCurrency = (amount, currency = 'VND') => {
    if (amount === undefined || amount === null) return '0';
    if (currency === 'VND') {
      return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(amount);
    }
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(amount);
  };

  const renderGrowthBadge = (growth) => {
    const isPositive = growth >= 0;
    return (
      <span className={`growth-badge ${isPositive ? 'positive' : 'negative'}`}>
        {isPositive ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}
        {Math.abs(growth)}%
      </span>
    );
  };

  return (
    <div className="admin-page page-enter" style={{ marginTop: 0, paddingTop: 12 }}>
      <div className="container" style={{ marginTop: 0, paddingTop: 0 }}>
        
        {/* Header */}
        <div className="admin-header" style={{ marginTop: 0, paddingTop: 0, marginBottom: 20 }}>
          <h1 className="admin-title" style={{ marginTop: 0, paddingTop: 0 }}>
            🛡️ Hệ thống <span className="gradient-text">Quản trị Admin</span>
          </h1>
          <p className="admin-desc">Báo cáo doanh thu, chỉ số AI Usage, phân tích thành viên và phân quyền hệ thống</p>
        </div>

        <div className="admin-layout">
          {/* Left Sidebar Menu */}
          <div className="admin-sidebar">
            <div className="sidebar-group-title">BÁO CÁO THỐNG KÊ</div>
            <button 
              className={`admin-menu-btn ${activeTab === 'revenue-stats' ? 'active' : ''}`}
              onClick={() => setActiveTab('revenue-stats')}
            >
              <TrendingUp size={16} />
              <span>Doanh thu & Giao dịch</span>
            </button>
            <button 
              className={`admin-menu-btn ${activeTab === 'user-stats' ? 'active' : ''}`}
              onClick={() => setActiveTab('user-stats')}
            >
              <Activity size={16} />
              <span>Hoạt động & AI Usage</span>
            </button>

            <div className="sidebar-group-title" style={{ marginTop: 16 }}>QUẢN LÝ HỆ THỐNG</div>
            <button 
              className={`admin-menu-btn ${activeTab === 'users' ? 'active' : ''}`}
              onClick={() => setActiveTab('users')}
            >
              <Users size={16} />
              <span>Quản lý thành viên</span>
            </button>
            <button 
              className={`admin-menu-btn ${activeTab === 'roles' ? 'active' : ''}`}
              onClick={() => setActiveTab('roles')}
            >
              <ShieldAlert size={16} />
              <span>Vai trò & Quyền hạn</span>
            </button>
          </div>

          {/* Right Main Content */}
          <div className="admin-content-card">
            {loading && (
              <div className="admin-loading-overlay">
                <Loader2 className="spin" size={24} />
                <span>Đang tải dữ liệu báo cáo...</span>
              </div>
            )}

            {/* TAB 1: DASHBOARD DOANH THU & GIAO DỊCH */}
            {activeTab === 'revenue-stats' && (
              <div className="tab-pane">
                {/* Header & Date Filter */}
                <div className="pane-header-with-filter">
                  <div>
                    <h3>📊 Báo cáo Doanh Thu & Giao Dịch</h3>
                    <p>Theo dõi doanh thu VNĐ/USD, số gói cước đang hoạt động và trạng thái giao dịch.</p>
                  </div>
                  <div className="date-filter-bar">
                    <div className="date-inputs">
                      <input 
                        type="date" 
                        value={startDate} 
                        onChange={(e) => setStartDate(e.target.value)} 
                        className="date-input"
                      />
                      <span>đến</span>
                      <input 
                        type="date" 
                        value={endDate} 
                        onChange={(e) => setEndDate(e.target.value)} 
                        className="date-input"
                      />
                    </div>
                    <div className="filter-presets">
                      <button className="preset-btn" onClick={() => handleApplyPreset(7)}>7 ngày</button>
                      <button className="preset-btn" onClick={() => handleApplyPreset(30)}>30 ngày</button>
                      <button className="preset-btn" onClick={() => handleApplyPreset('year')}>Năm nay</button>
                      <button className="refresh-btn" onClick={() => loadTabData(startDate, endDate)}>
                        <RefreshCw size={14} />
                      </button>
                    </div>
                  </div>
                </div>

                {revenueData && (
                  <div className="dashboard-body">
                    {/* Summary KPI Cards */}
                    <div className="kpi-grid">
                      <div className="kpi-card glass-panel">
                        <div className="kpi-icon-wrap vnd">
                          <DollarSign size={20} />
                        </div>
                        <div className="kpi-info">
                          <span className="kpi-label">Doanh thu VNĐ (PayOS)</span>
                          <div className="kpi-value-row">
                            <span className="kpi-value">{formatCurrency(revenueData.summary?.total_revenue_vnd?.current_value, 'VND')}</span>
                            {renderGrowthBadge(revenueData.summary?.total_revenue_vnd?.growth ?? 0)}
                          </div>
                          <span className="kpi-subtext">Kỳ trước: {formatCurrency(revenueData.summary?.total_revenue_vnd?.previous_value, 'VND')}</span>
                        </div>
                      </div>

                      <div className="kpi-card glass-panel">
                        <div className="kpi-icon-wrap usd">
                          <CreditCard size={20} />
                        </div>
                        <div className="kpi-info">
                          <span className="kpi-label">Doanh thu USD (Stripe)</span>
                          <div className="kpi-value-row">
                            <span className="kpi-value">{formatCurrency(revenueData.summary?.total_revenue_usd?.current_value, 'USD')}</span>
                            {renderGrowthBadge(revenueData.summary?.total_revenue_usd?.growth ?? 0)}
                          </div>
                          <span className="kpi-subtext">Kỳ trước: {formatCurrency(revenueData.summary?.total_revenue_usd?.previous_value, 'USD')}</span>
                        </div>
                      </div>

                      <div className="kpi-card glass-panel">
                        <div className="kpi-icon-wrap subs">
                          <Sparkles size={20} />
                        </div>
                        <div className="kpi-info">
                          <span className="kpi-label">Gói cước đang hoạt động</span>
                          <div className="kpi-value-row">
                            <span className="kpi-value">{revenueData.summary?.active_subscriptions?.current_value ?? 0}</span>
                            {renderGrowthBadge(revenueData.summary?.active_subscriptions?.growth ?? 0)}
                          </div>
                          <span className="kpi-subtext">Kỳ trước: {revenueData.summary?.active_subscriptions?.previous_value ?? 0} gói</span>
                        </div>
                      </div>
                    </div>

                    {/* Package & Transaction Distribution */}
                    <div className="dashboard-grid-2">
                      <div className="panel-card glass-panel">
                        <h4 className="panel-title">📦 Phân bổ Gói dịch vụ (Package Distribution)</h4>
                        <div className="distribution-list">
                          {(revenueData.package_distribution || []).map((pkg, idx) => {
                            const name = pkg.package_name || pkg.package_code || 'Gói khác';
                            const count = pkg.count ?? pkg.total ?? 0;
                            const percent = pkg.percent ?? Math.min(100, count * 10);
                            const tagClass = name.toLowerCase().includes('pro') ? 'pro' : name.toLowerCase().includes('ultra') ? 'ultra' : 'free';
                            return (
                              <div key={idx} className="dist-item">
                                <div className="dist-header">
                                  <span className={`pkg-tag ${tagClass}`}>{name}</span>
                                  <span className="dist-count">{count} đăng ký ({percent}%)</span>
                                </div>
                                <div className="progress-bar-wrap">
                                  <div className={`progress-fill ${tagClass}`} style={{ width: `${Math.min(100, percent)}%` }} />
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>

                      <div className="panel-card glass-panel">
                        <h4 className="panel-title">💳 Trạng thái Giao dịch (Transaction Status)</h4>
                        <div className="tx-status-grid">
                          {(revenueData.transaction_status_distribution || []).map((tx, idx) => {
                            const name = tx.package_name || tx.status || 'Khác';
                            const count = tx.count ?? tx.total ?? 0;
                            const percent = tx.percent ?? 0;
                            const isSuccess = name.toUpperCase().includes('SUCCESS') || name.includes('Thành công');
                            const isPending = name.toUpperCase().includes('PENDING') || name.includes('Đang xử lý');
                            const statusClass = isSuccess ? 'success' : isPending ? 'pending' : 'failed';
                            return (
                              <div key={idx} className={`tx-status-box ${statusClass}`}>
                                <span className="tx-status-name" style={{ fontSize: '0.7rem', textAlign: 'center' }}>{name}</span>
                                <span className="tx-status-count">{count}</span>
                                <span className="tx-status-sub">{percent}% giao dịch</span>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* TAB 2: DASHBOARD HOẠT ĐỘNG NGƯỜI DÙNG & AI USAGE */}
            {activeTab === 'user-stats' && (
              <div className="tab-pane">
                {/* Header & Date Filter */}
                <div className="pane-header-with-filter">
                  <div>
                    <h3>📈 Báo cáo Hoạt Động Người Dùng & AI Usage</h3>
                    <p>Thống kê số lượng Slide tạo ra, tần suất sử dụng AI và cảnh báo hệ thống.</p>
                  </div>
                  <div className="date-filter-bar">
                    <div className="date-inputs">
                      <input 
                        type="date" 
                        value={startDate} 
                        onChange={(e) => setStartDate(e.target.value)} 
                        className="date-input"
                      />
                      <span>đến</span>
                      <input 
                        type="date" 
                        value={endDate} 
                        onChange={(e) => setEndDate(e.target.value)} 
                        className="date-input"
                      />
                    </div>
                    <div className="filter-presets">
                      <button className="preset-btn" onClick={() => handleApplyPreset(7)}>7 ngày</button>
                      <button className="preset-btn" onClick={() => handleApplyPreset(30)}>30 ngày</button>
                      <button className="preset-btn" onClick={() => handleApplyPreset('year')}>Năm nay</button>
                      <button className="refresh-btn" onClick={() => loadTabData(startDate, endDate)}>
                        <RefreshCw size={14} />
                      </button>
                    </div>
                  </div>
                </div>

                {usersDashboardData && (
                  <div className="dashboard-body">
                    {/* System Warnings Banners */}
                    {usersDashboardData.user_warnings && (
                      <div className="warnings-container">
                        <div className="warning-banner inactive">
                          <AlertCircle size={18} />
                          <div>
                            <strong>{usersDashboardData.user_warnings.inactive_users_30d ?? 0}</strong> người dùng không hoạt động trong 30 ngày qua
                          </div>
                        </div>
                        <div className="warning-banner expiring">
                          <Clock size={18} />
                          <div>
                            <strong>{usersDashboardData.user_warnings.package_expiring_3d ?? 0}</strong> gói cước sắp hết hạn trong 3 ngày tới
                          </div>
                        </div>
                        <div className="warning-banner unverified">
                          <AlertTriangle size={18} />
                          <div>
                            <strong>{usersDashboardData.user_warnings.unverified_emails ?? 0}</strong> tài khoản chưa xác thực Email OTP
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Summary KPI Cards */}
                    <div className="kpi-grid">
                      <div className="kpi-card glass-panel">
                        <div className="kpi-icon-wrap users">
                          <Users size={20} />
                        </div>
                        <div className="kpi-info">
                          <span className="kpi-label">Tổng người dùng mới</span>
                          <div className="kpi-value-row">
                            <span className="kpi-value">{usersDashboardData.summary?.total_users?.current_value ?? 0}</span>
                            {renderGrowthBadge(usersDashboardData.summary?.total_users?.growth ?? 0)}
                          </div>
                          <span className="kpi-subtext">Kỳ trước: {usersDashboardData.summary?.total_users?.previous_value ?? 0} người</span>
                        </div>
                      </div>

                      <div className="kpi-card glass-panel">
                        <div className="kpi-icon-wrap slides">
                          <Zap size={20} />
                        </div>
                        <div className="kpi-info">
                          <span className="kpi-label">Tổng Slide AI đã tạo</span>
                          <div className="kpi-value-row">
                            <span className="kpi-value">{usersDashboardData.summary?.slides_generated?.current_value ?? 0}</span>
                            {renderGrowthBadge(usersDashboardData.summary?.slides_generated?.growth ?? 0)}
                          </div>
                          <span className="kpi-subtext">Kỳ trước: {usersDashboardData.summary?.slides_generated?.previous_value ?? 0} slide</span>
                        </div>
                      </div>

                      <div className="kpi-card glass-panel">
                        <div className="kpi-icon-wrap avg">
                          <BarChart3 size={20} />
                        </div>
                        <div className="kpi-info">
                          <span className="kpi-label">Trung bình Slide / Người dùng</span>
                          <div className="kpi-value-row">
                            <span className="kpi-value">{usersDashboardData.summary?.average_slides_per_user?.current_value ?? 0}</span>
                            {renderGrowthBadge(usersDashboardData.summary?.average_slides_per_user?.growth ?? 0)}
                          </div>
                          <span className="kpi-subtext">Kỳ trước: {usersDashboardData.summary?.average_slides_per_user?.previous_value ?? 0} slide/user</span>
                        </div>
                      </div>
                    </div>

                    {/* Charts & Top Users */}
                    <div className="dashboard-grid-2">
                      {/* Daily Slide Generation Chart */}
                      <div className="panel-card glass-panel">
                        <h4 className="panel-title">📈 Xu hướng tạo Slide theo ngày (Daily AI Usage)</h4>
                        <div className="chart-bars-wrap">
                          {(usersDashboardData.daily_slides_chart || []).slice(-10).map((item, idx) => (
                            <div key={item.date || idx} className="chart-bar-item">
                              <div className="bar-track">
                                <div 
                                  className="bar-fill" 
                                  style={{ height: `${Math.min(100, Math.max(15, (item.total_slides || 0) * 8))}%` }}
                                  title={`${item.total_slides || 0} slide vào ${item.date}`}
                                />
                              </div>
                              <span className="bar-label">{item.date?.slice(5) || `Ngày ${idx+1}`}</span>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Top Active Users Leaderboard */}
                      <div className="panel-card glass-panel">
                        <h4 className="panel-title">👑 Top Người Dùng Hoạt Động Năng Nổ Nhất</h4>
                        <div className="table-wrap mini-table">
                          <table className="admin-table">
                            <thead>
                              <tr>
                                <th>Email</th>
                                <th>Gói cước</th>
                                <th>Số Slide</th>
                                <th>Tăng trưởng</th>
                              </tr>
                            </thead>
                            <tbody>
                              {(usersDashboardData.top_active_users || []).map((u, idx) => (
                                <tr key={u.email || idx}>
                                  <td><strong>{u.email}</strong></td>
                                  <td>
                                    <span className={`pkg-tag ${u.package_tier?.toLowerCase()}`}>
                                      {u.package_tier || 'FREE'}
                                    </span>
                                  </td>
                                  <td><strong>{u.slides_count}</strong> slide</td>
                                  <td>{renderGrowthBadge(u.growth ?? 0)}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* TAB: QUẢN LÝ THÀNH VIÊN */}
            {activeTab === 'users' && (
              <div className="tab-pane">
                <div className="pane-header">
                  <h3>👥 Quản lý thành viên hệ thống</h3>
                  <p>Xem danh sách tài khoản đăng ký, lịch sử đăng nhập cuối và thu hồi/xóa tài khoản.</p>
                </div>

                <div className="table-wrap">
                  <table className="admin-table">
                    <thead>
                      <tr>
                        <th>Tên người dùng</th>
                        <th>Email</th>
                        <th>Gói cước</th>
                        <th>Trạng thái</th>
                        <th>Thao tác</th>
                      </tr>
                    </thead>
                    <tbody>
                      {usersList.map(u => (
                        <tr key={u.id}>
                          <td><strong>{u.fullName || u.username || 'N/A'}</strong></td>
                          <td>{u.email}</td>
                          <td>
                            <span className={`role-badge ${u.roles?.some(r => r.name === 'USER_PRO' || r.code === 'USER_PRO') ? 'pro' : 'free'}`}>
                              {u.roles?.some(r => r.name === 'USER_PRO' || r.code === 'USER_PRO') ? 'Pro User' : 'Free User'}
                            </span>
                          </td>
                          <td>
                            <span className={`status-dot ${u.status === 'ACTIVE' || u.status === 'active' || u.status === undefined ? 'active' : 'inactive'}`}>
                              {u.status || 'ACTIVE'}
                            </span>
                          </td>
                          <td>
                            <button 
                              className="btn btn-ghost btn-xs danger-hover"
                              onClick={() => handleDeleteUser(u.id)}
                              disabled={u.email === user?.email}
                            >
                              <Trash2 size={13} />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* TAB: VAI TRÒ & QUYỀN HẠN */}
            {activeTab === 'roles' && (
              <div className="tab-pane">
                <div className="pane-header">
                  <h3>🛡️ Phân quyền chức năng (RBAC)</h3>
                  <p>Xem và tùy chọn các quyền hạn chi tiết gắn với từng nhóm vai trò thành viên.</p>
                </div>

                <div className="rbac-grid">
                  <div className="rbac-section">
                    <h4>Danh sách Quyền (Permissions)</h4>
                    <div className="rbac-list">
                      {permsList.map(p => (
                        <div key={p.name || p.code} className="rbac-item">
                          <ShieldCheck size={14} className="doc-icon-color" />
                          <div>
                            <strong>{p.name || p.code}</strong>
                            <span>{p.description || 'Không có mô tả'}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="rbac-section">
                    <h4>Vai trò (Roles)</h4>
                    <div className="rbac-list">
                      {rolesList.map(r => (
                        <div key={r.name || r.code} className="rbac-item card-style">
                          <div>
                            <strong>🔑 {r.name || r.code}</strong>
                            <span>{r.description || 'Không có mô tả'}</span>
                            <div className="rbac-badge-list">
                              {(r.permissions || []).map(p => (
                                <span key={p.name || p.code} className="rbac-tag">{p.name || p.code}</span>
                              ))}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}

          </div>
        </div>

      </div>
    </div>
  );
}

// ── FAILSAFE MOCK DATA FOR REVENUE DASHBOARD ──
function getMockRevenueData() {
  return {
    summary: {
      total_revenue_vnd: { current_value: 12450000, previous_value: 9800000, growth: 27.0 },
      total_revenue_usd: { current_value: 420, previous_value: 350, growth: 20.0 },
      active_subscriptions: { current_value: 86, previous_value: 65, growth: 32.3 }
    },
    package_distribution: [
      { package_code: 'PRO', count: 48 },
      { package_code: 'ULTRA', count: 22 },
      { package_code: 'FREE', count: 16 }
    ],
    transaction_status_distribution: [
      { status: 'SUCCESS', count: 112 },
      { status: 'PENDING', count: 8 },
      { status: 'FAILED', count: 3 }
    ]
  };
}

// ── FAILSAFE MOCK DATA FOR USERS DASHBOARD ──
function getMockUsersDashboardData() {
  return {
    summary: {
      total_users: { current_value: 340, previous_value: 280, growth: 21.4 },
      slides_generated: { current_value: 1420, previous_value: 1100, growth: 29.1 },
      average_slides_per_user: { current_value: 4.2, previous_value: 3.9, growth: 7.7 }
    },
    user_warnings: {
      inactive_users_30d: 12,
      package_expiring_3d: 5,
      unverified_emails: 3
    },
    daily_slides_chart: [
      { date: '2026-08-01', total_slides: 42 },
      { date: '2026-08-02', total_slides: 58 },
      { date: '2026-08-03', total_slides: 65 },
      { date: '2026-08-04', total_slides: 78 },
      { date: '2026-08-05', total_slides: 90 },
      { date: '2026-08-06', total_slides: 84 },
      { date: '2026-08-07', total_slides: 105 }
    ],
    top_active_users: [
      { email: 'chuthanglsz@gmail.com', package_tier: 'PRO', slides_count: 145, growth: 18.5 },
      { email: 'userpro@example.com', package_tier: 'ULTRA', slides_count: 112, growth: 12.0 },
      { email: 'teacher.nguyen@edu.vn', package_tier: 'PRO', slides_count: 98, growth: 25.4 },
      { email: 'marketer@company.com', package_tier: 'PRO', slides_count: 76, growth: -5.2 },
      { email: 'student.hieu@hust.edu.vn', package_tier: 'FREE', slides_count: 54, growth: 40.0 }
    ]
  };
}

function getMockUsers() {
  return [
    { id: 'u1', email: 'admin@aislide.com', fullName: 'Hệ Thống Admin', status: 'ACTIVE', roles: [{ code: 'ADMIN', name: 'ADMIN' }] },
    { id: 'u2', email: 'chuthanglsz@gmail.com', fullName: 'Chu Thắng', status: 'ACTIVE', roles: [{ code: 'USER_FREE', name: 'USER_FREE' }] },
    { id: 'u3', email: 'userpro@example.com', fullName: 'Trần Văn Pro', status: 'ACTIVE', roles: [{ code: 'USER_PRO', name: 'USER_PRO' }] },
    { id: 'u4', email: 'banneduser@example.com', fullName: 'Tài Khoản Spamer', status: 'BANNED', roles: [{ code: 'USER_FREE', name: 'USER_FREE' }] }
  ];
}

function getMockRoles() {
  return [
    { 
      code: 'ADMIN', 
      name: 'ADMIN', 
      description: 'Quản trị viên toàn quyền hệ thống', 
      permissions: [{ code: 'EXPORT_PPTX' }, { code: 'EXPORT_PDF' }, { code: 'GEN_IMAGE_FLUX' }, { code: 'SYNC_AI_CONFIGS' }] 
    },
    { 
      code: 'USER_PRO', 
      name: 'USER_PRO', 
      description: 'Thành viên gói chuyên nghiệp trả phí', 
      permissions: [{ code: 'EXPORT_PPTX' }, { code: 'EXPORT_PDF' }, { code: 'GEN_IMAGE_FLUX' }] 
    },
    { 
      code: 'USER_FREE', 
      name: 'USER_FREE', 
      description: 'Thành viên dùng thử miễn phí mặc định', 
      permissions: [{ code: 'EXPORT_PDF' }] 
    }
  ];
}

function getMockPermissions() {
  return [
    { code: 'EXPORT_PPTX', name: 'Xuất slide PPTX', description: 'Cho phép xuất tệp PowerPoint vật lý về máy' },
    { code: 'EXPORT_PDF', name: 'Xuất slide PDF', description: 'Cho phép convert slide sang file PDF' },
    { code: 'GEN_IMAGE_FLUX', name: 'Sinh ảnh FLUX AI', description: 'Quyền tạo ảnh minh họa chất lượng cao bằng FLUX' },
    { code: 'SYNC_AI_CONFIGS', name: 'Đồng bộ cấu hình', description: 'Thay đổi giới hạn tạo slide của các gói cước' }
  ];
}
