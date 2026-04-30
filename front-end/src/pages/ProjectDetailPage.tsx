import React, { useEffect, useState, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { projectApi } from '../api/project';
import type { Project, SlidePage, AITaskLog, ProjectExport } from '../types';
import Layout from '../components/Layout';
import {
  Download,
  Eye,
  Edit3,
  History,
  FileText,
  Loader2,
  RefreshCcw,
  CircleCheck,
  Plus,
  Trash2,
  Check,
  X as CancelIcon
} from 'lucide-react';
import './ProjectDetail.css';
import toast from 'react-hot-toast';
import { getTaskTypeLabel, getTaskStatus, getProjectStatus } from '../utils/statusMapper';

const ProjectDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [project, setProject] = useState<Project | null>(null);
  const [pages, setPages] = useState<SlidePage[]>([]);
  const [localPages, setLocalPages] = useState<SlidePage[]>([]);
  const [logs, setLogs] = useState<AITaskLog[]>([]);
  const [exports, setExports] = useState<ProjectExport[]>([]);
  const [activeTab, setActiveTab] = useState<'content' | 'logs' | 'exports'>('content');
  const [loading, setLoading] = useState(true);
  const [isEditingAll, setIsEditingAll] = useState(false);
  const [saving, setSaving] = useState(false);

  const timerRef = useRef<any>(null);

  const fetchData = async () => {
    if (!id) return;
    try {
      const [pRes, pgRes, lRes, eRes] = await Promise.all([
        projectApi.getById(id),
        projectApi.getPages(id),
        projectApi.getLogs(id),
        projectApi.getExports(id)
      ]);
      setProject(pRes.data.data);
      const sortedPages = pgRes.data.data.sort((a: any, b: any) => a.pageIndex - b.pageIndex);
      setPages(sortedPages);
      setLocalPages(JSON.parse(JSON.stringify(sortedPages)));
      setLogs(lRes.data.data);
      setExports(eRes.data.data);
    } catch (error) {
      toast.error('Lỗi tải thông tin dự án');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    // Only poll if NOT editing and project is processing
    timerRef.current = setInterval(() => {
      if (project?.status === 2 && !isEditingAll) {
        fetchData();
      }
    }, 5000);
    return () => clearInterval(timerRef.current);
  }, [id, project?.status, isEditingAll]);

  const handleStartEdit = () => {
    // Sync localPages with current pages before starting edit
    setLocalPages(JSON.parse(JSON.stringify(pages)));
    setIsEditingAll(true);
  };

  const handleAddPage = () => {
    const newPage: any = {
      title: 'Tiêu đề Slide mới',
      content: 'Nội dung Slide mới...',
      pageIndex: localPages.length
    };
    setLocalPages([...localPages, newPage]);
  };

  const handleDeletePage = (index: number) => {
    const newLocal = [...localPages];
    newLocal.splice(index, 1);
    setLocalPages(newLocal);
  };

  const handleUpdateLocalPage = (index: number, field: string, value: string) => {
    const newLocal = [...localPages];
    newLocal[index] = { ...newLocal[index], [field]: value };
    setLocalPages(newLocal);
  };

  const handleSyncAll = async () => {
    if (!id) return;
    setSaving(true);
    try {
      await projectApi.syncPages(id, localPages);
      toast.success('Đã cập nhật tất cả các trang');
      setIsEditingAll(false);
      fetchData();
    } catch (error) {
      toast.error('Lỗi khi cập nhật slide');
    } finally {
      setSaving(false);
    }
  };

  const handleCancelEdit = () => {
    setLocalPages(JSON.parse(JSON.stringify(pages)));
    setIsEditingAll(false);
  };

  if (loading) return <Layout><div className="loading-full"><Loader2 className="spinner" /> <span>Đang tải dự án...</span></div></Layout>;
  if (!project) return <Layout><div>Không tìm thấy dự án</div></Layout>;

  return (
    <Layout>
      <div className="detail-container">
        <header className="detail-header">
          <div className="title-section">
            <div className="status-indicator" style={{ backgroundColor: getProjectStatus(project.status).color }}></div>
            <div>
              <h1>{project.name}</h1>
              <p className="project-meta">{getProjectStatus(project.status).text}</p>
            </div>
          </div>
          <div className="action-section">
            {activeTab === 'content' && (
              isEditingAll ? (
                <>
                  <button className="btn-success" onClick={handleSyncAll} disabled={saving}>
                    {saving ? <Loader2 className="spin" size={18} /> : <Check size={18} />} Lưu thay đổi
                  </button>
                  <button className="btn-secondary" onClick={handleCancelEdit} disabled={saving}>
                    <CancelIcon size={18} /> Hủy
                  </button>
                </>
              ) : (
                <button className="btn-primary" onClick={handleStartEdit}>
                  <Edit3 size={18} /> Chỉnh sửa nội dung
                </button>
              )
            )}
            <button className="btn-secondary" onClick={fetchData}>
              <RefreshCcw size={18} /> Làm mới
            </button>
            <button className="btn-primary" disabled={project.status !== 3}>
              <Download size={18} /> Xuất File
            </button>
          </div>
        </header>

        <div className="detail-tabs">
          <button className={activeTab === 'content' ? 'active' : ''} onClick={() => { setActiveTab('content'); setIsEditingAll(false); }}>
            <Eye size={18} /> Nội dung Slide
          </button>
          <button className={activeTab === 'logs' ? 'active' : ''} onClick={() => { setActiveTab('logs'); setIsEditingAll(false); }}>
            <History size={18} /> Tiến trình AI
          </button>
          <button className={activeTab === 'exports' ? 'active' : ''} onClick={() => { setActiveTab('exports'); setIsEditingAll(false); }}>
            <Download size={18} /> Bản đã xuất
          </button>
        </div>

        <div className="tab-content">
          {activeTab === 'content' && (
            <div className="slide-list">
              {(isEditingAll ? localPages : pages).map((page, idx) => (
                <div key={page.id || `new-${idx}`} className={`slide-card glass ${isEditingAll ? 'editing' : ''}`}>
                  <div className="slide-index">{idx + 1}</div>
                  <div className="slide-body">
                    {isEditingAll ? (
                      <div className="edit-form">
                        <input 
                          type="text" 
                          value={page.title} 
                          onChange={e => handleUpdateLocalPage(idx, 'title', e.target.value)}
                          placeholder="Tiêu đề Slide"
                        />
                        <textarea 
                          value={page.content} 
                          onChange={e => handleUpdateLocalPage(idx, 'content', e.target.value)}
                          placeholder="Nội dung Slide"
                          rows={4}
                        />
                      </div>
                    ) : (
                      <>
                        <h3>{page.title}</h3>
                        <p>{page.content}</p>
                      </>
                    )}
                  </div>
                  {isEditingAll && (
                    <div className="slide-actions">
                      <button className="delete-btn" onClick={() => handleDeletePage(idx)}>
                        <Trash2 size={18} />
                      </button>
                    </div>
                  )}
                </div>
              ))}
              
              {isEditingAll && (
                <button className="add-slide-btn glass" onClick={handleAddPage}>
                  <Plus size={24} /> Thêm Slide mới
                </button>
              )}

              {pages.length === 0 && !isEditingAll && (
                <div className="empty-content">
                  {project.status === 2 ? (
                    <div className="rendering">
                      <Loader2 className="spinner" size={48} />
                      <h3>AI đang thiết kế các trang slide...</h3>
                      <p>Quá trình này có thể mất 1-2 phút. Bạn có thể theo dõi tiến trình ở tab "Tiến trình AI".</p>
                    </div>
                  ) : (
                    <p>Chưa có nội dung slide nào được tạo.</p>
                  )}
                </div>
              )}
            </div>
          )}

          {activeTab === 'logs' && (
            <div className="log-list glass">
              {logs.length > 0 ? [...logs].sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()).map((log) => (
                <div key={log.id} className="log-item">
                  <span className="log-time">{new Date(log.createdAt).toLocaleTimeString('vi-VN')}</span>
                  <span className="log-status-icon">
                    {log.status === 2 ? (
                      <CircleCheck size={16} color="#22c55e" />
                    ) : log.status === 1 ? (
                      <Loader2 size={16} className="spin" color="#f59e0b" />
                    ) : (
                      <Loader2 size={16} color="#94a3b8" />
                    )}
                  </span>
                  <div className="log-content">
                    <span className="log-title">{getTaskTypeLabel(log.taskType)}</span>
                    {log.errorMessage && <span className="log-error">{log.errorMessage}</span>}
                  </div>
                  <span className="log-status-text" style={{ color: getTaskStatus(log.status).color }}>
                    {getTaskStatus(log.status).text}
                  </span>
                </div>
              )) : <p className="empty-msg">Chưa có nhật ký hoạt động.</p>}
            </div>
          )}

          {activeTab === 'exports' && (
            <div className="export-list">
              {exports.length > 0 ? exports.map((exp) => (
                <div key={exp.id} className="export-card glass">
                  <div className="export-main-info">
                    <div className="export-icon">
                      <FileText size={32} color={exp.exportType === 0 ? "#f59e0b" : "#ef4444"} />
                      <span className="export-type-tag">{exp.exportType === 0 ? 'PPTX' : 'PDF'}</span>
                    </div>
                    <div className="export-info">
                      <h4>Bản xuất bài thuyết trình #{exp.id.substring(0, 8)}</h4>
                      <p>Định dạng: {exp.exportType === 0 ? 'PowerPoint' : 'PDF'} • {new Date(exp.createdAt).toLocaleString('vi-VN')}</p>
                    </div>
                  </div>
                  <a href={exp.s3Url} target="_blank" rel="noreferrer" className="btn-download" download>
                    Tải về <Download size={16} />
                  </a>
                </div>
              )) : (
                <div className="empty-exports">
                  <Download size={48} color="rgba(255,255,255,0.1)" />
                  <p>Chưa có bản xuất nào được tạo.</p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
};

export default ProjectDetailPage;
