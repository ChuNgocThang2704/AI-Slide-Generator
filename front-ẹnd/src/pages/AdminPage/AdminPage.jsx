import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore, useUIStore } from '../../store';
import { adminService } from '../../services/adminService';
import { 
  Users, Settings, ShieldAlert, Trash2, Plus, 
  Check, AlertTriangle, ShieldCheck, Loader2
} from 'lucide-react';
import './AdminPage.css';

export default function AdminPage() {
  const { user } = useAuthStore();
  const { addToast } = useUIStore();
  const navigate = useNavigate();

  const [activeTab, setActiveTab] = useState('configs');
  const [loading, setLoading] = useState(false);

  // States for tab content
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

  // Check Admin Privilege
  useEffect(() => {
    // Check if roles has ADMIN, e.g. "ADMIN" or "ROLE_ADMIN"
    const isAdmin = user?.roles?.some(r => r.name === 'ADMIN' || r.code === 'ADMIN' || r.name === 'ROLE_ADMIN') || user?.email === 'admin@aislide.com';
    if (!isAdmin) {
      addToast('Bạn không có quyền truy cập trang quản trị!', 'error');
      navigate('/dashboard');
    } else {
      loadTabData();
    }
  }, [activeTab]);

  const loadTabData = async () => {
    setLoading(true);
    try {
      if (activeTab === 'users') {
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
          console.log('Không lấy được configs từ BE, sử dụng cấu hình mặc định');
        }
      }
    } catch (err) {
      console.error(err);
      // Fallbacks
      if (activeTab === 'users') setUsersList(getMockUsers());
      if (activeTab === 'roles') {
        setRolesList(getMockRoles());
        setPermsList(getMockPermissions());
      }
    } finally {
      setLoading(false);
    }
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

  return (
    <div className="admin-page page-enter">
      <div className="admin-bg" />
      <div className="container">
        
        {/* Header */}
        <div className="admin-header">
          <h1 className="admin-title">
            🛡️ Hệ thống <span className="gradient-text">Quản trị</span>
          </h1>
          <p className="admin-desc">Quản lý giới hạn tài khoản, danh sách người dùng và phân quyền hệ thống</p>
        </div>

        <div className="admin-layout">
          {/* Left Sidebar Menu */}
          <div className="admin-sidebar">
            <button 
              className={`admin-menu-btn ${activeTab === 'configs' ? 'active' : ''}`}
              onClick={() => setActiveTab('configs')}
            >
              <Settings size={16} />
              <span>Cấu hình gói AI</span>
            </button>
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
                <span>Đang xử lý dữ liệu...</span>
              </div>
            )}

            {/* TAB: CẤU HÌNH AI */}
            {activeTab === 'configs' && (
              <div className="tab-pane">
                <div className="pane-header">
                  <h3>⚙️ Cấu hình giới hạn gói dịch vụ</h3>
                  <p>Thiết lập giới hạn số slide, số project và tone sinh slide cho từng nhóm thành viên.</p>
                </div>

                <div className="configs-list">
                  {aiConfigs.map((config, index) => (
                    <div key={config.roleCode} className="config-card">
                      <div className="cc-header">
                        <h4>{config.configName} ({config.roleCode})</h4>
                      </div>
                      
                      <div className="cc-grid">
                        <div className="form-group">
                          <label className="form-label">Dự án tối đa / ngày</label>
                          <input 
                            type="number" 
                            className="input"
                            value={config.maxProjectsPerDay}
                            onChange={(e) => handleConfigChange(index, 'maxProjectsPerDay', parseInt(e.target.value))}
                          />
                        </div>
                        <div className="form-group">
                          <label className="form-label">Số slide tối thiểu</label>
                          <input 
                            type="number" 
                            className="input"
                            value={config.minPagesPerProject}
                            onChange={(e) => handleConfigChange(index, 'minPagesPerProject', parseInt(e.target.value))}
                          />
                        </div>
                        <div className="form-group">
                          <label className="form-label">Số slide tối đa</label>
                          <input 
                            type="number" 
                            className="input"
                            value={config.maxPagesPerProject}
                            onChange={(e) => handleConfigChange(index, 'maxPagesPerProject', parseInt(e.target.value))}
                          />
                        </div>
                        <div className="form-group">
                          <label className="form-label">Ngôn ngữ mặc định</label>
                          <input 
                            type="text" 
                            className="input"
                            value={config.language}
                            onChange={(e) => handleConfigChange(index, 'language', e.target.value)}
                          />
                        </div>
                      </div>
                    </div>
                  ))}
                </div>

                <button className="btn btn-primary" onClick={handleSyncConfigs} disabled={loading} style={{ marginTop: 16 }}>
                  <Check size={16} /> Lưu & Đồng bộ cấu hình
                </button>
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

// ── MOCK DATA FOR FAILSAFE FALLBACKS ──
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
