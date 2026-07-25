// Mock services – simulates backend API calls

const delay = (ms = 800) => new Promise((res) => setTimeout(res, ms));
const generateId = () => Math.random().toString(36).substr(2, 9);

// ─────────────────────────────────────────────
// AUTH SERVICE
// ─────────────────────────────────────────────
export const authService = {
  async login(email, password) {
    await delay(1000);
    if (!email || !password) throw new Error('Email và mật khẩu không được trống');
    if (password.length < 6) throw new Error('Mật khẩu phải ít nhất 6 ký tự');
    return {
      user: { id: 'u001', email, name: email.split('@')[0], plan: 'free', credits: 5,
        avatar: `https://ui-avatars.com/api/?name=${email.split('@')[0]}&background=6c63ff&color=fff` },
      token: 'mock-jwt-' + generateId(),
    };
  },
  async register(name, email, password) {
    await delay(1200);
    if (!name || !email || !password) throw new Error('Vui lòng điền đầy đủ thông tin');
    if (password.length < 6) throw new Error('Mật khẩu phải ít nhất 6 ký tự');
    return {
      user: { id: generateId(), email, name, plan: 'free', credits: 5,
        avatar: `https://ui-avatars.com/api/?name=${name}&background=6c63ff&color=fff` },
      token: 'mock-jwt-' + generateId(),
    };
  },
};

// ─────────────────────────────────────────────
// TEMPLATES (clean-white là mặc định sau khi gen)
// ─────────────────────────────────────────────
export const TEMPLATES = [
  {
    id: 'clean-white',
    name: 'Clean White',
    description: 'Mặc định – sạch sẽ, tối giản, dễ đọc',
    category: 'minimal',
    colors: { bg: '#ffffff', primary: '#2d2d2d', accent: '#4f46e5', text: '#1a1a1a', surface: '#f5f5f5' },
    fonts: { heading: 'Outfit', body: 'Inter' },
    preview: 'linear-gradient(135deg,#f8f9fa,#ffffff)',
    isLight: true,
    isDefault: true,
  },
  {
    id: 'modern-dark',
    name: 'Modern Dark',
    description: 'Tối giản, sang trọng với gradient đặc trưng',
    category: 'business',
    colors: { bg: '#0d0d1a', primary: '#6c63ff', accent: '#ff6584', text: '#ffffff', surface: '#1c1c3a' },
    fonts: { heading: 'Outfit', body: 'Inter' },
    preview: 'linear-gradient(135deg,#0d0d1a,#1c1c3a)',
    popular: true,
  },
  {
    id: 'corporate-blue',
    name: 'Corporate Blue',
    description: 'Chuyên nghiệp, phù hợp doanh nghiệp',
    category: 'business',
    colors: { bg: '#001f4d', primary: '#0077e6', accent: '#00c2ff', text: '#ffffff', surface: '#002966' },
    fonts: { heading: 'Outfit', body: 'Inter' },
    preview: 'linear-gradient(135deg,#001f4d,#003080)',
  },
  {
    id: 'creative-minimal',
    name: 'Creative Minimal',
    description: 'Tối giản, sáng tạo, nhiều khoảng trắng',
    category: 'creative',
    colors: { bg: '#fafafa', primary: '#2d2d2d', accent: '#ff4757', text: '#2d2d2d', surface: '#f0f0f0' },
    fonts: { heading: 'Outfit', body: 'Inter' },
    preview: 'linear-gradient(135deg,#fafafa,#f0f0f0)',
    isLight: true,
  },
  {
    id: 'vibrant-gradient',
    name: 'Vibrant Gradient',
    description: 'Màu sắc rực rỡ, nổi bật và cuốn hút',
    category: 'creative',
    colors: { bg: '#1a0533', primary: '#f72585', accent: '#4cc9f0', text: '#ffffff', surface: '#2d0a52' },
    fonts: { heading: 'Outfit', body: 'Inter' },
    preview: 'linear-gradient(135deg,#f72585,#7209b7,#3a0ca3)',
    popular: true,
  },
  {
    id: 'nature-green',
    name: 'Nature Green',
    description: 'Xanh lá tươi mát, cảm giác tự nhiên',
    category: 'nature',
    colors: { bg: '#0a2318', primary: '#27ae60', accent: '#2ecc71', text: '#ffffff', surface: '#0f3426' },
    fonts: { heading: 'Outfit', body: 'Inter' },
    preview: 'linear-gradient(135deg,#0a2318,#0f3426)',
  },
  {
    id: 'tech-purple',
    name: 'Tech Purple',
    description: 'Công nghệ, hiện đại với màu tím neon',
    category: 'tech',
    colors: { bg: '#0a0015', primary: '#9b59b6', accent: '#e056fd', text: '#ffffff', surface: '#160026' },
    fonts: { heading: 'Outfit', body: 'Inter' },
    preview: 'linear-gradient(135deg,#0a0015,#160026)',
  },
];

export const templateService = {
  async getAll() { await delay(200); return TEMPLATES; },
  async getById(id) { await delay(100); return TEMPLATES.find((t) => t.id === id); },
};

