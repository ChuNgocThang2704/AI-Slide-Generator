/*
 * Prompt-driven templates.
 *
 * A generated template is fully described by a short code kept in the project's
 * `templateId` (e.g. "gen1.28.1.0.2.3.1.0.1.0"), so it needs no backend storage
 * and survives reloads, other devices and exports. `buildGeneratedTheme(code)`
 * is a pure function that turns the code into every table the renderer needs.
 *
 * The code is derived from the prompt: subject keywords pick the hue family, the
 * light/dark mood, the typeface and the ornament, and the remaining choices come
 * from a seeded random source, so the same prompt is stable and a different
 * prompt (or a re-roll) gives a visibly different template. Every colour is
 * built from HSL with fixed lightness bands, which keeps text readable.
 */

const PREFIX = 'gen1.';
export const isGeneratedTheme = (id) => typeof id === 'string' && id.startsWith(PREFIX);

// Only typefaces already loaded by the app and verified against the text planner.
const FONT_PAIRS = [
  { title: "'Nunito', sans-serif", weight: 700, size: 36 },
  { title: "'Playfair Display', serif", weight: 700, size: 38 },
  { title: "'Space Grotesk', sans-serif", weight: 700, size: 36 },
  { title: "'Merriweather', serif", weight: 700, size: 34 },
  { title: "'Plus Jakarta Sans', sans-serif", weight: 700, size: 36 },
  { title: "'Nunito', sans-serif", weight: 800, size: 36 },
  { title: "'Saira', sans-serif", weight: 600, size: 36 },
  { title: "'Exo 2', sans-serif", weight: 700, size: 36 },
];
const BODY_FONT = "'Inter', sans-serif";
const COVERS = ['cover-center', 'cover-left', 'cover-split', 'cover-hero'];
const CLOSINGS = ['closing-cards', 'closing-list', 'closing-center'];
// The last entry, 'none', is a choice for the user; random generation only picks the first six.
const DECOR_KINDS = ['orbs', 'frame', 'waves', 'dots', 'rings', 'stripe', 'none'];
const RANDOM_DECOR_COUNT = DECOR_KINDS.length - 1;

