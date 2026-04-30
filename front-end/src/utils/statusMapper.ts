export const getProjectStatus = (status: number) => {
  switch (status) {
    case 0: return { text: 'Bản nháp', color: '#94a3b8' };
    case 1: return { text: 'Đang xem xét', color: '#3b82f6' };
    case 2: return { text: 'Đang xử lý', color: '#f59e0b' };
    case 3: return { text: 'Hoàn thành', color: '#22c55e' };
    case 4: return { text: 'Thất bại', color: '#ef4444' };
    default: return { text: 'Không xác định', color: '#64748b' };
  }
};

export const getTaskStatus = (status: number) => {
  switch (status) {
    case 0: return { text: 'Đang chờ', color: '#94a3b8' };
    case 1: return { text: 'Đang xử lý', color: '#f59e0b' };
    case 2: return { text: 'Thành công', color: '#22c55e' };
    case 3: return { text: 'Thất bại', color: '#ef4444' };
    default: return { text: 'Không xác định', color: '#64748b' };
  }
};

export const getTaskTypeLabel = (type: number) => {
  switch (type) {
    case 0: return 'Trích xuất nội dung từ tài liệu';
    case 1: return 'Tạo gợi ý hình ảnh (AI Prompt)';
    case 2: return 'Thiết kế slide và xuất file PPTX';
    default: return 'Tác vụ AI';
  }
};

export const getDocumentType = (type: number) => {
  switch (type) {
    case 0: return 'PDF';
    case 1: return 'DOCX';
    case 2: return 'Mô tả văn bản';
    default: return 'Không xác định';
  }
};
