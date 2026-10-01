// Topic → visual system. Every built-in theme is reachable, and a topic with
// several fitting themes rotates between them (by project name) so two decks on
// the same subject do not come out identical.
const TOPIC_PROFILES = [
  {
    id: 'technology',
    label: 'Công nghệ & AI',
    themes: ['blue-planet', 'tech-purple', 'modern-dark'],
    keywords: ['ai', 'trí tuệ nhân tạo', 'công nghệ', 'phần mềm', 'dữ liệu', 'machine learning', 'deep learning', 'robot', 'internet', 'chuyển đổi số', 'lập trình', 'an ninh mạng', 'blockchain', 'điện toán', 'vũ trụ', 'không gian'],
  },
  {
    id: 'nature',
    label: 'Môi trường & tự nhiên',
    themes: ['nature-green', 'ocean-teal'],
    keywords: ['môi trường', 'tự nhiên', 'khí hậu', 'xanh', 'sinh học', 'nông nghiệp', 'năng lượng', 'sinh thái', 'rừng', 'biển', 'đại dương', 'thực vật', 'động vật', 'bền vững', 'cà phê', 'nông sản'],
  },
  {
    id: 'health',
    label: 'Sức khỏe & đời sống',
    themes: ['ocean-teal', 'clean-white'],
    keywords: ['sức khỏe', 'y tế', 'bệnh', 'dinh dưỡng', 'thể thao', 'tâm lý', 'bác sĩ', 'thuốc', 'thiền', 'lối sống'],
  },
  {
    id: 'business',
    label: 'Kinh doanh & dữ liệu',
    themes: ['gradient-border', 'modern-dark', 'clean-white'],
    keywords: ['kinh doanh', 'marketing', 'doanh nghiệp', 'thị trường', 'chiến lược', 'doanh thu', 'khách hàng', 'thống kê', 'khởi nghiệp', 'quản lý', 'bán hàng', 'báo cáo'],
  },
  {
    id: 'finance',
    label: 'Tài chính & cao cấp',
    themes: ['midnight-gold', 'modern-dark'],
    keywords: ['tài chính', 'đầu tư', 'ngân hàng', 'chứng khoán', 'bất động sản', 'cao cấp', 'thương hiệu', 'sang trọng', 'bảo hiểm', 'kinh tế'],
  },
  {
    id: 'education',
    label: 'Giáo dục & học thuật',
    themes: ['soft-blue', 'clean-white'],
    keywords: ['giáo dục', 'bài giảng', 'học tập', 'nghiên cứu', 'khoa học', 'toán học', 'sinh viên', 'trường học', 'giảng dạy', 'luận văn', 'kiến thức'],
  },
  {
    id: 'humanities',
    label: 'Văn hóa & nhân văn',
    themes: ['editorial-paper', 'midnight-gold'],
    keywords: ['lịch sử', 'văn học', 'văn hóa', 'triết học', 'bảo tàng', 'di sản', 'truyền thống', 'tôn giáo', 'ngôn ngữ', 'báo chí', 'xuất bản'],
  },
  {
    id: 'creative',
    label: 'Sáng tạo & truyền thông',
    themes: ['playful-yellow', 'gradient-border'],
    keywords: ['sáng tạo', 'thiết kế', 'nghệ thuật', 'truyền thông', 'du lịch', 'ẩm thực', 'thời trang', 'âm nhạc', 'phim', 'trẻ em', 'sự kiện', 'lễ hội'],
  },
];

const GENERAL_THEMES = ['royal-purple', 'soft-blue', 'ocean-teal', 'clean-white'];

function toSearchableText(value) {
  if (value == null) return '';
  if (typeof value === 'string' || typeof value === 'number') return String(value);
  if (Array.isArray(value)) return value.map(toSearchableText).join(' ');
  if (typeof value === 'object') return Object.values(value).map(toSearchableText).join(' ');
  return '';
}

function normalizeVietnamese(value) {
  return toSearchableText(value)
    .toLocaleLowerCase('vi')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/đ/g, 'd');
}

function hashText(value) {
  let hash = 0;
  for (const char of String(value || '')) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  return hash;
}

// Whole-word match so short keywords such as "ai" do not fire inside other words.
function countKeyword(text, keyword) {
  const normalized = normalizeVietnamese(keyword);
  const pattern = new RegExp(`(^|[^a-z0-9])${normalized.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}([^a-z0-9]|$)`, 'g');
  return (text.match(pattern) || []).length;
}

/** Selects one coherent built-in visual system for an entire deck without an AI call. */
export function recommendTemplateForDeck(project, slides = []) {
  const titleText = normalizeVietnamese([project?.name, project?.description]);
  const bodyText = normalizeVietnamese(slides);
  let bestProfile = null;
  let bestScore = 0;

  TOPIC_PROFILES.forEach((profile) => {
    // A keyword in the title says more about the subject than one in the body.
    const score = profile.keywords.reduce((total, keyword) => (
      total
      + (countKeyword(titleText, keyword) > 0 ? 3 : 0)
      + Math.min(2, countKeyword(bodyText, keyword))
    ), 0);
    if (score > bestScore) {
      bestScore = score;
      bestProfile = profile;
    }
  });

  const seed = hashText(project?.name || project?.id || '');
  if (!bestProfile) {
    return {
      id: 'general',
      label: 'Nội dung tổng quát',
      themeId: GENERAL_THEMES[seed % GENERAL_THEMES.length],
    };
  }
  return {
    id: bestProfile.id,
    label: bestProfile.label,
    themeId: bestProfile.themes[seed % bestProfile.themes.length],
  };
}

export const TOPIC_THEME_IDS = [...new Set([...TOPIC_PROFILES.flatMap((profile) => profile.themes), ...GENERAL_THEMES])];