// keywords are accent-folded; `dark` is the chance of a dark mood.
const FAMILIES = [
  { id: 'coffee', label: 'Cà phê & đồ uống', hue: 27, dark: 0.35, fonts: [1, 3], words: ['ca phe', 'cafe', 'coffee', 'tra ', 'socola', 'chocolate', 'do uong', 'ruou', 'bia '] },
  { id: 'food', label: 'Ẩm thực', hue: 18, dark: 0.3, fonts: [5, 0, 4], words: ['am thuc', 'mon an', 'nau an', 'banh', 'nha hang', 'thuc pham', 'bep ', 'cong thuc nau', 'nau ', 'pho ', 'mon '] },
  { id: 'ocean', label: 'Biển & nước', hue: 198, dark: 0.35, fonts: [0, 4, 7], words: ['bien', 'dai duong', 'nuoc', 'thuy ', 'hai san', 'lan bien', 'song ngoi', 'ca map', 'thuy san', 'nuoi trong'] },
  { id: 'nature', label: 'Thiên nhiên', hue: 142, dark: 0.4, fonts: [3, 0, 1], words: ['rung', 'thien nhien', 'moi truong', 'sinh thai', 'nong nghiep', 'thuc vat', 'cay ', 'khi hau', 'ben vung', 'tai che', 'do thi xanh', 'nang luong sach', 'phat trien ben'] },
  { id: 'animals', label: 'Động vật', hue: 34, dark: 0.15, fonts: [5, 0], words: ['thu cung', 'dong vat', 'meo ', 'cho ', 'chim ', 'nuoi thu', 'thu y'] },
  { id: 'space', label: 'Vũ trụ', hue: 262, dark: 0.95, fonts: [7, 6, 2], words: ['vu tru', 'khong gian', 'hanh tinh', 'thien van', 'ngoi sao', 'ten lua', 'he mat troi', 'thien ha'] },
  { id: 'tech', label: 'Công nghệ', hue: 252, dark: 0.75, fonts: [2, 6, 7], words: ['cong nghe', 'tri tue nhan tao', 'phan mem', 'du lieu', 'robot', 'lap trinh', 'an ninh mang', 'blockchain', 'may hoc', 'internet', 'python', 'cach mang cong nghiep', 'so hoa', 'chuyen doi so', 'may tinh', 'ung dung', 'linux', 'he dieu hanh', 'giai thuat', 'mang may tinh'] },
  { id: 'transport', label: 'Giao thông & xe cộ', hue: 205, dark: 0.55, fonts: [7, 2, 6], words: ['o to', 'xe dien', 'giao thong', 'pin ', 'hang khong', 'duong sat', 'may bay', 'cang bien', 'van tai', 'lithium'] },
  { id: 'industry', label: 'Công nghiệp & xây dựng', hue: 32, dark: 0.5, fonts: [2, 6, 3], words: ['san xuat', 'cong nghiep', 'xay dung', 'co khi', 'nha may', 'xi mang', 'dien luc', 'logistic', 'ky su', 'ky thuat', 'quy trinh', 'che tao', 'vat lieu'] },
  { id: 'finance', label: 'Tài chính', hue: 44, dark: 0.85, fonts: [1, 3], words: ['tai chinh', 'dau tu', 'ngan hang', 'chung khoan', 'kinh te', 'bat dong san', 'bao hiem', 'ke toan', 'thue ', 'ngan sach', 'tien te', 'kiem toan'] },
  { id: 'business', label: 'Kinh doanh', hue: 218, dark: 0.4, fonts: [4, 2, 0], words: ['kinh doanh', 'marketing', 'doanh nghiep', 'chien luoc', 'khoi nghiep', 'ban hang', 'quan ly', 'bao cao', 'nhan su', 'khach hang', 'thuong hieu', 'san pham moi', 'ke hoach', 'du an', 'thi truong', 'doanh thu', 'cong ty', 'su kien', 'ra mat', 'tuyen dung', 'rui ro'] },
  { id: 'law', label: 'Pháp luật & chính sách', hue: 224, dark: 0.35, fonts: [3, 1, 4], words: ['luat', 'phap luat', 'quyen ', 'tu phap', 'toa an', 'hop dong', 'phap che', 'nghi dinh', 'lao dong', 'chinh sach', 'chinh phu', 'nha nuoc', 'hanh chinh', 'cong dan', 'dao duc'] },
  { id: 'health', label: 'Sức khỏe & y tế', hue: 168, dark: 0.15, fonts: [0, 4], words: ['suc khoe', 'y te', 'benh', 'thuoc', 'dinh duong', 'the thao', 'tam ly', 'thien ', 'ung thu', 'y hoc', 'vac xin', 'phau thuat', 'bac si', 'cham soc', 'phong ngua', 'co the', 'vitamin', 'khoang chat', 'tieu duong', 'yoga'] },
  { id: 'education', label: 'Giáo dục & học thuật', hue: 214, dark: 0.15, fonts: [0, 4, 3], words: ['giao duc', 'bai giang', 'hoc tap', 'truong hoc', 'sinh vien', 'khoa hoc', 'nghien cuu', 'kien thuc', 'toan hoc', 'vat ly', 'hoa hoc', 'sinh hoc', 'thi nghiem', 'ham so', 'lop ', 'hoc sinh', 'ngoai ngu', 'phuong phap hoc', 'luan van', 'giang day', 'dia ly', 'kinh te hoc', 'tieng anh'] },
  { id: 'skills', label: 'Kỹ năng & phát triển bản thân', hue: 268, dark: 0.3, fonts: [4, 0, 2], words: ['ky nang', 'thuyet trinh', 'giao tiep', 'lanh dao', 'thoi gian', 'ban than', 'tu duy', 'dong luc', 'lam viec nhom', 'hieu qua', 'phong van', 'cam xuc', 'thoi quen'] },
  { id: 'history', label: 'Lịch sử & văn hóa', hue: 22, dark: 0.2, fonts: [1, 3], words: ['lich su', 'van hoa', 'di san', 'truyen thong', 'bao tang', 'van hoc', 'co dai', 'chien tranh', 'trieu dai', 'tet ', 'le hoi', 'dan toc', 'cuoc doi', 'ho chi minh', 'su nghiep', 'nhan vat'] },
  { id: 'arts', label: 'Âm nhạc & nghệ thuật', hue: 300, dark: 0.5, fonts: [1, 5, 4], words: ['nhac', 'am nhac', 'hoi hoa', 'nghe thuat', 'dien anh', 'san khau', 'nhac cu', 'ca si', 'bai hat', 'phim '] },
  { id: 'design', label: 'Thiết kế & kiến trúc', hue: 30, dark: 0.2, fonts: [1, 4, 0], words: ['noi that', 'kien truc', 'thiet ke', 'trang tri', 'mau sac', 'phong cach', 'do hoa'] },
  { id: 'travel', label: 'Du lịch', hue: 188, dark: 0.25, fonts: [0, 5, 4], words: ['du lich', 'kham pha', 'phieu luu', 'dao ', 'chuyen di', 'lu hanh', 'khach san', 'diem den'] },
  { id: 'fashion', label: 'Thời trang & làm đẹp', hue: 335, dark: 0.35, fonts: [1, 4], words: ['thoi trang', 'lam dep', 'tinh yeu', 'hoa ', 'cuoi ', 'my pham', 'toc ', 'da ', 'phu nu'] },
  { id: 'energy', label: 'Năng lượng & thể thao', hue: 8, dark: 0.55, fonts: [6, 7, 2], words: ['nang luong', 'the thao', 'bong da', 'lua ', 'suc manh', 'toc do', 'olympic', 'giai dau', 'sea games', 'cau thu'] },
  { id: 'safety', label: 'An toàn & cứu hộ', hue: 12, dark: 0.2, fonts: [4, 2, 0], words: ['an toan', 'phong chay', 'chua chay', 'cuu ho', 'tai nan', 'cap cuu', 'bao ve', 'bao lu', 'thien tai', 'ung pho', 'phong chong'] },
  { id: 'kids', label: 'Trẻ em & sáng tạo', hue: 46, dark: 0.05, fonts: [5, 0], words: ['tre em', 'tro choi', 'hoat hinh', 'sang tao', 'vui ', 'be ', 'mam non', 'thieu nhi'] },
];

