import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useDocumentStore, useUIStore } from '../../store';
import { documentService } from '../../services/documentService';
import { 
  FileText, Trash2, Eye, Plus, Sparkles, 
  Search, Clock, HardDrive, Loader2, ArrowRight
} from 'lucide-react';
import './DocumentsPage.css';

export default function DocumentsPage() {
  const { documents, setDocuments, addDocument, deleteDocument } = useDocumentStore();
  const { addToast } = useUIStore();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [uploading, setUploading] = useState(false);
  const [deletingId, setDeletingId] = useState(null);

  // Fetch documents on mount
  useEffect(() => {
    fetchDocs();
  }, []);

  const fetchDocs = async () => {
    try {
      setLoading(true);
      const data = await documentService.getAll(0, 100, '');
      if (data && data.items) {
        setDocuments(data.items);
      } else if (Array.isArray(data)) {
        setDocuments(data);
      }
    } catch (err) {
      console.error(err);
      addToast(err.message || 'Không thể tải danh sách tài liệu', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const allowedExtensions = ['.pdf', '.docx'];
    const fileExtension = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();

    if (!allowedExtensions.includes(fileExtension)) {
      addToast('Chỉ hỗ trợ định dạng tài liệu PDF hoặc DOCX', 'error');
      return;
    }

    setUploading(true);
    addToast('Đang tải tệp tin lên...', 'info');

    try {
      const data = await documentService.upload(file);
      if (data) {
        addDocument(data);
        addToast('🎉 Tải tài liệu lên thành công!', 'success');
      }
    } catch (err) {
      addToast(err.message || 'Lỗi khi tải tài liệu lên', 'error');
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (id, e) => {
    e.stopPropagation();
    if (!window.confirm('Bạn có chắc chắn muốn xóa tài liệu này? Điều này có thể ảnh hưởng đến slide được tạo từ nó.')) return;

    setDeletingId(id);
    try {
      await documentService.deleteMultiple([id]);
      deleteDocument(id);
      addToast('Đã xóa tài liệu thành công', 'success');
    } catch (err) {
      addToast(err.message || 'Xóa tài liệu thất bại', 'error');
    } finally {
      setDeletingId(null);
    }
  };

  const handleView = async (id, e) => {
    e.stopPropagation();
    addToast('Đang lấy link xem trước từ S3...', 'info');
    try {
      const url = await documentService.getViewUrl(id);
      if (url) {
        window.open(url, '_blank');
      } else {
        addToast('Không thể tạo link xem trước', 'error');
      }
    } catch (err) {
      addToast(err.message || 'Không thể xem tài liệu lúc này', 'error');
    }
  };

  const handleCreateSlide = (doc, e) => {
    e.stopPropagation();
    // Redirect to generate page and pass document metadata in router state
    navigate('/generate', { 
      state: { 
        preSelectedFile: {
          fileUrl: doc.s3Url || doc.url,
          fileName: doc.fileName,
          fileSize: doc.fileSize,
          id: doc.id
        }
      } 
    });
  };

  const formatDate = (d) => {
    if (!d) return '';
    const date = new Date(d);
    return date.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric' });
  };

  const formatSize = (bytes) => {
    if (!bytes) return '0 KB';
    const mb = bytes / (1024 * 1024);
    if (mb >= 1) return `${mb.toFixed(2)} MB`;
    return `${(bytes / 1024).toFixed(0)} KB`;
  };

  const filtered = documents.filter(doc => 
    doc.fileName?.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="docs-page page-enter">
      <div className="docs-bg" />
      <div className="container">
        
        {/* Header */}
        <div className="docs-header">
          <div>
            <h1 className="docs-title">
              📚 Thư viện <span className="gradient-text">Tài liệu</span>
            </h1>
            <p className="docs-desc">Quản lý các tài liệu PDF/DOCX bạn đã tải lên để sinh slide</p>
          </div>

          <div className="upload-btn-wrap">
            <input 
              type="file" 
              id="library-upload" 
              accept=".pdf,.docx" 
              onChange={handleUpload}
              disabled={uploading}
              style={{ display: 'none' }}
            />
            <label htmlFor="library-upload" className={`btn btn-primary ${uploading ? 'disabled' : ''}`}>
              {uploading ? <Loader2 size={16} className="spin" /> : <Plus size={16} />}
              Tải tài liệu lên
            </label>
          </div>
        </div>

        {/* Stats card */}
        <div className="docs-stats">
          <div className="docs-stat-card">
            <div className="dsc-icon"><HardDrive size={18} /></div>
            <div>
              <div className="dsc-value">{loading ? '-' : documents.length}</div>
              <div className="dsc-label">Tài liệu đã tải lên</div>
            </div>
          </div>
        </div>

        {/* Search bar */}
        <div className="docs-toolbar">
          <div className="docs-search">
            <Search size={15} className="search-icon" />
            <input 
              className="input search-input" 
              placeholder="Tìm kiếm tài liệu theo tên..." 
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        </div>

        {/* Documents Grid / Table */}
        {loading ? (
          <div className="docs-empty">
            <div className="spinner-large" />
            <h3>Đang tải tài liệu...</h3>
          </div>
        ) : filtered.length === 0 ? (
          <div className="docs-empty">
            <div className="empty-icon">📁</div>
            <h3>Không tìm thấy tài liệu nào</h3>
            <p style={{ color: 'rgba(255,255,255,0.4)', fontSize: '0.9rem', marginTop: 8 }}>
              {search ? 'Thử tìm kiếm với từ khóa khác' : 'Tải lên tài liệu PDF hoặc DOCX đầu tiên để bắt đầu tạo slide'}
            </p>
          </div>
        ) : (
          <div className="docs-list-card">
            <div className="docs-table-header">
              <div className="col-name">Tên tài liệu</div>
              <div className="col-size">Dung lượng</div>
              <div className="col-date">Ngày tải</div>
              <div className="col-actions">Thao tác</div>
            </div>
            
            <div className="docs-table-body">
              {filtered.map((doc) => (
                <div key={doc.id} className="docs-row" onClick={(e) => handleView(doc.id, e)}>
                  <div className="col-name flex items-center gap-3">
                    <FileText size={18} className="doc-icon-color" />
                    <span className="doc-name-text" title={doc.fileName}>{doc.fileName}</span>
                  </div>
                  <div className="col-size">{formatSize(doc.fileSize)}</div>
                  <div className="col-date">
                    <Clock size={12} style={{ marginRight: 6, opacity: 0.5 }} />
                    {formatDate(doc.createdAt)}
                  </div>
                  <div className="col-actions flex gap-2">
                    <button 
                      className="btn btn-ghost btn-xs" 
                      onClick={(e) => handleCreateSlide(doc, e)}
                      title="Tạo Slide từ file này"
                    >
                      <Sparkles size={13} style={{ color: '#a89fff' }} />
                      <span className="hide-mobile"> Tạo slide</span>
                    </button>
                    <button 
                      className="btn btn-ghost btn-xs" 
                      onClick={(e) => handleView(doc.id, e)}
                      title="Xem trước"
                    >
                      <Eye size={13} />
                    </button>
                    <button 
                      className="btn btn-ghost btn-xs danger-hover" 
                      onClick={(e) => handleDelete(doc.id, e)}
                      disabled={deletingId === doc.id}
                      title="Xóa"
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
