const fold = (value) => String(value || '')
  .normalize('NFD')
  .replace(/[\u0300-\u036f]/g, '')
  .toLowerCase()
  .replace(/\s+/g, ' ')
  .trim();

const hasAny = (text, patterns) => patterns.some((pattern) => pattern.test(text));

export function evaluatePromptQuality(value, { hasFile = false } = {}) {
  const prompt = fold(value);
  const words = prompt.match(/[\p{L}\p{N}]+/gu) || [];
  if (!prompt) {
    return {
      level: 'empty',
      label: hasFile ? 'Cần nhập yêu cầu' : 'Chưa có yêu cầu',
      message: hasFile
        ? 'Hãy nêu mục đích và phạm vi, ví dụ: “Tạo bài giảng tổng quan toàn bộ tài liệu”.'
        : 'Mô tả chủ đề hoặc mục tiêu của bài trình chiếu.',
      score: 0,
      valid: false,
    };
  }

  const purpose = hasAny(prompt, [
    /\b(tao|lam|soan|xay dung|trinh bay|tom tat|phan tich|so sanh|gioi thieu)\b/,
    /\b(create|make|prepare|present|summari[sz]e|analy[sz]e|compare|introduce)\b/,
    /\b(bai giang|bai thuyet trinh|bao cao|lecture|presentation|report)\b/,
  ]);
  const scope = hasAny(prompt, [
    /\b(toan bo|tat ca|tong quan|chuong|muc|phan|bai|tai lieu|tep|file|chu de|ve)\b/,
    /\b(entire|whole|overview|chapter|section|unit|lesson|document|file|topic|about|based on)\b/,
  ]);
  const language = hasAny(prompt, [
    /\b(tieng viet|tieng anh|song ngu|vietnamese|english|bilingual)\b/,
  ]);
  const audience = hasAny(prompt, [
    /\b(sinh vien|hoc sinh|giang vien|nguoi moi|chuyen gia|nam nhat|beginner|student|teacher|expert|audience)\b/,
  ]);
  const contentDetail = hasAny(prompt, [
    /\b(vi du|code|cong thuc|bang|bieu do|hinh anh|bai tap|cau hoi|ghi chu|example|formula|table|chart|image|exercise|question|speaker notes?)\b/,
  ]);
  const slideCount = /\b\d+\s*(slide|slides|trang|pages?)\b/.test(prompt);

  const score = [purpose, scope, language, audience, contentDetail, slideCount].filter(Boolean).length;
  const meaningful = prompt.length >= 10 && words.length >= 3;
  const valid = meaningful && (hasFile ? purpose && scope : purpose || prompt.length >= 18);

  if (!valid || score <= 1) {
    return {
      level: 'unclear',
      label: 'Chưa đủ rõ',
      message: !purpose
        ? 'Hãy bổ sung mục đích: bài giảng, báo cáo, tóm tắt hoặc thuyết trình.'
        : 'Hãy nêu phạm vi: toàn bộ tài liệu, chương/mục cụ thể hoặc chủ đề cần trình bày.',
      score,
      valid: false,
    };
  }
  if (score >= 4) {
    return {
      level: 'detailed',
      label: 'Chi tiết',
      message: 'Yêu cầu đã có đủ định hướng để AI tạo bài trình chiếu sát mục tiêu.',
      score,
      valid: true,
    };
  }
  return {
    level: 'sufficient',
    label: 'Đủ dùng',
    message: 'AI đã xác định được mục đích và phạm vi; có thể bổ sung đối tượng hoặc nội dung cần giữ.',
    score,
    valid: true,
  };
}
