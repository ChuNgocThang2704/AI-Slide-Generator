import test from 'node:test';
import assert from 'node:assert/strict';
import { reflowSlideTemplate } from '../src/utils/slideElements.js';
import { ADAPTIVE_TEMPLATES, LAYOUT_VARIANTS } from '../src/utils/templateLayouts.js';

const themes = [...ADAPTIVE_TEMPLATES];
const long = 'Đây là một ý dài hơn bình thường nhằm kiểm tra việc xuống dòng và kích thước khung chữ trong bố cục';
const shapes = {
  short: { title: 'Tiêu đề ngắn', bullets: ['Ý một', 'Ý hai', 'Ý ba'] },
  medium: { title: 'Lịch sử phát triển của ngành cà phê Việt Nam', bullets: ['Mốc năm 1857: nhà truyền giáo mang cây cà phê đến trồng thử nghiệm', 'Cường quốc Robusta số một thế giới nhờ chính sách đổi mới', 'Nhà truyền giáo Pháp đưa hạt giống vào các nhà thờ miền Bắc'] },
  long: { title: 'Những thách thức và cơ hội trong tương lai của ngành cà phê Việt Nam giai đoạn 2025-2030 trên thị trường toàn cầu', bullets: Array.from({ length: 9 }, (_, i) => `${long} ${i + 1}`) },
  one: { title: 'Một ý duy nhất', bullets: ['Chỉ có một câu ngắn gọn làm nội dung chính của slide này.'] },
};
const table = { headers: ['Năm', 'Tổng'], rows: [[2020, 1], [2021, 2], [2022, 3]] };
const chart = { type: 'bar', labels: ['A', 'B', 'C'], series: [{ name: 's', values: [1, 2, 3] }] };
const kinds = {
  text: (s) => ({ type: 'content', ...s }),
  image: (s) => ({ type: 'imageText', ...s, imageUrl: 'a.jpg' }),
  data: (s) => ({ type: 'chart', ...s, chart }),
  table: (s) => ({ type: 'table', ...s, table }),
  cover: (s) => ({ type: 'title', title: s.title, bullets: [s.bullets[0]] }),
  closing: (s) => ({ type: 'thankyou', ...s, bullets: s.bullets.slice(0, 4) }),
};
const variantKind = { text: 'text', image: 'image', data: 'data', table: 'data', cover: 'cover', closing: 'closing' };

const overlaps = (a, b) => Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x) > 2
  && Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y) > 2;

for (const theme of themes) {
  test(`${theme}: every variant of every slide kind stays on canvas without overlaps`, () => {
    for (const [name, make] of Object.entries(kinds)) {
      for (const variant of LAYOUT_VARIANTS[variantKind[name]]) {
        for (const [shape, content] of Object.entries(shapes)) {
          const slide = { id: 's', ...make(content), richText: { _layoutVariant: variant.id } };
          const out = reflowSlideTemplate(slide, theme).elements;
          const where = `${theme}/${name}/${variant.id}/${shape}`;
          for (const el of out) {
            assert.ok(el.x >= 0 && el.y >= 0 && el.width > 0 && el.height > 0, `${where}: ${el.role} invalid box`);
            assert.ok(el.x + el.width <= 960 && el.y + el.height <= 540, `${where}: ${el.role} leaves canvas ${JSON.stringify([el.x, el.y, el.width, el.height])}`);
          }
          for (let i = 0; i < out.length; i += 1) {
            for (let j = i + 1; j < out.length; j += 1) {
              assert.ok(!overlaps(out[i], out[j]), `${where}: ${out[i].role} overlaps ${out[j].role}`);
            }
          }
          if (theme === 'blue-planet') {
            for (const el of out.filter((item) => item.type === 'text')) {
              assert.ok(el.x + el.width <= 745 || el.y + el.height <= 350, `${where}: ${el.role} runs into the planet`);
            }
          }
        }
      }
    }
  });
}

test('content slides default to the traditional layout in every theme', () => {
  for (const theme of themes) {
    const out = reflowSlideTemplate({ id: 's', type: 'content', ...shapes.medium }, theme).elements;
    const title = out.find((el) => el.role === 'title');
    const body = out.find((el) => el.role === 'body');
    assert.ok(title.y < 60 && title.x <= 80, `${theme}: title is not top-left`);
    assert.ok(body.y > title.y + title.height && body.width >= 560, `${theme}: body is not a wide block below the title`);
    assert.equal(out.filter((el) => el.role === 'body').length, 1);
  }
});

