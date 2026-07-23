import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useProjectStore, useUIStore } from '../../store';
import { projectService, documentService } from '../../services/documentService';
import { Sparkles, ChevronRight, Loader2, UploadCloud, FileText, X } from 'lucide-react';
import './GeneratePage.css';

const PROMPT_SUGGESTIONS = [
  {
    label: 'Giới thiệu sản phẩm',
    prompt: 'Tạo bài thuyết trình giới thiệu một sản phẩm công nghệ mới, gồm vấn đề cần giải quyết, khách hàng mục tiêu, tính năng nổi bật, lợi thế cạnh tranh và kế hoạch phát triển.',
  },
  {
    label: 'Báo cáo nghiên cứu',
    prompt: 'Tạo bài thuyết trình báo cáo kết quả nghiên cứu, gồm bối cảnh, mục tiêu, phương pháp, dữ liệu chính, phân tích kết quả, hạn chế và kết luận.',
  },
  {
    label: 'So sánh giải pháp',
    prompt: 'Tạo bài thuyết trình phân tích và so sánh các giải pháp theo chi phí, hiệu quả, khả năng triển khai, rủi ro và khả năng mở rộng; sử dụng bảng hoặc biểu đồ khi phù hợp.',
  },
  {
    label: 'Đề xuất dự án',
    prompt: 'Tạo bài thuyết trình đề xuất một dự án, gồm thực trạng, mục tiêu, giải pháp, kế hoạch triển khai, nguồn lực, ngân sách dự kiến, rủi ro và kết quả kỳ vọng.',
  },
];