const fold = (value) => String(value || '')
  .toLocaleLowerCase('vi')
  .normalize('NFD')
  .replace(/[̀-ͯ]/g, '')
  .replace(/đ/g, 'd');

function hashText(value) {
  let hash = 2166136261;
  for (const char of String(value || '')) {
    hash ^= char.charCodeAt(0);
    hash = Math.imul(hash, 16777619) >>> 0;
  }
  return hash >>> 0;
}

function seeded(seed) {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function detectTopicFamily(text) {
  const haystack = ` ${fold(text)} `;
  let best = null;
  let bestScore = 0;
  FAMILIES.forEach((family) => {
    // Words match from the start of a word, so "ai" never fires inside "hai" or "bai".
    const score = family.words.reduce((total, word) => total + (haystack.includes(` ${word}`) ? 1 : 0), 0);
    if (score > bestScore) { best = family; bestScore = score; }
  });
  return best;
}

/** A theme code for this subject. `variation` re-rolls the look for the same subject. */
export function makeThemeCode(subject, variation = 0) {
  const text = Array.isArray(subject) ? subject.join(' ') : String(subject || '');
  const rng = seeded(hashText(fold(text)) + Math.imul(variation | 0, 7919));
  const family = detectTopicFamily(text);
  const hue = family
    ? (family.hue + Math.round((rng() - 0.5) * 28) + 360) % 360
    : Math.floor(rng() * 360);
  const dark = rng() < (family ? family.dark : 0.5) ? 1 : 0;
  const sat = Math.floor(rng() * 3);
  const bg = Math.floor(rng() * 3);
  const decor = Math.floor(rng() * RANDOM_DECOR_COUNT);
  const font = family && rng() < 0.75
    ? family.fonts[Math.floor(rng() * family.fonts.length)]
    : Math.floor(rng() * FONT_PAIRS.length);
  const cover = Math.floor(rng() * COVERS.length);
  const closing = Math.floor(rng() * CLOSINGS.length);
  const shift = Math.floor(rng() * 3);
  return `${PREFIX}${[hue, dark, sat, bg, decor, font, cover, closing, shift].join('.')}`;
}

const BRIEF_FONT = { friendly: 0, 'elegant-serif': 1, tech: 2, 'classic-serif': 3, 'modern-sans': 4, 'bold-rounded': 5, futuristic: 6, 'sci-fi': 7 };
const BRIEF_COVER = { centered: 0, left: 1, split: 2, hero: 3 };
const BRIEF_ACCENT = { analogous: 0, 'analogous-alt': 1, contrast: 2 };
const BRIEF_SATURATION = { soft: 0, medium: 1, vivid: 2 };

/**
 * A theme code from an AI design brief (hue, mood, type, ornament...). Every value is looked up
 * in a fixed vocabulary, so a malformed or hostile brief can only ever produce a valid theme.
 * `variation` > 0 keeps the brief's colour and mood but re-rolls the ornament and composition.
 */
export function codeFromBrief(brief, subject = '', variation = 0) {
  if (!brief || !Number.isFinite(Number(brief.hue))) return makeThemeCode(subject, variation);
  const rng = seeded(hashText(fold(subject)) + Math.imul(variation | 0, 7919) + 31);
  const roll = (count) => Math.floor(rng() * count);
  const reroll = variation > 0;
  const hue = ((Math.round(Number(brief.hue)) + (reroll ? Math.round((rng() - 0.5) * 24) : 0)) % 360 + 360) % 360;
  const dark = brief.mood === 'dark' ? 1 : 0;
  const sat = BRIEF_SATURATION[brief.saturation] ?? 1;
  const decor = reroll || !DECOR_KINDS.includes(brief.decor) || brief.decor === 'none' ? roll(RANDOM_DECOR_COUNT) : DECOR_KINDS.indexOf(brief.decor);
  const font = BRIEF_FONT[brief.typeface] ?? 4;
  const cover = reroll || BRIEF_COVER[brief.cover] === undefined ? roll(COVERS.length) : BRIEF_COVER[brief.cover];
  const shift = reroll ? roll(3) : (BRIEF_ACCENT[brief.accent] ?? 0);
  return `${PREFIX}${[hue, dark, sat, roll(3), decor, font, cover, roll(CLOSINGS.length), shift].join('.')}`;
}

/* ─────────────────────────────── colour helpers ─────────────────────────────── */

const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

function hslToRgb(h, s, l) {
  const hue = ((h % 360) + 360) % 360;
  const sat = clamp(s, 0, 100) / 100;
  const light = clamp(l, 0, 100) / 100;
  const k = (n) => (n + hue / 30) % 12;
  const a = sat * Math.min(light, 1 - light);
  const f = (n) => light - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)));
  return [Math.round(f(0) * 255), Math.round(f(8) * 255), Math.round(f(4) * 255)];
}