test('an explicit variant is honoured and survives a theme switch', () => {
  const first = reflowSlideTemplate({ id: 's', type: 'content', ...shapes.short, richText: { _layoutVariant: 'rail' } }, 'soft-blue');
  const second = reflowSlideTemplate(first, 'nature-green');
  assert.equal(second.elements.find((el) => el.role === 'title').templateLayout, 'rail');
  assert.ok(second.elements.find((el) => el.role === 'title').width < 400);
});

test('cover and closing text stays editable: nothing is forced back on re-layout of saved edits', () => {
  const saved = [
    { id: 't', type: 'text', role: 'title', content: 'X', x: 300, y: 200, width: 300, height: 60, style: { textAlign: 'right', fontSize: 30 } },
    { id: 'b', type: 'text', role: 'body', content: '<ul><li>y</li></ul>', x: 10, y: 10, width: 100, height: 40, style: { fontSize: 18 } },
  ];
  for (const type of ['title', 'thankyou']) {
    assert.equal(reflowSlideTemplate({ id: 's', type, title: 'X', elements: saved }, 'tech-purple').elements.length, 2);
  }
});

test('slides saved with the first generator\'s split layouts return to the classic arrangement on load', async () => {
  const { formatSlidePage } = await import('../src/utils/slideMapping.js');
  const bullets = ['Ý một', 'Ý hai', 'Ý ba'];
  const page = {
    id: 'p', pageIndex: 3, title: 'Tiêu đề', bullets, layout: 'text_only',
    elements: [
      { id: 't', type: 'text', role: 'title', content: 'Tiêu đề', x: 64, y: 40, width: 832, height: 86, templateLayout: 'two-column-points' },
      ...bullets.map((text, index) => ({ id: `b${index}`, type: 'text', role: 'body', layoutGroup: 'b0', layoutOrder: index,
        content: `<ul><li>${text}</li></ul>`, x: 64 + index * 300, y: 150, width: 280, height: 160, templateLayout: 'two-column-points' })),
    ],
  };
  const slide = formatSlidePage(page, { theme: 'soft-blue' });
  const bodies = slide.elements.filter((el) => el.role === 'body');
  assert.equal(bodies.length, 1);
  assert.ok(bodies[0].width >= 800);
  assert.equal(slide.elements[0].templateLayout, 'classic');
  // a custom-template deck (no built-in theme) is left exactly as saved
  assert.equal(formatSlidePage(page, {}).elements.filter((el) => el.role === 'body').length, 3);
});

test('covers and closings saved by the first generator return to the current composition on load', async () => {
  const { formatSlideDeck } = await import('../src/utils/slideMapping.js');
  const legacy = (role, content, box) => ({ id: role, type: 'text', role, content, templateLayout: 'cover', ...box, style: { fontSize: 46 } });
  const pages = [
    { id: 'a', pageIndex: 0, layout: 'title', title: 'Bìa', bullets: ['Phụ đề ngắn'], elements: [legacy('title', 'Bìa', { x: 5, y: 5, width: 300, height: 40 }), legacy('body', 'Phụ đề ngắn', { x: 5, y: 60, width: 300, height: 40 })] },
    { id: 'b', pageIndex: 1, layout: 'text_only', title: 'Giữa', bullets: ['x'] },
    { id: 'c', pageIndex: 2, layout: 'thankyou', title: 'Kết', bullets: ['Ý một', 'Ý hai'], elements: [legacy('title', 'Kết', { x: 1, y: 1, width: 200, height: 30 }), legacy('body', '<ul><li>Ý một</li><li>Ý hai</li></ul>', { x: 1, y: 40, width: 200, height: 60 })] },
  ];
  const deck = formatSlideDeck(pages, '', 'soft-blue');
  for (const index of [0, 2]) {
    const title = deck[index].elements.find((el) => el.role === 'title');
    assert.ok(/^(cover|closing)-/.test(title.templateLayout), `slide ${index} was not migrated`);
    assert.ok(title.width > 300);
  }
  // an edited (non-legacy) cover is left untouched
  const edited = [{ ...pages[0], elements: pages[0].elements.map((el) => ({ ...el, templateLayout: 'cover-center' })) }, pages[1]];
  assert.equal(formatSlideDeck(edited, '', 'soft-blue')[0].elements[0].width, 300);
});

test('choosing a layout clears stale paragraph alignment', () => {
  const elements = [
    { id: 't', type: 'text', role: 'title', content: '<p style="text-align: right;">Tiêu đề</p>', x: 0, y: 0, width: 1, height: 1 },
    { id: 'b', type: 'text', role: 'body', content: '<ul><li><p style="text-align: center;">Ý</p></li></ul>', x: 0, y: 0, width: 1, height: 1 },
  ];
  const out = reflowSlideTemplate({ id: 's', type: 'title', title: 'Tiêu đề', elements }, 'soft-blue').elements;
  assert.ok(out.every((el) => !/text-align/.test(el.content)));
});
