import React, { useEffect, useState } from 'react';
import { documentApi } from '../api/document';
import type {SourceDocument} from '../types';
import Layout from '../components/Layout';
import { 
  FileText, 
  Trash2, 
  ExternalLink,
  Search,
  HardDrive
} from 'lucide-react';
import toast from 'react-hot-toast';

const DocumentListPage: React.FC = () => {
  const [docs, setDocs] = useState<SourceDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  const fetchDocs = async () => {
    try {
      const res = await documentApi.getAll({ search, page: 0, size: 50 });
      setDocs(res.data.data.items);
    } catch (error) {
      toast.error('Lỗi tải danh sách tài liệu');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDocs();
  }, [search]);

  const handleDelete = async (id: string) => {
    if (!confirm('Bạn có chắc muốn xóa tài liệu này?')) return;
    try {
      await documentApi.delete([id]);
      toast.success('Đã xóa tài liệu');
      fetchDocs();
    } catch (error) {
      toast.error('Lỗi khi xóa');
    }
  };

  const handleView = async (id: string) => {
    try {
      const res = await documentApi.getViewUrl(id);
      window.open(res.data.data as string, '_blank');
    } catch (error) {
      toast.error('Không thể lấy link xem file');
    }
  };

  return (
    <Layout>
      <div className="dashboard-header">
        <div>
          <h1>Tài liệu nguồn</h1>
          <p>Quản lý các file đã tải lên hệ thống</p>
        </div>
      </div>

      <div className="dashboard-actions">
        <div className="search-bar glass">
          <Search size={20} color="var(--text-muted)" />
          <input 
            type="text" 
            placeholder="Tìm kiếm tài liệu..." 
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      <div className="doc-list glass" style={{padding: '20px', borderRadius: '24px'}}>
        {loading ? <p>Đang tải...</p> : docs.length > 0 ? (
          <table style={{width: '100%', borderCollapse: 'collapse'}}>
            <thead>
              <tr style={{textAlign: 'left', borderBottom: '1px solid var(--border)', color: 'var(--text-muted)', fontSize: '14px'}}>
                <th style={{padding: '12px'}}>Tên file</th>
                <th style={{padding: '12px'}}>Dung lượng</th>
                <th style={{padding: '12px'}}>Ngày tải</th>
                <th style={{padding: '12px', textAlign: 'right'}}>Hành động</th>
              </tr>
            </thead>
            <tbody>
              {docs.map(doc => (
                <tr key={doc.id} style={{borderBottom: '1px solid rgba(255,255,255,0.05)'}}>
                  <td style={{padding: '16px', display: 'flex', alignItems: 'center', gap: '12px'}}>
                    <FileText size={20} color="var(--primary)" />
                    <span>{doc.fileName}</span>
                  </td>
                  <td style={{padding: '16px'}}>{(doc.fileSize / 1024 / 1024).toFixed(2)} MB</td>
                  <td style={{padding: '16px'}}>{new Date(doc.createdAt).toLocaleDateString()}</td>
                  <td style={{padding: '16px', textAlign: 'right'}}>
                    <button className="icon-btn" onClick={() => handleView(doc.id)} title="Xem file"><ExternalLink size={18} /></button>
                    <button className="icon-btn" onClick={() => handleDelete(doc.id)} style={{color: 'var(--error)'}}><Trash2 size={18} /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div style={{textAlign: 'center', padding: '40px', color: 'var(--text-muted)'}}>
            <HardDrive size={48} style={{marginBottom: '16px'}} />
            <p>Chưa có tài liệu nào được tải lên</p>
          </div>
        )}
      </div>
    </Layout>
  );
};

export default DocumentListPage;
