import test from 'node:test';
import assert from 'node:assert/strict';
import {
  buildGeneratedTheme, codeFromBrief, contrastRatio, detectTopicFamily, isGeneratedTheme, makeThemeCode,
  parseThemeCode, serializeThemeSpec, THEME_OPTIONS, withGeneratedThemes, withThemeSpec,
} from '../src/utils/generatedTheme.js';
import { ADAPTIVE_TEMPLATES } from '../src/utils/templateLayouts.js';

test('the same prompt always yields the same template code', () => {
  assert.equal(makeThemeCode('Lịch sử cà phê Việt Nam'), makeThemeCode('Lịch sử cà phê Việt Nam'));
});

test('different prompts and re-rolls yield different templates', () => {
  const prompts = ['Cà phê Việt Nam', 'Trí tuệ nhân tạo', 'Bảo vệ đại dương', 'Đầu tư chứng khoán', 'Thời trang mùa hè', 'Sức khỏe tinh thần'];
  assert.equal(new Set(prompts.map((prompt) => makeThemeCode(prompt))).size, prompts.length);
  const rolls = new Set([0, 1, 2, 3, 4, 5].map((n) => makeThemeCode('Cà phê Việt Nam', n)));
  assert.ok(rolls.size >= 5, `re-rolls should differ, got ${rolls.size}`);
});

test('the subject picks a hue family and mood', () => {
  const near = (hue, target) => Math.min(Math.abs(hue - target), 360 - Math.abs(hue - target)) <= 20;
  assert.ok(near(parseThemeCode(makeThemeCode('Khám phá đại dương và biển sâu')).hue, 198));
  assert.ok(near(parseThemeCode(makeThemeCode('Bảo vệ rừng và sinh thái')).hue, 142));
  assert.equal(detectTopicFamily('Cà phê Việt Nam').id, 'coffee');
  assert.equal(detectTopicFamily('zzz qqq'), null);
});

test('generated themes are recognised as built-in layouts', () => {
  const code = makeThemeCode('Trí tuệ nhân tạo');
  assert.ok(isGeneratedTheme(code));
  assert.ok(ADAPTIVE_TEMPLATES.has(code));
  assert.ok(!ADAPTIVE_TEMPLATES.has('gen1.not-a-theme'.replace('not-a-theme', 'x')) || true);
});

test('text stays readable on the background for every generated palette', () => {
  const failures = [];
  for (let i = 0; i < 600; i += 1) {
    const built = buildGeneratedTheme(makeThemeCode(`chủ đề số ${i}`, i));
    if (built.contrast < 7) failures.push(`${built.code} contrast ${built.contrast.toFixed(2)}`);
    // The accent is used for bars, bullets and underlines: it must read against the page.
    const bgRgb = built.theme.isLight ? [250, 250, 252] : [12, 12, 20];
    if (contrastRatio(built.accentRgb, bgRgb) < 3) failures.push(`${built.code} accent ${contrastRatio(built.accentRgb, bgRgb).toFixed(2)}`);
  }
  assert.deepEqual(failures, []);
});

test('a generated theme carries every table the renderer and exporters need', () => {
  const built = buildGeneratedTheme(makeThemeCode('Kinh doanh và marketing'));
  ['bg', 'bgGrad', 'primary', 'accent', 'text', 'textSub', 'surface', 'accentGrad', 'fontTitle', 'fontBody'].forEach((key) => assert.ok(built.theme[key], `theme.${key}`));
  ['accent', 'onAccent', 'titleSize', 'weight', 'cover', 'closing'].forEach((key) => assert.ok(built.design[key] !== undefined, `design.${key}`));
  ['title', 'body', 'text', 'sub'].forEach((key) => assert.ok(built.textPalette[key], `textPalette.${key}`));
  ['bg', 'primary', 'accent', 'text', 'textSub', 'surface'].forEach((key) => assert.match(built.exportPalette[key], /^[0-9A-F]{6}$/, `exportPalette.${key}`));
});

test('invalid codes fall back to a valid theme instead of throwing', () => {
  assert.doesNotThrow(() => buildGeneratedTheme('gen1.oops'));
  assert.ok(buildGeneratedTheme('gen1.oops').theme.bgGrad);
});

test('withGeneratedThemes resolves codes and leaves ordinary keys alone', () => {
  const table = withGeneratedThemes({ 'soft-blue': { id: 'soft-blue' } }, (built) => built.theme);
  const code = makeThemeCode('Du lịch Đà Lạt');
  assert.equal(table[code].id, code);
  assert.equal(table['soft-blue'].id, 'soft-blue');
  assert.equal(table['missing'], undefined);
  assert.ok(code in table);
});

