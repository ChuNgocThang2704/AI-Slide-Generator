import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { projectApi } from '../api/project';
import type {Project} from '../types';
import Layout from '../components/Layout';
import { 
  Search, 
  Plus, 
  MoreVertical, 
  Clock, 
  CircleCheck, 
  CircleAlert,
  FileText
} from 'lucide-react';
import './Dashboard.css';
import toast from 'react-hot-toast';

import { getProjectStatus } from '../utils/statusMapper';

const DashboardPage: React.FC = () => {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  
  const navigate = useNavigate();

  const fetchProjects = async () => {
    try {
      const res = await projectApi.getAll({ search, page: 0, size: 20 });
      setProjects(res.data.data.items);
    } catch (error) {
      toast.error('Không thể tải danh sách dự án');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProjects();
  }, [search]);

  const getStatusIcon = (status: number) => {
    const { color } = getProjectStatus(status);
    switch(status) {
      case 2: return <Clock size={16} color={color} />;
      case 3: return <CircleCheck size={16} color={color} />;
      case 4: return <CircleAlert size={16} color={color} />;
      default: return <Clock size={16} color={color} />;
    }
  };

  return (
    <Layout>
      <div className="dashboard-header">
        <div>
          <h1>Dự án của tôi</h1>
          <p>Quản lý và chỉnh sửa các bài thuyết trình AI</p>
        </div>
        <button className="btn-primary" onClick={() => navigate('/create')}>
          <Plus size={20} />
          Tạo dự án mới
        </button>
      </div>

      <div className="dashboard-actions">
        <div className="search-bar glass">
          <Search size={20} color="var(--text-muted)" />
          <input 
            type="text" 
            placeholder="Tìm kiếm dự án..." 
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      <div className="project-grid">
        {loading ? (
          <div className="loading">Đang tải...</div>
        ) : projects.length > 0 ? (
          projects.map((project) => (
            <div 
              key={project.id} 
              className="project-card glass" 
              onClick={() => navigate(`/project/${project.id}`)}
            >
              <div className="project-preview">
                <FileText size={48} color="var(--primary)" />
                <div className="project-status-badge">
                  {getStatusIcon(project.status)}
                  <span style={{ color: getProjectStatus(project.status).color }}>
                    {getProjectStatus(project.status).text}
                  </span>
                </div>
              </div>
              <div className="project-info">
                <div className="project-title-row">
                  <h3 title={project.name}>{project.name}</h3>
                  <button className="icon-btn"><MoreVertical size={18} /></button>
                </div>
                <p className="project-date">
                  Cập nhật: {new Date(project.updatedAt).toLocaleDateString('vi-VN')}
                </p>
              </div>
            </div>
          ))
        ) : (
          <div className="empty-state glass">
            <Plus size={48} color="var(--text-muted)" />
            <h3>Chưa có dự án nào</h3>
            <p>Bắt đầu tạo bài thuyết trình đầu tiên của bạn</p>
            <button onClick={() => navigate('/create')}>Bắt đầu ngay</button>
          </div>
        )}
      </div>
    </Layout>
  );
};

export default DashboardPage;
