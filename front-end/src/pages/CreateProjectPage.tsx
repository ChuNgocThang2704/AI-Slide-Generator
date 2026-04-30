import React, { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { projectApi } from '../api/project';
import { documentApi } from '../api/document';
import Layout from '../components/Layout';
import { 
  Sparkles, 
  FileText, 
  X, 
  Paperclip,
  Send,
  Loader2
} from 'lucide-react';
import './CreateProject.css';
import toast from 'react-hot-toast';
import { useAuth } from '../context/AuthContext';

const CreateProjectPage: React.FC = () => {
  const [prompt, setPrompt] = useState('');
  const [attachedFile, setAttachedFile] = useState<{ url: string, fileName: string, fileSize: number, loading: boolean } | null>(null);
  const [creating, setCreating] = useState(false);
  
  const { user } = useAuth();
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setAttachedFile({ url: '', fileName: file.name, fileSize: 0, loading: true });

      try {
        const res = await documentApi.upload(file);
        const data = res.data.data;
        setAttachedFile({ 
          url: data.url, 
          fileName: data.fileName, 
          fileSize: data.fileSize, 
          loading: false 
        });
        toast.success(`Đã tải lên: ${file.name}`);
      } catch (error) {
        toast.error(`Lỗi tải file: ${file.name}`);
        setAttachedFile(null);
      }
    }
    if (e.target.value) e.target.value = '';
  };

  const removeFile = () => {
    setAttachedFile(null);
  };

  const handleCreate = async () => {
    if (!prompt.trim() && !attachedFile) {
      toast.error('Vui lòng nhập ý tưởng hoặc tải lên tài liệu');
      return;
    }
    
    setCreating(true);
    try {
      const res = await projectApi.create({
        ownerId: user?.id,
        prompt: prompt,
        fileUrl: attachedFile?.url,
        fileName: attachedFile?.fileName,
        fileSize: attachedFile?.fileSize
      });
      toast.success('Khởi tạo dự án thành công!');
      navigate(`/project/${res.data.data.id}`);
    } catch (error) {
      toast.error('Lỗi khởi tạo dự án');
    } finally {
      setCreating(false);
    }
  };

  return (
    <Layout>
      <div className="create-container">
        <div className="create-header">
          <h1>Tạo bài thuyết trình mới</h1>
          <p>Sử dụng AI để biến ý tưởng hoặc tài liệu của bạn thành slide chuyên nghiệp</p>
        </div>

        <div className="unified-input-container glass">
          <div className="input-wrapper">
            <textarea 
              className="prompt-textarea"
              placeholder="Mô tả ý tưởng của bạn hoặc dán nội dung tại đây... (Ví dụ: Tạo slide về chiến lược marketing cho quán cafe)" 
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              disabled={creating}
            />

            {attachedFile && (
              <div className="attached-files">
                <div className={`file-chip ${attachedFile.loading ? 'loading' : ''}`}>
                  <FileText size={16} />
                  <span className="file-name">{attachedFile.fileName}</span>
                  {attachedFile.loading ? (
                    <Loader2 size={14} className="spin" />
                  ) : (
                    <button className="remove-file-btn" onClick={removeFile}>
                      <X size={14} />
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>

          <div className="input-footer">
            <div className="footer-left">
              <input 
                type="file" 
                ref={fileInputRef}
                onChange={handleFileChange}
                style={{ display: 'none' }}
                accept=".pdf,.docx,.pptx"
              />
              <button 
                className="action-icon-btn" 
                onClick={() => fileInputRef.current?.click()}
                disabled={creating}
                title="Đính kèm tài liệu"
              >
                <Paperclip size={20} />
                <span>Đính kèm file</span>
              </button>
              <span className="hint-text">Hỗ trợ PDF, DOCX, PPTX (Tối đa 20MB)</span>
            </div>

            <button 
              className="btn-create-submit" 
              onClick={handleCreate}
              disabled={creating || attachedFile?.loading}
            >
              {creating ? (
                <>
                  <Loader2 size={18} className="spin" />
                  <span>Đang xử lý...</span>
                </>
              ) : (
                <>
                  <span>Bắt đầu tạo</span>
                  <Send size={18} />
                </>
              )}
            </button>
          </div>
        </div>

        <div className="pro-tips">
          <Sparkles size={20} color="var(--primary)" />
          <span>Mẹo: Bạn có thể tải tài liệu lên và mô tả cách AI nên xử lý tài liệu đó trong phần mô tả.</span>
        </div>
      </div>
    </Layout>
  );
};

export default CreateProjectPage;
