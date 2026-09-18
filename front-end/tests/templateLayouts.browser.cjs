const assert = require('node:assert/strict');
const path = require('node:path');
const os = require('node:os');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

async function main() {
  const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || 'msedge', headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1100, height: 900 } });
    const errors = [];
    page.on('pageerror', (error) => errors.push(error.message));
    const origin = process.env.LAYOUT_TEST_ORIGIN || 'http://127.0.0.1:5173';
    await page.goto(`${origin}/tests/template-layouts.html`);
    await page.waitForSelector('.element-canvas');
    assert.ok((await page.evaluate(() => window.layoutChecks)).every((check) => check.passed));
    for (const width of process.env.LAYOUT_TEST_EDITOR_ONLY ? [] : [1100, 390]) {
      await page.setViewportSize({ width, height: 900 });
      for (const theme of ['soft-blue', 'clean-white', 'blue-planet', 'royal-purple', 'modern-dark', 'playful-yellow', 'gradient-border', 'nature-green', 'tech-purple']) {
        await page.getByLabel('Theme').selectOption(theme);
        await page.waitForFunction((expected) => document.querySelector('main')?.dataset.theme === expected, theme);
        await page.evaluate(() => document.fonts.ready);
        await page.waitForFunction(() => [...document.images].every((img) => img.complete && img.naturalWidth > 0));
        await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
        const result = await page.evaluate(() => ({
          rows: document.querySelectorAll('section')[5].querySelectorAll('tbody tr').length,
          overflow: [...document.querySelectorAll('.canvas-text')].filter((el) => el.scrollHeight > el.clientHeight + 2).length,
          overflowingText: [...document.querySelectorAll('.canvas-text')].filter((el) => el.scrollHeight > el.clientHeight + 2).map((el) => ({ text: el.textContent.slice(0, 60), height: el.clientHeight, scroll: el.scrollHeight, font: getComputedStyle(el).fontSize })),
          closingFont: Number.parseFloat(getComputedStyle(document.querySelector('section:last-child .role-body .canvas-text')).fontSize),
          width: document.documentElement.scrollWidth,
        }));
        console.log(theme, width, result);
        assert.equal(result.rows, 12);
        assert.equal(result.overflow, 0);
        assert.equal(result.closingFont, 24, `Closing text was auto-fitted down to ${result.closingFont}px`);
        assert.ok(result.width <= width);
        await page.screenshot({ path: path.join(os.tmpdir(), `genslide-${theme}-${width}.png`), fullPage: true });
      }
    }
    assert.deepEqual(errors, []);
    await page.close();

    // Exercise the real editor with an isolated, in-memory API. No user data is written.
    const editor = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    const project = { id: 'layout-regression', name: 'Layout regression', title: 'Layout regression', status: 1, templateId: 'soft-blue' };
    const customTemplate = { id: 'd0944157-2af1-438d-a01e-0aeae9d82d77', name: 'Custom regression', sourceType: 'CUSTOM_PPTX' };
    const matchRequests = [];
    const deletedTemplates = [];
    let pages = [{ id: 'page-1', projectId: project.id, pageIndex: 0, title: 'Learning objectives', layout: 'text_only', bullets: ['Understand the concept', 'Apply the tools', 'Review the results', 'Discuss the outcome'], elements: [] }];
    await editor.addInitScript(() => localStorage.setItem('auth-storage', JSON.stringify({ state: { isAuthenticated: true, token: 'test-token', user: { id: 'test-user', name: 'Test' } }, version: 0 })));
    await editor.route('**/api/**', async (route) => {
      const url = new URL(route.request().url());
      const endpoint = url.pathname;
      let data = [];
      if (endpoint.endsWith('/template/get-all')) data = { items: [customTemplate] };
      else if (endpoint.endsWith('/template/custom')) data = customTemplate;
      else if (route.request().method() === 'DELETE' && endpoint.endsWith(`/template/custom/${customTemplate.id}`)) {
        deletedTemplates.push(customTemplate.id);
        data = null;
      }
      else if (endpoint.endsWith('/match')) {
        const content = route.request().postDataJSON();
        matchRequests.push(content);
        data = {
          layoutId: 'custom-layout',
          layoutType: 'title',
          primaryColor: '#7C3AED',
          headingFont: 'Arial',
          bodyFont: 'Arial',
          titleStyle: { fontFamily: 'Arial', fontSize: 48, color: '#172554', textAlign: 'center' },
          bodyStyle: { fontFamily: 'Arial', fontSize: 24, color: '#334155' },
          elements: [
          { id: 'template-background', type: 'shape', role: 'background', fill: '#FFFFFF', locked: true, x: 0, y: 0, width: 960, height: 540 },
          { id: 'template-title', type: 'text', role: 'title', content: content.title, x: 100, y: 50, width: 750, height: 110, style: { fontFamily: 'Arial', fontSize: 48 } },
          ...content.bullets.map((bullet, index) => ({ id: `template-body-${index}`, type: 'text', role: 'body', content: `<p>${bullet}</p>`, x: 100, y: 180 + index * 55, width: 700, height: 50, style: { fontFamily: 'Arial', fontSize: 24 } })),
          { id: 'template-image', type: 'image', role: 'image', x: 600, y: 350, width: 200, height: 150 },
        ] };
      } else if (endpoint.endsWith('/pages/sync')) {
        pages = route.request().postDataJSON().map((item, index) => ({ ...item, pageIndex: index }));
        data = pages;
      } else if (endpoint.endsWith('/pages')) data = pages;
      else if (endpoint.endsWith(`/projects/${project.id}`)) {
        if (route.request().method() === 'POST') Object.assign(project, route.request().postDataJSON());
        data = project;
      } else if (endpoint.endsWith('/progress')) data = { status: 'COMPLETED', progress: 100 };
      await route.fulfill({ json: { code: 200, data } });
    });
    await editor.goto(`${origin}/editor/${project.id}`);
    await editor.getByRole('button', { name: 'Template', exact: true }).click();
    await editor.locator('.e2-tmpl-card').filter({ hasText: 'Clean White' }).click();
    await editor.waitForFunction(() => JSON.parse(localStorage.getItem('projects-storage')).state.projects[0].templateId === 'clean-white');
    await editor.getByRole('button', { name: 'Hoàn tác', exact: true }).click();
    await editor.waitForFunction(() => JSON.parse(localStorage.getItem('projects-storage')).state.projects[0].templateId === 'soft-blue');
    await editor.getByRole('button', { name: 'Làm lại', exact: true }).click();
    await editor.waitForFunction(() => JSON.parse(localStorage.getItem('projects-storage')).state.projects[0].templateId === 'clean-white');
    const saved = editor.waitForResponse((response) => response.url().endsWith('/pages/sync') && response.status() === 200);
    await editor.getByRole('button', { name: 'Lưu thay đổi', exact: true }).click();
    await saved;
    assert.equal(pages[0].elements.find((el) => el.role === 'title').x, 64);
    assert.equal(pages[0].elements.find((el) => el.role === 'body').x, 372);
    await editor.reload();
    await editor.waitForSelector('.element-canvas');
    await editor.screenshot({ path: path.join(os.tmpdir(), 'genslide-editor-layout.png'), fullPage: true });
    console.log('Editor: template switch, undo, redo, save and reload passed');
    const canvas = editor.locator('.element-canvas:not(.readonly)');
    const title = canvas.locator('.role-title .canvas-text');
    await title.dblclick();
    if (!await title.evaluate((el) => el.isContentEditable)) await title.dblclick();
    await title.fill('Latest canvas title');
    await editor.getByRole('button', { name: 'Template', exact: true }).click();
    const body = canvas.locator('.role-body .canvas-text').first();
    await body.dblclick();
    if (!await body.evaluate((el) => el.isContentEditable)) await body.dblclick();
    await body.fill('Latest canvas bullet');
    await editor.getByRole('tab', { name: 'Tùy chỉnh', exact: true }).click();
    await editor.locator('.e2-template-panel input[type=file]').first().setInputFiles({ name: 'regression.pptx', mimeType: 'application/vnd.openxmlformats-officedocument.presentationml.presentation', buffer: Buffer.from('Mock upload; parser is outside this FE test') });
    await editor.waitForFunction((expected) => document.querySelector('.element-canvas:not(.readonly)')?.dataset.theme === expected, customTemplate.id);
    assert.equal(matchRequests.at(-1).title, 'Latest canvas title');
    assert.deepEqual(matchRequests.at(-1).bullets, ['Latest canvas bullet']);
    assert.equal(matchRequests.at(-1).layout, 'text_only');
    assert.equal(await canvas.locator('.role-background').count(), 0);
    assert.equal(await canvas.locator('.role-image').count(), 0);
    assert.match(await canvas.locator('.role-title .canvas-text').evaluate((element) => element.style.fontFamily), /Arial/i);
    assert.equal(await canvas.locator('.role-title').evaluate((element) => Number.parseFloat(element.style.left)), 64);
    await editor.getByRole('tab', { name: 'Mặc định', exact: true }).click();
    await editor.locator('.e2-tmpl-card').filter({ hasText: 'Soft Blue' }).click();
    await editor.waitForFunction(() => document.querySelector('.element-canvas:not(.readonly)')?.dataset.theme === 'soft-blue');
    assert.equal(await canvas.locator('.role-background').count(), 0);
    assert.equal(await canvas.locator('.role-image').count(), 0);
    assert.equal(await canvas.locator('.role-title .canvas-text').textContent(), 'Latest canvas title');
    const roundTripSaved = editor.waitForResponse((response) => response.url().endsWith('/pages/sync') && response.status() === 200);
    await editor.getByRole('button', { name: 'Lưu thay đổi', exact: true }).click();
    await roundTripSaved;
    assert.equal(pages[0].layout, 'text_only');
    assert.equal(pages[0].elements.find((el) => el.role === 'title').style.fontSize, 34);
    assert.deepEqual(pages[0].bullets, ['Latest canvas bullet']);
    await editor.reload();
    await editor.waitForSelector('.element-canvas:not(.readonly) .role-title');
    assert.equal(await editor.locator('.element-canvas:not(.readonly) .role-title .canvas-text').textContent(), 'Latest canvas title');
    console.log('Editor: live edits, custom upload/match, built-in restoration and reload passed');

    await editor.getByRole('button', { name: 'Template', exact: true }).click();
    await editor.getByRole('tab', { name: 'Tùy chỉnh', exact: true }).click();
    editor.once('dialog', (dialog) => dialog.accept());
    await editor.getByRole('button', { name: `Xóa template ${customTemplate.name}` }).click();
    await editor.waitForFunction((templateId) => !document.querySelector(`[aria-label="Xóa template Custom regression"]`), customTemplate.id);
    assert.deepEqual(deletedTemplates, [customTemplate.id]);
    assert.equal(await editor.getByRole('button', { name: /Xóa template Soft Blue/ }).count(), 0);
    console.log('Editor: owned custom template deletion passed');
    await editor.close();
  } finally {
    await browser.close();
  }
}
main().catch((error) => { console.error(error); process.exitCode = 1; });