// ─────────────────────────────────────────────
// OUTLINE GENERATION (mock backend)
// Simulates AI analyzing prompt and returning slide outline
// ─────────────────────────────────────────────
const SLIDE_TYPE_PATTERNS = ['title','content','twoColumn','imageText','content','twoColumn','quote','content','thankyou'];

function buildOutline(topic, slideCount) {
  const outline = [];

  const templates = [
    { type: 'title',     title: topic,                             description: `Slide mở đầu giới thiệu về "${topic}" – tiêu đề chính và phụ đề ngắn gọn` },
    { type: 'content',   title: `Tổng quan về ${topic}`,           description: 'Định nghĩa, khái niệm cơ bản và tầm quan trọng của chủ đề' },
    { type: 'twoColumn', title: `Phân tích ${topic}`,              description: 'So sánh hai khía cạnh chính: cơ hội và thách thức' },
    { type: 'content',   title: `Ứng dụng của ${topic}`,           description: 'Các ứng dụng thực tiễn trong cuộc sống và công việc hiện đại' },
    { type: 'imageText', title: `Xu hướng hiện nay`,               description: `Những xu hướng nổi bật liên quan đến ${topic} trong năm 2025` },
    { type: 'twoColumn', title: `Lợi ích & Hạn chế`,               description: 'Đánh giá ưu điểm và nhược điểm một cách khách quan' },
    { type: 'content',   title: `Tương lai của ${topic}`,           description: 'Dự báo và triển vọng phát triển trong 5-10 năm tới' },
    { type: 'quote',     title: `Góc nhìn chuyên gia`,             description: 'Trích dẫn quan điểm nổi tiếng về chủ đề này' },
    { type: 'content',   title: `Giải pháp & Đề xuất`,             description: 'Các bước hành động cụ thể và khuyến nghị thực tế' },
    { type: 'twoColumn', title: `Tóm tắt`,                         description: 'Tóm lại các điểm chính và kết luận của bài thuyết trình' },
    { type: 'thankyou',  title: `Cảm ơn!`,                         description: 'Slide kết thúc – thông tin liên hệ và lời cảm ơn' },
  ];

  const count = Math.min(slideCount, templates.length);
  const step = Math.max(1, Math.floor(templates.length / count));
  
  // Always include first (title) and last (thankyou)
  for (let i = 0; i < count; i++) {
    if (i === 0) outline.push({ ...templates[0], id: generateId() });
    else if (i === count - 1) outline.push({ ...templates[templates.length - 1], id: generateId() });
    else {
      const idx = Math.min(1 + Math.floor((i / (count - 2)) * (templates.length - 2)), templates.length - 2);
      outline.push({ ...templates[idx], id: generateId() });
    }
  }

  return outline;
}

function buildFullSlide(item, topic) {
  const base = { id: item.id, type: item.type };
  switch (item.type) {
    case 'title':
      return { ...base, title: item.title, subtitle: item.description };
    case 'content':
      return { ...base, title: item.title, bullets: [
        `Điểm chính 1 về ${topic}`,
        `Điểm chính 2 về ${topic}`,
        `Điểm chính 3 về ${topic}`,
        `Điểm chính 4`,
        `Điểm chính 5`,
      ].slice(0, 4) };
    case 'twoColumn':
      return { ...base, title: item.title,
        left:  { heading: '✅ Ưu điểm', points: ['Điểm mạnh 1', 'Điểm mạnh 2', 'Điểm mạnh 3'] },
        right: { heading: '⚠️ Thách thức', points: ['Thách thức 1', 'Thách thức 2', 'Thách thức 3'] } };
    case 'imageText':
      return { ...base, title: item.title, imageEmoji: '🔍', text: item.description };
    case 'quote':
      return { ...base, quote: `${topic} đang thay đổi cách chúng ta nhìn nhận thế giới và tạo ra những cơ hội chưa từng có trong lịch sử.`, author: 'Chuyên gia ngành', role: 'Nhà nghiên cứu & Tư vấn' };
    case 'thankyou':
      return { ...base, title: item.title, subtitle: item.description, contact: 'contact@example.com' };
    default:
      return { ...base, title: item.title, bullets: ['Nội dung 1', 'Nội dung 2', 'Nội dung 3'] };
  }
}

export const presentationService = {
  // Phase 1: Generate outline from prompt (fast)
  async generateOutline({ prompt, slideCount, language }) {
    await delay(1800); // simulate BE processing
    const outline = buildOutline(prompt, slideCount);
    return { outline, topic: prompt };
  },

  // Phase 2: Generate full presentation from outline
  async generateFromOutline({ outline, topic, templateId = 'clean-white' }) {
    await delay(2500); // simulate BE building slides
    const template = TEMPLATES.find((t) => t.id === templateId) || TEMPLATES[0];
    const slides = outline.map((item) => buildFullSlide(item, topic));
    return {
      id: generateId(),
      title: topic,
      templateId,
      template,
      slideCount: slides.length,
      slides,
      createdAt: new Date().toISOString(),
      status: 'completed',
    };
  },

  async delete(id) {
    await delay(400);
    return { success: true };
  },
};