export default function GeneratePage() {
  const { addProject, updateProject } = useProjectStore();
  const { addToast } = useUIStore();
  const navigate = useNavigate();
  const location = useLocation();

  const [loading, setLoading] = useState(false);
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadedFileData, setUploadedFileData] = useState(null);
  const [form, setForm] = useState({
    prompt: '',
    slideCount: 8,
    templateId: 'clean-white',
  });

  // Progress states
  const [showProgress, setShowProgress] = useState(false);
  const [progressVal, setProgressVal] = useState(0);
  const [progressStatus, setProgressStatus] = useState('Đang gửi dữ liệu đến AI...');
  const [currentProjectId, setCurrentProjectId] = useState(null);
  const [pollingIntervalId, setPollingIntervalId] = useState(null);

  // Dọn dẹp bộ đếm khi unmount
  React.useEffect(() => {
    return () => {
      if (pollingIntervalId) {
        clearInterval(pollingIntervalId);
      }
    };
  }, [pollingIntervalId]);

  React.useEffect(() => {
    if (location.state?.preSelectedFile) {
      const { fileName, fileSize, fileUrl } = location.state.preSelectedFile;
      setFile({ name: fileName, size: fileSize });
      setUploadedFileData({ fileName, fileSize, fileUrl });
      addToast(`Đã chọn tài liệu: ${fileName}`, 'success');
      // Xóa state trong history để tránh lặp lại khi refresh trang
      window.history.replaceState({}, document.title);
    }
  }, [location.state]);

  const handleFileChange = async (e) => {
    const selectedFile = e.target.files[0];
    if (!selectedFile) return;

    const allowedTypes = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'];
    const allowedExtensions = ['.pdf', '.docx'];
    const fileExtension = selectedFile.name.substring(selectedFile.name.lastIndexOf('.')).toLowerCase();

    if (!allowedTypes.includes(selectedFile.type) && !allowedExtensions.includes(fileExtension)) {
      addToast('Chỉ hỗ trợ tệp tin định dạng PDF hoặc DOCX', 'error');
      return;
    }

    if (selectedFile.size > 50 * 1024 * 1024) {
      addToast('Dung lượng tệp tối đa là 50MB', 'error');
      return;
    }

    setFile(selectedFile);
    setUploading(true);
    addToast('Đang tải tệp tin lên máy chủ...', 'info');

    try {
      const data = await documentService.upload(selectedFile);
      if (data) {
        setUploadedFileData({
          fileUrl: data.url || data.s3Url || data.fileUrl,
          fileName: data.fileName || selectedFile.name,
          fileSize: data.fileSize || selectedFile.size
        });
        addToast('🎉 Tải tệp tin lên thành công!', 'success');
      }
    } catch (err) {
      addToast(err.message || 'Không thể tải tệp tin lên', 'error');
      setFile(null);
      setUploadedFileData(null);
    } finally {
      setUploading(false);
    }
  };

  const handleRemoveFile = () => {
    setFile(null);
    setUploadedFileData(null);
  };

  // Lấy câu thông báo tương ứng với % tiến độ
  const getProgressMessage = (pct, aiStatus) => {
    if (aiStatus === 'failed' || aiStatus === 'error') {
      return 'Có lỗi xảy ra trong quá trình xử lý.';
    }
    if (aiStatus === 'cancelled') {
      return 'Tác vụ đã bị hủy.';
    }
    if (pct >= 100 || aiStatus === 'completed') {
      return 'Hoàn thành! Đang chuẩn bị mở trình soạn thảo...';
    }
    return 'AI đang tạo slide, Vui lòng chờ...';
  };

  // Hủy tác vụ
  const handleCancel = async () => {
    if (pollingIntervalId) {
      clearInterval(pollingIntervalId);
      setPollingIntervalId(null);
    }
    setShowProgress(false);
    setLoading(false);
    if (currentProjectId) {
      try {
        await projectService.cancel(currentProjectId);
        addToast('Đã gửi yêu cầu hủy tác vụ tạo slide', 'info');
      } catch (e) {
        console.error('Failed to cancel task:', e);
      }
    }
  };

  // Create project
  const handleCreate = async () => {
    if (!form.prompt.trim() && !uploadedFileData) {
      addToast('Vui lòng nhập chủ đề hoặc tải lên tệp tin tài liệu', 'error');
      return;
    }

    let intervalId = null;

    try {
      setLoading(true);
      const promptText = form.prompt.trim() || `Tạo slide từ tệp tin ${uploadedFileData.fileName}`;
      
      const project = await projectService.create(
        promptText,
        form.templateId,
        promptText,
        uploadedFileData?.fileUrl || null,
        uploadedFileData?.fileName || null,
        uploadedFileData?.fileSize || null
      );
      
      addProject(project);
      setCurrentProjectId(project.id);
      setProgressVal(0);
      setProgressStatus('Đang khởi tạo tác vụ...');
      setShowProgress(true);

      // Bắt đầu vòng lặp check status mỗi 1.5 giây
      intervalId = setInterval(async () => {
        try {
          const res = await projectService.getProgress(project.id);
          const pct = res.progress || 0;
          const status = res.aiStatus || 'processing';
          
          setProgressVal(pct);
          setProgressStatus(getProgressMessage(pct, status));

          if (res.projectStatus === 1) {
            clearInterval(intervalId);
            setPollingIntervalId(null);
            updateProject(project.id, { status: 1 });
            setShowProgress(false);
            setLoading(false);
            addToast('🎉 Tạo slide thành công!', 'success');
            navigate(`/editor/${project.id}`);
          } else if (status === 'failed' || status === 'error' || res.projectStatus === 2) {
            clearInterval(intervalId);
            setPollingIntervalId(null);
            setShowProgress(false);
            setLoading(false);
            addToast(res.errorMessage || 'AI sinh slide thất bại, vui lòng thử lại', 'error');
          } else if (status === 'cancelled') {
            clearInterval(intervalId);
            setPollingIntervalId(null);
            setShowProgress(false);
            setLoading(false);
            addToast('Tác vụ tạo slide đã bị hủy', 'info');
          }
        } catch (pollErr) {
          console.error('Lỗi khi kiểm tra tiến độ:', pollErr);
          // Không ngắt vòng lặp, để nó thử lại lần tiếp theo
        }
      }, 1500);

      setPollingIntervalId(intervalId);

    } catch (err) {
      addToast(err.message || 'Tạo project thất bại', 'error');
      setLoading(false);
    }
  };

  return (
    <div className="gen2-page page-enter">
      <div className="gen2-bg" />
      <div className="gen2-container">
        <div className="gen2-header">
          <h1 className="gen2-title">
            <Sparkles size={26} style={{ color: '#a89fff' }} /> Tạo slide với AI
          </h1>
          <p className="gen2-desc">Nhập chủ đề, chọn template, AI sẽ tạo slide thuyết trình cho bạn</p>
        </div>

        <div className="gen2-form-card">
          {/* Prompt */}
          <div className="gen2-field">
            <label className="gen2-label">📝 Chủ đề thuyết trình</label>
            <textarea
              id="gen-prompt"
              className="input gen2-textarea"
              rows={4}
              placeholder="Ví dụ: Giới thiệu về Trí Tuệ Nhân Tạo và ứng dụng trong giáo dục hiện đại..."
              value={form.prompt}
              onChange={(e) => setForm({ ...form, prompt: e.target.value })}
              disabled={loading || uploading}
            />
            <div className="gen2-suggestions">
              {PROMPT_SUGGESTIONS.map((suggestion) => (
                <button
                  key={suggestion.label}
                  className="chip"
                  type="button"
                  onClick={() => setForm({ ...form, prompt: suggestion.prompt })}
                  disabled={loading || uploading}
                >
                  {suggestion.label}
                </button>
              ))}
            </div>
          </div>

          {/* File Upload Zone */}
          <div className="gen2-field">
            <label className="gen2-label">📁 Hoặc tải lên tài liệu nguồn (PDF / DOCX)</label>
            {!file ? (
              <div className={`gen2-upload-zone ${uploading ? 'disabled' : ''}`}>
                <input
                  type="file"
                  id="file-upload"
                  className="gen2-file-input"
                  accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                  onChange={handleFileChange}
                  disabled={loading || uploading}
                />
                <label htmlFor="file-upload" className="gen2-upload-label">
                  <UploadCloud size={32} style={{ color: 'rgba(255,255,255,0.3)', marginBottom: 8 }} />
                  <span>Kéo thả tệp tin hoặc nhấp vào đây để tải lên</span>
                  <span className="gen2-upload-hint">Định dạng hỗ trợ: PDF, DOCX (Tối đa 50MB)</span>
                </label>
              </div>
            ) : (
              <div className="gen2-uploaded-file">
                <div className="gen2-uf-info">
                  <FileText size={20} className="gen2-file-icon" />
                  <div className="gen2-uf-details">
                    <span className="gen2-uf-name">{file.name}</span>
                    <span className="gen2-uf-size">{(file.size / (1024 * 1024)).toFixed(2)} MB</span>
                  </div>
                </div>
                {uploading ? (
                  <Loader2 size={16} className="spin" />
                ) : (
                  <button type="button" className="gen2-remove-file-btn" onClick={handleRemoveFile} disabled={loading}>
                    <X size={16} />
                  </button>
                )}
              </div>
            )}
          </div>



          <button
            id="create-btn"
            className="btn btn-primary btn-lg gen2-submit"
            onClick={handleCreate}
            disabled={loading || uploading || (!form.prompt.trim() && !uploadedFileData)}
          >
            {loading && !showProgress ? (
              <>
                <Loader2 size={18} className="spin" /> Đang tạo project...
              </>
            ) : (
              <>
                <Sparkles size={18} /> Tạo slide ngay <ChevronRight size={18} />
              </>
            )}
          </button>
        </div>
      </div>

      {/* Progress Loading Glassmorphism Modal */}
      {showProgress && (
        <div className="gen2-progress-overlay">
          <div className="gen2-progress-modal">
            <div className="gen2-progress-header">
              <Sparkles size={32} className="gen2-progress-sparkle spin-slow" />
              <h3>Đang tạo slide với AI</h3>
            </div>
            
            <div className="gen2-progress-circle-container">
              <div className="gen2-progress-circle">
                <span className="gen2-progress-percent">{progressVal}%</span>
              </div>
            </div>
            
            <div className="gen2-progress-bar-wrapper">
              <div className="gen2-progress-bar-bg">
                <div className="gen2-progress-bar-fill" style={{ width: `${progressVal}%` }}></div>
              </div>
            </div>
            
            <p className="gen2-progress-status">{progressStatus}</p>
            
            <button 
              type="button" 
              className="btn btn-secondary gen2-progress-cancel" 
              onClick={handleCancel}
            >
              Hủy tác vụ
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
