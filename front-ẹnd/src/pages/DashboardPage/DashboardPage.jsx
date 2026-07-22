import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore, useProjectStore, useUIStore } from '../../store';
import { projectService } from '../../services/documentService';
import {
  Plus, Trash2, Clock,
  Download, Sparkles, Search, FileText, Eye
} from 'lucide-react';
import './DashboardPage.css';

const PLAN_INFO = {
  free:  { label: 'Free',  color: '#6c63ff', desc: '5 slides/tháng',  price: 'Miễn phí' },
  pro:   { label: 'Pro',   color: '#f72585', desc: '20 slides/ngày',  price: '$20/tháng' },
  ultra: { label: 'Ultra', color: '#fbbf24', desc: 'Không giới hạn',  price: '$49/tháng' },
};

const getStatusBadge = (status) => {
  const key = typeof status === 'string' ? status.toUpperCase() : status;
  const mapping = {
    0:            { label: '⏳ Đang tạo...',   color: '#3b82f6', bg: 'rgba(59,130,246,0.15)' },
    'CREATE':     { label: '⏳ Đang tạo...',   color: '#3b82f6', bg: 'rgba(59,130,246,0.15)' },
    'PROCESSING': { label: '⏳ Đang tạo...',   color: '#3b82f6', bg: 'rgba(59,130,246,0.15)' },
    1:            { label: '✅ Hoàn thành',   color: '#10b981', bg: 'rgba(16,185,129,0.15)' },
    'DONE':       { label: '✅ Hoàn thành',   color: '#10b981', bg: 'rgba(16,185,129,0.15)' },
    'COMPLETED':  { label: '✅ Hoàn thành',   color: '#10b981', bg: 'rgba(16,185,129,0.15)' },
    2:            { label: '❌ Thất bại',     color: '#ef4444', bg: 'rgba(239,68,68,0.15)' },
    'FAILED':     { label: '❌ Thất bại',     color: '#ef4444', bg: 'rgba(239,68,68,0.15)' },
  };
  return mapping[key] || { label: `⏳ Processing (${status})`, color: '#3b82f6', bg: 'rgba(59,130,246,0.15)' };
};

