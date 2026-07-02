// 文件路径：frontend/screenshot.mjs
// 文件作用：用 Playwright 自动截图验证 ScreenSight 各页面 UI
// 最后更新时间：2026-07-02-1209
import { chromium } from 'playwright';
import { fileURLToPath } from 'url';
import path from 'path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.join(__dirname, 'screenshots');

import fs from 'fs';
fs.mkdirSync(outDir, { recursive: true });

const URL = process.env.SS_URL || 'http://127.0.0.1:8765/';

const shots = [
  { name: '01-timeline', menuIdx: 0 },
  { name: '02-reports', menuIdx: 1 },
  { name: '03-search', menuIdx: 2 },
  { name: '04-settings', menuIdx: 3 },
];

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

console.log('访问', URL);
await page.goto(URL, { waitUntil: 'networkidle', timeout: 30000 });
await page.waitForTimeout(2000);

// 逐页截图
for (const s of shots) {
  try {
    const items = await page.$$('.ant-menu-item');
    if (items[s.menuIdx]) {
      await items[s.menuIdx].click();
      await page.waitForTimeout(1500);
    }
    const p = path.join(outDir, `${s.name}.png`);
    await page.screenshot({ path: p, fullPage: false });
    console.log('截图:', s.name, '->', p);
  } catch (e) {
    console.log('截图失败', s.name, ':', e.message);
  }
}

// 报告详情弹窗
try {
  const items = await page.$$('.ant-menu-item');
  if (items[1]) { await items[1].click(); await page.waitForTimeout(1200); }
  const viewBtn = await page.$('.ant-table-tbody .ant-btn:first-child');
  if (viewBtn) {
    await viewBtn.click();
    await page.waitForTimeout(3000);
    const p = path.join(outDir, '05-report-detail.png');
    await page.screenshot({ path: p });
    console.log('截图: 05-report-detail ->', p);
    // 关闭弹窗
    const closeBtn = await page.$('.ant-modal-close');
    if (closeBtn) { await closeBtn.click(); await page.waitForTimeout(500); }
  }
} catch (e) { console.log('报告详情截图失败:', e.message); }

// 搜索页 RAG 标签
try {
  const items = await page.$$('.ant-menu-item');
  if (items[2]) { await items[2].click(); await page.waitForTimeout(1200); }
  const ragTab = await page.$('.ant-tabs-tab:nth-child(2)');
  if (ragTab) { await ragTab.click(); await page.waitForTimeout(1000); }
  const p = path.join(outDir, '06-search-rag.png');
  await page.screenshot({ path: p });
  console.log('截图: 06-search-rag ->', p);
} catch (e) { console.log('RAG截图失败:', e.message); }

await browser.close();
console.log('全部截图完成, 输出目录:', outDir);
