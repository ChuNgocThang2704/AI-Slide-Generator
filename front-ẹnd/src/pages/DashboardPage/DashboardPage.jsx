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
  const { projects, setProjects, updateProject, deleteProject } = useProjectStore();
  const { addToast } = useUIStore();
  const navigate = useNavigate();

  const [search, setSearch] = useState('');
  const [activeTab, setActiveTab] = useState('all');
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState(null);
  const [progressById, setProgressById] = useState({});

  // Fetch projects on mount
  useEffect(() => {
    loadProjects();
  }, []);

  const loadProjects = async ({ silent = false } = {}) => {
    try {
      if (!silent) setLoading(true);
      const data = await projectService.getAll(0, 100, '');
      console.log('Projects loaded:', data);
      if (data.items) {
        setProjects(data.items);
      }
    } catch (err) {
      console.error('Load projects error:', err);
      if (silent) return;
      addToast(err.message || 'Không thể tải projects', 'error');
    } finally {
      if (!silent) setLoading(false);
    }
  };

  const hasProcessingProjects = projects.some((project) => {
    const status = typeof project.status === 'string' ? project.status.toUpperCase() : project.status;
    return status === 0 || status === 'CREATE' || status === 'PROCESSING';
  });

  useEffect(() => {
    if (!hasProcessingProjects) return undefined;

    const refreshProcessing = async () => {
      const processing = projects.filter((project) => {
        const status = typeof project.status === 'string' ? project.status.toUpperCase() : project.status;
        return status === 0 || status === 'CREATE' || status === 'PROCESSING';
      });
      const results = await Promise.allSettled(processing.map(async (project) => ({
        id: project.id,
        progress: await projectService.getProgress(project.id),
      })));
      results.forEach((result) => {
        if (result.status !== 'fulfilled') return;
        const task = result.value.progress;
        const aiStatus = String(task?.aiStatus || '').toLowerCase();
        if (Number(task?.progress) >= 100 || task?.projectStatus === 1 || aiStatus === 'completed') {
          updateProject(result.value.id, { status: 1 });
        }
      });
      setProgressById((current) => {
        const next = { ...current };
        results.forEach((result) => {
          if (result.status === 'fulfilled') {
            next[result.value.id] = result.value.progress;
          }
        });
        return next;
      });
      loadProjects({ silent: true });
    };
    refreshProcessing();
    const intervalId = window.setInterval(refreshProcessing, 3000);

    return () => window.clearInterval(intervalId);
  }, [hasProcessingProjects, projects.length]);

  const filtered = projects
    .filter((p) => p.name?.toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => activeTab === 'recent'
      ? new Date(b.updatedAt || b.createdAt || 0) - new Date(a.updatedAt || a.createdAt || 0)
      : 0)
    .slice(0, activeTab === 'recent' ? 8 : undefined);

  const planInfo = PLAN_INFO[user?.plan || 'free'];
  const upgradeInfo = user?.plan === 'ultra'
    ? { title: 'Đã mở khóa Ultra', description: 'Toàn bộ tính năng cao cấp', clickable: false }
    : user?.plan === 'pro'
      ? { title: 'Nâng cấp Ultra', description: 'Giới hạn cao nhất + ảnh chất lượng cao', clickable: true }
      : { title: 'Nâng cấp Pro', description: '20 slides/ngày + HD images', clickable: true };

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
          <div
            className={`dash-stat-card upgrade-card ${upgradeInfo.clickable ? '' : 'is-current-plan'}`}
            onClick={upgradeInfo.clickable ? () => navigate('/pricing') : undefined}
            style={{ cursor: upgradeInfo.clickable ? 'pointer' : 'default' }}
          >
            <div className="upgrade-glow" />
            <div className="dsc-icon" style={{ background: 'rgba(251,191,36,0.15)', color: '#fbbf24' }}>
              <Sparkles size={20} />
            </div>
            <div>
              <div className="dsc-value" style={{ color: '#fbbf24' }}>{upgradeInfo.title}</div>
              <div className="dsc-label">{upgradeInfo.description}</div>
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
              const taskProgress = progressById[pres.id];
              const progressPercent = Math.max(0, Math.min(100, Number(taskProgress?.progress) || 0));
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
                        const effectiveStatus = progressPercent >= 100
                          || taskProgress?.projectStatus === 1
                          || String(taskProgress?.aiStatus || '').toLowerCase() === 'completed'
                          ? 1
                          : pres.status;
                        const badge = getStatusBadge(effectiveStatus);
                        return (
                          <span className="pres-template-tag" style={{ color: badge.color, background: badge.bg }}>
                            {badge.label}
                          </span>
                        );
                      })()}
                    </div>
                    {progressPercent < 100 && (pres.status === 0 || ['CREATE', 'PROCESSING'].includes(String(pres.status).toUpperCase())) && (
                      <div className="pres-progress" title={taskProgress?.aiStatus || 'Đang tạo slide'}>
                        <div className="pres-progress-track"><span style={{ width: `${progressPercent}%` }}/></div>
                        <span>{progressPercent}%</span>
                      </div>
                    )}
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