export default function DashboardPage() {
  const { user } = useAuthStore();
  const { projects, setProjects, deleteProject } = useProjectStore();
  const { addToast } = useUIStore();
  const navigate = useNavigate();

  const [search, setSearch] = useState('');
  const [activeTab, setActiveTab] = useState('all');
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState(null);

  // Fetch projects on mount
  useEffect(() => {
    loadProjects();
  }, []);

  const loadProjects = async () => {
    try {
      setLoading(true);
      const data = await projectService.getAll(0, 100, '');
      console.log('Projects loaded:', data);
      if (data.items) {
        setProjects(data.items);
      }
    } catch (err) {
      console.error('Load projects error:', err);
      addToast(err.message || 'Không thể tải projects', 'error');
    } finally {
      setLoading(false);
    }
  };

  const filtered = projects.filter((p) =>
    p.name?.toLowerCase().includes(search.toLowerCase())
  );

  const planInfo = PLAN_INFO[user?.plan || 'free'];

  const handleDelete = async (id, e) => {
    e.stopPropagation();
    if (!window.confirm('Bạn có chắc muốn xóa presentation này?')) return;
    try {
      setDeleting(id);
      await projectService.deleteMultiple([id]);
      deleteProject(id);
      addToast('Đã xóa thành công', 'success');
    } catch (err) {
      addToast(err.message || 'Xóa thất bại', 'error');
    } finally {
      setDeleting(null);
    }
  };

  const handleOpen = (pres) => {
    navigate(`/editor/${pres.id}`);
  };

  const formatDate = (d) => {
    if (!d) return '';
    const date = new Date(d);
    return date.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric' });
  };

  return (
    <div className="dashboard page-enter">
      <div className="container">

        {/* ── Header ── */}
        <div className="dash-header">
          <div>
            <h1 className="dash-title">
              Xin chào, <span className="gradient-text">{user?.name}</span> 👋
            </h1>
            <p style={{ color: 'rgba(255,255,255,0.5)', marginTop: 6 }}>
              Quản lý tất cả bài thuyết trình của bạn tại đây
            </p>
          </div>
          <button className="btn btn-primary btn-lg" onClick={() => navigate('/generate')}>
            <Plus size={18} /> Tạo slide mới
          </button>
        </div>

        {/* ── Stats cards ── */}
        <div className="dash-stats">
          <div className="dash-stat-card">
            <div className="dsc-icon" style={{ background: 'rgba(108,99,255,0.15)', color: '#a89fff' }}>
              📊
            </div>
            <div>
              <div className="dsc-value">{loading ? '-' : projects.length}</div>
              <div className="dsc-label">Tổng presentations</div>
            </div>
          </div>
          <div className="dash-stat-card">
            <div className="dsc-icon" style={{ background: 'rgba(39,174,96,0.15)', color: '#27ae60' }}>
              <FileText size={20} />
            </div>
            <div>
              <div className="dsc-value">{loading ? '-' : projects.length}</div>
              <div className="dsc-label">Projects Created</div>
            </div>
          </div>
          <div className="dash-stat-card">
            <div className="dsc-icon" style={{ background: planInfo.color + '22', color: planInfo.color }}>
              <Sparkles size={20} />
            </div>
            <div>
              <div className="dsc-value" style={{ color: planInfo.color }}>{planInfo.label}</div>
              <div className="dsc-label">Gói hiện tại – {planInfo.price}</div>
            </div>
          </div>
          <div className="dash-stat-card upgrade-card" onClick={() => navigate('/pricing')} style={{ cursor: 'pointer' }}>
            <div className="upgrade-glow" />
            <div className="dsc-icon" style={{ background: 'rgba(251,191,36,0.15)', color: '#fbbf24' }}>
              <Sparkles size={20} />
            </div>
            <div>
              <div className="dsc-value" style={{ color: '#fbbf24' }}>Nâng cấp Pro</div>
              <div className="dsc-label">20 slides/ngày + HD images</div>
            </div>
          </div>
        </div>

        {/* ── Toolbar ── */}
        <div className="dash-toolbar">
          <div className="dash-search">
            <Search size={15} className="search-icon" />
            <input
              className="input search-input"
              placeholder="Tìm kiếm presentations..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <div className="dash-tabs">
            {['all', 'recent'].map((t) => (
              <button key={t} className={`chip ${activeTab === t ? 'active' : ''}`} onClick={() => setActiveTab(t)}>
                {t === 'all' ? 'Tất cả' : 'Gần đây'}
              </button>
            ))}
          </div>
        </div>

        {/* ── Content ── */}
        {loading ? (
          <div className="dash-empty">
            <div className="spinner-large"></div>
            <h3>Đang tải projects...</h3>
          </div>
        ) : filtered.length === 0 ? (
          <div className="dash-empty">
            <div className="empty-icon">🎨</div>
            <h3>Chưa có presentation nào</h3>
            <p style={{ color: 'rgba(255,255,255,0.4)', fontSize: '0.9rem', marginTop: 8, marginBottom: 24 }}>
              Bắt đầu tạo slide AI đầu tiên của bạn ngay nào!
            </p>
            <button className="btn btn-primary btn-lg" onClick={() => navigate('/generate')}>
              <Sparkles size={18} /> Tạo slide đầu tiên
            </button>
          </div>
        ) : (
          <div className="pres-grid">
            {filtered.map((pres) => {
              return (
                <div key={pres.id} className="pres-card" onClick={() => handleOpen(pres)}>
                  <div className="pres-thumb" style={{
                    background: 'linear-gradient(135deg,#0d0d1a,#1c1c3a)'
                  }}>
                    <div className="pres-thumb-deco" style={{ background: '#6c63ff25' }} />
                    <div className="pres-thumb-badge" style={{ color: '#6c63ff', background: '#6c63ff18', borderColor: '#6c63ff44' }}>
                      ✦ AI Slide
                    </div>
                    <div className="pres-thumb-title" style={{ color: 'white' }}>
                      {pres.name}
                    </div>
                    <div className="pres-thumb-bar" style={{ background: '#6c63ff' }} />
                    <div className="pres-thumb-overlay" title="Xem slide" aria-label="Xem slide">
                      <Eye size={18} />
                    </div>
                  </div>

                  <div className="pres-info">
                    <div className="pres-info-top">
                      <h4 className="pres-title-text">{pres.name}</h4>
                      <button className="pres-delete-btn" onClick={(e) => handleDelete(pres.id, e)} title="Xóa" disabled={deleting === pres.id}>
                        <Trash2 size={14} />
                      </button>
                    </div>
                    <div className="pres-meta">
                      {(() => {
                        const badge = getStatusBadge(pres.status);
                        return (
                          <span className="pres-template-tag" style={{ color: badge.color, background: badge.bg }}>
                            {badge.label}
                          </span>
                        );
                      })()}
                    </div>
                    <div className="pres-date">
                      <Clock size={12} /> {formatDate(pres.createdAt)}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
