import { useEffect, useState } from 'react';
import {
  AlertTriangle,
  ArrowLeft,
  Check,
  Download,
  Film,
  Loader2,
  Play,
  RefreshCw,
  Trash2,
  X,
} from 'lucide-react';
import { getVideoApiError, videoGenerationService } from '../../services/videoGenerationService';
import './VideoLibraryModal.css';

function formatCreatedAt(value) {
  if (!value) return 'Không rõ thời gian';
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value);
  const date = new Date(hasTimezone ? value : `${value}Z`);
  if (Number.isNaN(date.getTime())) return 'Không rõ thời gian';
  return date.toLocaleString('vi-VN', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function VideoLibraryModal({ open, onClose, onNotify }) {
  const [videos, setVideos] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [selectedVideo, setSelectedVideo] = useState(null);
  const [pendingDeleteId, setPendingDeleteId] = useState(null);
  const [deletingId, setDeletingId] = useState(null);
  const [downloadingId, setDownloadingId] = useState(null);

  const loadVideos = async (signal) => {
    if (!videoGenerationService.hasSession()) {
      setError('Phiên đăng nhập Gen Video chưa sẵn sàng. Vui lòng đăng nhập lại GenSlide.');
      return;
    }

    setLoading(true);
    setError('');
    try {
      const result = await videoGenerationService.getMyVideos(signal);
      setVideos(result.videos);
    } catch (loadError) {
      if (loadError?.code !== 'ERR_CANCELED') {
        setError(getVideoApiError(loadError, 'Không tải được danh sách video'));
      }
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  };

  useEffect(() => {
    if (!open) return undefined;
    const controller = new AbortController();
    const loadTimer = window.setTimeout(() => loadVideos(controller.signal), 0);
    return () => {
      window.clearTimeout(loadTimer);
      controller.abort();
    };
  }, [open]);

  const handleClose = () => {
    setSelectedVideo(null);
    setPendingDeleteId(null);
    setError('');
    onClose();
  };

  const handleDelete = async (videoId) => {
    setDeletingId(videoId);
    setError('');
    try {
      await videoGenerationService.deleteVideo(videoId);
      setVideos((current) => current.filter((video) => video.id !== videoId));
      setPendingDeleteId(null);
      if (selectedVideo?.id === videoId) setSelectedVideo(null);
      onNotify?.('Đã xóa video', 'success');
    } catch (deleteError) {
      const message = getVideoApiError(deleteError, 'Không thể xóa video');
      setError(message);
      onNotify?.(message, 'error');
    } finally {
      setDeletingId(null);
    }
  };

  const handleDownload = async (video) => {
    setDownloadingId(video.id);
    try {
      const response = await fetch(video.video_url);
      if (!response.ok) throw new Error('Không tải được video');
      const blob = await response.blob();
      const objectUrl = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = objectUrl;
      anchor.download = `video-${video.id}.mp4`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(objectUrl);
    } catch {
      window.open(video.video_url, '_blank', 'noopener,noreferrer');
      onNotify?.('Đã mở video trong tab mới để tải xuống', 'info');
    } finally {
      setDownloadingId(null);
    }
  };

  if (!open) return null;

  return (
    <div className="video-library-overlay" role="presentation">
      <section className="video-library-dialog" role="dialog" aria-modal="true" aria-labelledby="video-library-title">
        <header className="video-library-header">
          <div className="video-library-title">
            <span><Film size={19} /></span>
            <div>
              <h2 id="video-library-title">Video của tôi</h2>
              <p>{videos.length} video đã lưu</p>
            </div>
          </div>
          <div className="video-library-header-actions">
            <button type="button" onClick={() => loadVideos()} disabled={loading} title="Làm mới" aria-label="Làm mới">
              <RefreshCw size={17} className={loading ? 'spin' : ''} />
            </button>
            <button type="button" onClick={handleClose} title="Đóng" aria-label="Đóng">
              <X size={18} />
            </button>
          </div>
        </header>

        {error && <div className="video-library-alert"><AlertTriangle size={17} /><span>{error}</span></div>}

        {selectedVideo ? (
          <div className="video-library-player">
            <button type="button" className="video-library-back" onClick={() => setSelectedVideo(null)}>
              <ArrowLeft size={16} /> Quay lại danh sách
            </button>
            <video src={selectedVideo.video_url} controls autoPlay preload="metadata" />
            <div className="video-library-player-meta">
              <div>
                <strong>Video #{selectedVideo.id}</strong>
                <span>{formatCreatedAt(selectedVideo.created_at)}</span>
              </div>
              <button type="button" className="btn btn-primary btn-sm" onClick={() => handleDownload(selectedVideo)} disabled={downloadingId === selectedVideo.id}>
                {downloadingId === selectedVideo.id ? <Loader2 size={15} className="spin" /> : <Download size={15} />}
                Tải xuống
              </button>
            </div>
          </div>
        ) : (
          <div className="video-library-body">
            {loading ? (
              <div className="video-library-state"><Loader2 size={24} className="spin" /><span>Đang tải danh sách video...</span></div>
            ) : videos.length === 0 ? (
              <div className="video-library-state"><Film size={30} /><strong>Chưa có video nào</strong><span>Video hoàn thành sẽ xuất hiện tại đây.</span></div>
            ) : (
              <div className="video-library-list">
                {videos.map((video) => (
                  <article className="video-library-row" key={video.id}>
                    <button type="button" className="video-library-thumbnail" onClick={() => setSelectedVideo(video)} aria-label={`Xem video ${video.id}`}>
                      <video src={video.video_url} muted preload="metadata" />
                      <span><Play size={18} fill="currentColor" /></span>
                    </button>
                    <div className="video-library-info">
                      <strong>Video #{video.id}</strong>
                      <span>{formatCreatedAt(video.created_at)}</span>
                      <small>{video.username}</small>
                    </div>
                    <div className="video-library-actions">
                      <button type="button" onClick={() => setSelectedVideo(video)} title="Xem video" aria-label="Xem video"><Play size={16} /></button>
                      <button type="button" onClick={() => handleDownload(video)} disabled={downloadingId === video.id} title="Tải xuống" aria-label="Tải xuống">
                        {downloadingId === video.id ? <Loader2 size={16} className="spin" /> : <Download size={16} />}
                      </button>
                      {pendingDeleteId === video.id ? (
                        <div className="video-library-delete-confirm">
                          <span>Xóa?</span>
                          <button type="button" onClick={() => handleDelete(video.id)} disabled={deletingId === video.id} title="Xác nhận xóa" aria-label="Xác nhận xóa">
                            {deletingId === video.id ? <Loader2 size={15} className="spin" /> : <Check size={15} />}
                          </button>
                          <button type="button" onClick={() => setPendingDeleteId(null)} disabled={deletingId === video.id} title="Hủy xóa" aria-label="Hủy xóa"><X size={15} /></button>
                        </div>
                      ) : (
                        <button type="button" className="danger" onClick={() => setPendingDeleteId(video.id)} title="Xóa video" aria-label="Xóa video"><Trash2 size={16} /></button>
                      )}
                    </div>
                  </article>
                ))}
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  );
}