const toHex = ([r, g, b]) => `#${[r, g, b].map((v) => v.toString(16).padStart(2, '0')).join('')}`;
const hsl = (h, s, l) => toHex(hslToRgb(h, s, l));
const hexToRgb = (hex) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
const rgba = (rgb, alpha) => `rgba(${rgb[0]}, ${rgb[1]}, ${rgb[2]}, ${alpha})`;

function luminance([r, g, b]) {
  const lin = (v) => {
    const c = v / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

export function contrastRatio(rgbA, rgbB) {
  const [hi, lo] = [luminance(rgbA), luminance(rgbB)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

// Move lightness away from the page colour until the ink reads against it.
function readableLightness(h, s, startL, pageRgb, minRatio, dark) {
  let lightness = startL;
  for (let i = 0; i < 40 && contrastRatio(hslToRgb(h, s, lightness), pageRgb) < minRatio; i += 1) {
    lightness += dark ? 2 : -2;
  }
  return clamp(lightness, 4, 96);
}

/* ─────────────────────────────── theme builder ─────────────────────────────── */

const cache = new Map();

export function parseThemeCode(code) {
  if (!isGeneratedTheme(code)) return null;
  const parts = code.slice(PREFIX.length).split('.').map(Number);
  if (parts.length !== 9 || parts.some((part) => !Number.isFinite(part))) return null;
  const [hue, dark, sat, bg, decor, font, cover, closing, shift] = parts;
  return {
    hue: ((hue % 360) + 360) % 360,
    dark: dark === 1,
    sat: clamp(sat, 0, 2),
    bg: clamp(bg, 0, 2),
    decor: clamp(decor, 0, DECOR_KINDS.length - 1),
    font: clamp(font, 0, FONT_PAIRS.length - 1),
    cover: clamp(cover, 0, COVERS.length - 1),
    closing: clamp(closing, 0, CLOSINGS.length - 1),
    shift: clamp(shift, 0, 2),
  };
}

const HUE_NAMES = ['đỏ', 'cam', 'hổ phách', 'vàng', 'xanh chanh', 'lục', 'ngọc', 'lam ngọc', 'lam', 'chàm', 'tím', 'hồng'];
const hueName = (hue) => HUE_NAMES[Math.floor((((hue + 15) % 360) / 360) * HUE_NAMES.length)];

export function buildGeneratedTheme(code) {
  if (cache.has(code)) return cache.get(code);
  const spec = parseThemeCode(code) || parseThemeCode(makeThemeCode(code));
  const { hue, dark, sat, bg: bgStyle, decor, font, cover, closing, shift } = spec;
  const S = [46, 62, 78][sat];
  const accentHue = hue + [28, -28, 150][shift];
  const fontPair = FONT_PAIRS[font];

  let bg; let bgGrad; let primary; let accent; let text; let textSubRgb; let textRgb;
  if (dark) {
    bg = hsl(hue, 40, 8);
    bgGrad = [
      `linear-gradient(145deg, ${hsl(hue, 45, 7)} 0%, ${hsl(hue + 12, 38, 14)} 100%)`,
      `radial-gradient(120% 90% at 15% 0%, ${hsl(hue, 45, 17)} 0%, ${hsl(hue, 45, 6)} 65%)`,
      `linear-gradient(200deg, ${hsl(hue, 40, 10)} 0%, ${hsl(hue + 40, 35, 8)} 55%, ${hsl(hue, 45, 15)} 100%)`,
    ][bgStyle];
    primary = hsl(hue, 80, 64);
    accent = hsl(accentHue, 85, readableLightness(accentHue, 85, 62, hslToRgb(hue, 40, 8), 4, true));
    textRgb = hslToRgb(hue, 25, 96);
    textSubRgb = rgba(textRgb, 0.72);
  } else {
    bg = hsl(hue, 45, 97);
    bgGrad = [
      `linear-gradient(160deg, ${hsl(hue, 55, 96)} 0%, ${hsl(hue + 14, 40, 99)} 55%, ${hsl(hue - 10, 55, 93)} 100%)`,
      `radial-gradient(120% 90% at 85% 0%, ${hsl(hue, 60, 93)} 0%, ${hsl(hue, 40, 98)} 60%)`,
      `linear-gradient(120deg, ${hsl(hue, 50, 97)} 0%, ${hsl(hue, 50, 97)} 64%, ${hsl(hue, 55, 93)} 64%, ${hsl(hue, 55, 93)} 100%)`,
    ][bgStyle];
    primary = hsl(hue, S, 30);
    accent = hsl(accentHue, 78, readableLightness(accentHue, 78, 44, hslToRgb(hue, 45, 97), 3.2, false));
    textRgb = hslToRgb(hue, 50, 13);
    textSubRgb = hsl(hue, 25, 36);
  }
  text = toHex(textRgb);
  const accentRgb = hexToRgb(accent);
  const primaryRgb = hslToRgb(hue, dark ? 80 : S, dark ? 64 : 30);
  const onAccent = luminance(accentRgb) > 0.4 ? '#1a1a1a' : '#fefefe';
  const isLight = !dark;

  const theme = {
    id: code,
    isGenerated: true,
    bg,
    bgGrad,
    primary,
    accent,
    accentAlt: hsl(accentHue + 20, 80, dark ? 68 : 50),
    text,
    textSub: textSubRgb,
    surface: dark ? rgba(accentRgb, 0.08) : hsl(hue, 60, 95),
    surfaceAlt: dark ? rgba(primaryRgb, 0.06) : '#ffffff',
    surfaceBorder: dark ? rgba(accentRgb, 0.3) : rgba(primaryRgb, 0.22),
    accentGrad: `linear-gradient(135deg, ${primary} 0%, ${accent} 100%)`,
    panelBg: `linear-gradient(160deg, ${primary} 0%, ${accent} 100%)`,
    fontTitle: fontPair.title,
    fontBody: BODY_FONT,
    isLight,
    decorKind: DECOR_KINDS[decor],
  };

  const design = {
    accent,
    onAccent,
    titleSize: fontPair.size,
    weight: fontPair.weight,
    decor: shift === 2 ? null : 'underline',
    cover: COVERS[cover],
    closing: CLOSINGS[closing],
  };

  const hexBare = (value) => value.replace('#', '').toUpperCase();
  const textPalette = {
    title: fontPair.title,
    body: BODY_FONT,
    text,
    sub: textSubRgb,
  };
  const exportPalette = {
    bg: hexBare(bg),
    primary: hexBare(primary),
    accent: hexBare(accent),
    text: hexBare(text),
    textSub: hexBare(toHex(dark ? hslToRgb(hue, 20, 78) : hslToRgb(hue, 25, 36))),
    surface: hexBare(dark ? hsl(hue, 35, 15) : hsl(hue, 60, 95)),
  };
  const cssVars = {
    '--card-bg': dark ? 'rgba(255, 255, 255, 0.06)' : rgba(primaryRgb, 0.06),
    '--card-border': dark ? 'rgba(255, 255, 255, 0.14)' : rgba(primaryRgb, 0.2),
  };

  const built = {
    code,
    spec,
    name: `${dark ? 'Đêm' : 'Sáng'} ${hueName(hue)} · ${['Mềm', 'Đậm', 'Rực'][sat]}`,
    theme,
    design,
    textPalette,
    exportPalette,
    cssVars,
    accentRgb,
    primaryRgb,
    contrast: contrastRatio(textRgb, hslToRgb(hue, dark ? 40 : 45, dark ? 8 : 97)),
  };
  cache.set(code, built);
  return built;
}

// Labels and choices the tuning panel offers; each maps to one field of the code.
export const THEME_OPTIONS = {
  saturation: ['Mềm', 'Đậm', 'Rực'],
  accent: ['Liền kề', 'Liền kề 2', 'Tương phản'],
  background: ['Dịu', 'Tâm điểm', 'Chéo'],
  decor: ['Cầu sáng', 'Khung', 'Sóng', 'Chấm', 'Vòng', 'Dải chéo', 'Không'],
  cover: ['Giữa', 'Trái', 'Chia đôi', 'Toàn cảnh'],
  closing: ['Thẻ', 'Danh sách', 'Giữa'],
  font: FONT_PAIRS.map((pair, index) => ({
    label: ['Nunito', 'Playfair', 'Space Grotesk', 'Merriweather', 'Jakarta Sans', 'Nunito đậm', 'Saira', 'Exo 2'][index],
    family: pair.title,
    weight: pair.weight,
  })),
};

/** The code for a spec (the inverse of parseThemeCode). Every field is clamped to its range. */
export function serializeThemeSpec(spec) {
  const int = (value, min, max) => clamp(Math.round(Number(value) || 0), min, max);
  return `${PREFIX}${[
    ((int(spec.hue, -3600, 3600) % 360) + 360) % 360,
    spec.dark ? 1 : 0,
    int(spec.sat, 0, 2),
    int(spec.bg, 0, 2),
    int(spec.decor, 0, DECOR_KINDS.length - 1),
    int(spec.font, 0, FONT_PAIRS.length - 1),
    int(spec.cover, 0, COVERS.length - 1),
    int(spec.closing, 0, CLOSINGS.length - 1),
    int(spec.shift, 0, 2),
  ].join('.')}`;
}

/** A theme code with some fields changed. An invalid code is returned unchanged. */
export function withThemeSpec(code, changes) {
  const spec = parseThemeCode(code);
  return spec ? serializeThemeSpec({ ...spec, ...changes }) : code;
}

/** Wraps a `{ themeId: value }` table so generated codes resolve on demand. */
export function withGeneratedThemes(base, pick) {
  return new Proxy(base, {
    get(target, prop, receiver) {
      if (typeof prop === 'string' && isGeneratedTheme(prop)) return pick(buildGeneratedTheme(prop));
      return Reflect.get(target, prop, receiver);
    },
    has(target, prop) {
      return (typeof prop === 'string' && isGeneratedTheme(prop)) || Reflect.has(target, prop);
    },
  });
}

/** Text describing the deck's subject, for seeding a template. */
export function subjectOf(project, slides = []) {
  const titles = (Array.isArray(slides) ? slides : []).slice(0, 4).map((slide) => slide?.title);
  return [project?.initialPrompt, project?.name, project?.description, ...titles].filter(Boolean).join(' ');
}