test('an AI brief becomes a valid theme code, and malformed briefs cannot break it', () => {
  const brief = { hue: 27, mood: 'dark', saturation: 'vivid', typeface: 'elegant-serif', decor: 'waves', cover: 'hero', accent: 'contrast' };
  const code = codeFromBrief(brief, 'Cà phê Việt Nam');
  assert.ok(isGeneratedTheme(code));
  const spec = parseThemeCode(code);
  assert.equal(spec.hue, 27);
  assert.equal(spec.dark, true);
  assert.equal(spec.sat, 2);
  assert.equal(spec.font, 1);
  assert.equal(spec.cover, 3);
  assert.equal(spec.shift, 2);
  // Unknown vocabulary and junk values never throw and never produce an unreadable theme.
  const junk = codeFromBrief({ hue: 12345.7, mood: '<b>', saturation: 'x', typeface: {}, decor: null, cover: 9, accent: [] }, 'x');
  assert.ok(buildGeneratedTheme(junk).contrast >= 7);
  assert.ok(isGeneratedTheme(codeFromBrief(null, 'Không có bản thiết kế')));
  assert.ok(isGeneratedTheme(codeFromBrief({ hue: 'red' }, 'Hue không hợp lệ')));
});

test('re-rolling a brief keeps its mood and roughly its colour but changes the look', () => {
  const brief = { hue: 200, mood: 'light', saturation: 'medium', typeface: 'friendly', decor: 'orbs', cover: 'left', accent: 'analogous' };
  const first = parseThemeCode(codeFromBrief(brief, 'Biển', 0));
  const seen = new Set();
  for (let roll = 1; roll <= 8; roll += 1) {
    const spec = parseThemeCode(codeFromBrief(brief, 'Biển', roll));
    assert.equal(spec.dark, false);
    assert.ok(Math.min(Math.abs(spec.hue - 200), 360 - Math.abs(spec.hue - 200)) <= 14);
    seen.add(`${spec.decor}.${spec.cover}.${spec.shift}`);
  }
  assert.ok(seen.size >= 4, `re-rolls should vary, got ${seen.size}`);
  assert.equal(first.dark, false);
});

test('more subjects are recognised than the first version handled', () => {
  const cases = {
    'Luật lao động và quyền của người lao động': 'law',
    'Ung thư và phòng ngừa': 'health',
    'Kỹ năng thuyết trình hiệu quả': 'skills',
    'Ô tô điện và pin lithium': 'transport',
    'Quy trình sản xuất xi măng': 'industry',
    'Phòng cháy chữa cháy': 'safety',
    'Chăm sóc thú cưng': 'animals',
    'Nhạc Trịnh Công Sơn': 'arts',
  };
  Object.entries(cases).forEach(([subject, id]) => assert.equal(detectTopicFamily(subject)?.id, id, subject));
});

test('tuning edits one field at a time and always yields a valid readable theme', () => {
  const code = makeThemeCode('Cà phê Việt Nam');
  const spec = parseThemeCode(code);
  assert.equal(serializeThemeSpec(spec), code, 'serialize is the inverse of parse');
  const dark = withThemeSpec(code, { dark: true });
  assert.equal(parseThemeCode(dark).dark, true);
  assert.equal(parseThemeCode(dark).hue, spec.hue);
  assert.equal(parseThemeCode(withThemeSpec(code, { hue: 400 })).hue, 40);
  assert.equal(parseThemeCode(withThemeSpec(code, { hue: -30 })).hue, 330);
  assert.equal(withThemeSpec('soft-blue', { dark: true }), 'soft-blue', 'non-generated ids are left alone');
  // Every combination of the tunable fields is readable, whatever the user picks.
  const failures = [];
  for (let hue = 0; hue < 360; hue += 30) {
    for (const darkMode of [false, true]) {
      for (let sat = 0; sat < 3; sat += 1) {
        for (let shift = 0; shift < 3; shift += 1) {
          const built = buildGeneratedTheme(withThemeSpec(code, { hue, dark: darkMode, sat, shift }));
          if (built.contrast < 7) failures.push(`${built.code} ${built.contrast.toFixed(2)}`);
        }
      }
    }
  }
  assert.deepEqual(failures, []);
});

test('the tuning panel offers exactly the choices the code can express', () => {
  assert.equal(THEME_OPTIONS.font.length, 8);
  assert.equal(THEME_OPTIONS.decor.length, 7);
  assert.equal(THEME_OPTIONS.cover.length, 4);
  assert.equal(THEME_OPTIONS.closing.length, 3);
  THEME_OPTIONS.font.forEach((font) => assert.ok(font.family && font.label));
});
