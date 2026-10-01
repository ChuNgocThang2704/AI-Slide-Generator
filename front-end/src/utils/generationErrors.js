// Turns whatever the backend / AI stack reported when slide generation could not happen into
// something a person can act on: what went wrong, and what to do next. The raw messages come
// from several places (plan limits, quota checks, the AI engine and the model providers behind
// it), some already translated by apiClient and some verbatim, some without accents.

const fold = (value) => String(value || '')
  .normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/đ/g, 'd').toLowerCase();

const number = (value) => Number(value).toLocaleString('vi-VN');

const PLAN_NAMES = { free: 'Miễn phí', pro: 'Chuyên nghiệp', ultra: 'Vô cực' };

/**
 * @returns {{ title: string, detail: string, action: 'upgrade' | 'retry' | null }}
 */
export function explainGenerationError(raw, { status } = {}) {
  const message = String(raw || '').trim();
  const text = fold(message);

  // "Do dai noi dung vuot qua gioi han cua goi FREE (15476 > 10000 ky tu)"
  const tooLong = text.match(/vuot qua gioi han cua goi (\w+)\s*\((\d+)\s*>\s*(\d+)/);
  if (tooLong) {
    const [, plan, used, limit] = tooLong;
    return {
      title: 'Tài liệu dài quá giới hạn của gói hiện tại',
      detail: `Nội dung của bạn có ${number(used)} ký tự, gói ${PLAN_NAMES[plan] || plan.toUpperCase()} chỉ nhận tối đa ${number(limit)} ký tự. Hãy rút gọn tài liệu, hoặc nâng cấp gói để dùng tài liệu dài hơn.`,
      action: 'upgrade',
    };
  }

  if (/het luot|daily slide generation limit|gioi han (tao|sinh) slide|quota.*(exceed|exhaust)|exceeded.*quota|max_slides_per_day/.test(text)) {
    return {
      title: 'Bạn đã dùng hết lượt tạo slide hôm nay',
      detail: 'Lượt sẽ được làm mới vào ngày mai. Muốn tạo thêm ngay, hãy nâng cấp gói.',
      action: 'upgrade',
    };
  }

  if (/het luot sua|revision/.test(text) && /limit|het|quota/.test(text)) {
    return {
      title: 'Bạn đã dùng hết lượt chỉnh sửa bằng AI hôm nay',
      detail: 'Lượt sẽ được làm mới vào ngày mai, hoặc nâng cấp gói để chỉnh sửa thêm.',
      action: 'upgrade',
    };
  }

  // The model providers behind the AI gateway ran out of capacity / are rate limiting.
  if (/exhausted your capacity|resource_exhausted|rate.?limit|too many requests|\b429\b|overloaded|het han muc/.test(text)) {
    return {
      title: 'Dịch vụ AI đang quá tải hoặc hết hạn mức tạm thời',
      detail: 'Đây không phải lỗi của nội dung bạn nhập. Chờ vài phút rồi thử lại.',
      action: 'retry',
    };
  }

  if (/ket noi ai engine|connection|timeout|timed out|unavailable|\b50[234]\b|failed to connect/.test(text)) {
    return {
      title: 'Không kết nối được tới dịch vụ AI',
      detail: 'Dịch vụ đang bận hoặc gián đoạn. Hãy thử lại sau ít phút; nếu vẫn lỗi, hãy báo cho quản trị viên.',
      action: 'retry',
    };
  }

  if (/khong doc duoc|extract|corrupt|encrypted|password|khong the doc/.test(text)) {
    return {
      title: 'Không đọc được nội dung tài liệu',
      detail: 'Tệp có thể bị hỏng, bị khóa mật khẩu hoặc chỉ chứa ảnh quét. Hãy thử tệp khác, hoặc dán nội dung vào ô yêu cầu.',
      action: null,
    };
  }

  if (status === 401 || status === 403) {
    return {
      title: 'Phiên đăng nhập đã hết hạn',
      detail: 'Hãy đăng nhập lại rồi thử tạo slide lần nữa.',
      action: null,
    };
  }

  // Unknown: say so plainly, and show the reason when it is short enough to be readable.
  const readable = message && message.length <= 160 && !/exception|traceback|null|undefined|at com\./i.test(message);
  return {
    title: 'Không thể tạo slide',
    detail: readable ? `Lý do: ${message}` : 'Đã có lỗi khi tạo slide. Hãy thử lại; nếu vẫn lỗi, thử rút gọn nội dung hoặc đổi tài liệu.',
    action: 'retry',
  };
}
