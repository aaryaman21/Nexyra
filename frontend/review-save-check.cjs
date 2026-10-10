// Real Edge form interaction and API persistence against an isolated SQLite DB.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

(async () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'nexyra-review-browser-'));
  const projectRoot = path.resolve(__dirname, '..');
  let fixtureServer;
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    let queueCalls = 0;
    const liveQueue = await (await page.request.get('http://127.0.0.1:3000/api/agri/review/queue?limit=200')).json();
    const productionReviewCount = liveQueue.dataset_health.human_reviewed_articles;
    const savedArticle = liveQueue.events.find(row => row.prid === '1684194');
    assert.ok(savedArticle, 'real PRID 1684194 must be in the queue');
    // Reuse genuine source text but start the isolated test DB with no human
    // annotations so the browser can exercise a first review safely.
    const article = { ...savedArticle, review_status: 'pending', review_history: [] };
    fs.writeFileSync(path.join(tempDir, 'article.json'), JSON.stringify(article), 'utf8');
    const port = 18000 + Math.floor(Math.random() * 1000);
    fixtureServer = spawn(path.join(projectRoot, 'venv', 'Scripts', 'python.exe'), [
      'backend/tests/review_api_fixture_server.py', '--port', String(port),
      '--database', path.join(tempDir, 'reviews.sqlite'), '--fixture', path.join(tempDir, 'article.json')
    ], { cwd: projectRoot, stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true });
    let fixtureOutput = '';
    fixtureServer.stdout.on('data', data => { fixtureOutput += data.toString(); });
    fixtureServer.stderr.on('data', data => { fixtureOutput += data.toString(); });
    const apiRoot = `http://127.0.0.1:${port}`;
    let ready = false;
    for (let attempt = 0; attempt < 60 && !ready; attempt += 1) {
      try {
        const response = await fetch(`${apiRoot}/api/agri/review/queue`);
        ready = response.ok;
      } catch { await new Promise(resolve => setTimeout(resolve, 250)); }
    }
    assert.ok(ready, `isolated review API fixture server should start: ${fixtureOutput}`);
    await page.route('**/api/agri/review/**', async route => {
      if (route.request().url().includes('/queue')) queueCalls += 1;
      const url = route.request().url().replace('http://127.0.0.1:3000', apiRoot);
      await route.fetch({ url }).then(response => route.fulfill({ response }));
    });

    await page.goto('http://127.0.0.1:3000/');
    const skipIntro = page.getByRole('button', { name: /skip/i });
    if (await skipIntro.count()) await skipIntro.click();
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.getByRole('button', { name: /Article review/ }).click();
    await page.waitForFunction(() => document.getElementById('agri-dashboard')?.classList.contains('nexyra-dashboard-shatter'));
    await page.locator('.review-glass-shard').first().waitFor();
    await page.waitForURL('**/review', { timeout: 5000 });
    assert.ok(await page.locator('.review-glass-shard').count() > 0,
      'glass shards should remain over the new route while it is revealed');
    const shardOpacity = await page.locator('.review-glass-shard').first().evaluate(node => Number.parseFloat(getComputedStyle(node).opacity));
    assert.ok(shardOpacity > 0, 'glass fragments should be visibly animated even with OS reduced motion enabled');
    await page.getByRole('button', { name: /Prohibition removed from Onion Export/ }).click();
    await page.getByLabel('Your reviewer identifier').fill('reviewer_01');
    await page.getByLabel('Article relevance').selectOption('relevant');
    await page.getByLabel('Commodity relevance').selectOption('onion_direct');
    await page.getByLabel('Geographic relevance').selectOption('India-wide');
    await page.getByLabel('Publication date extraction').selectOption('correct');
    await page.getByRole('button', { name: 'Approved', exact: true }).click();
    assert.equal(await page.locator('label').filter({ hasText: 'Exact supporting passage' }).count(), 1,
      'headline-only prediction evidence should be excluded from the body-backed review draft');
    const exactQuote = 'Central Government removes prohibition for the export of all varieties of Onions with effect from 01.01.2021';
    const evidence = page.getByLabel('Exact supporting passage');
    assert.equal(await evidence.inputValue(), exactQuote);
    await page.getByRole('button', { name: 'Add date mention' }).click();
    await page.getByLabel('Source-supported date').fill('2021-01-01');
    await page.getByLabel('Date role').fill('Effective date');
    await page.getByLabel('Reviewer notes').fill('the automatic date extraction missed the effective date of 1 January 2021');
    const save = page.getByRole('button', { name: 'Save explicit human review' });
    assert.equal(await save.isEnabled(), true);
    await save.click();
    await page.getByRole('status').filter({ hasText: 'Review saved at' }).waitFor();
    await page.getByText('Completed reviews (1)', { exact: true }).click();
    await page.getByText('Completed · read-only', { exact: true }).waitFor();
    assert.equal(await page.getByRole('button', { name: 'Save explicit human review' }).count(), 0,
      'persisted article must leave the active review form');
    await page.getByText(/reviewer_01/).first().waitFor();
    const isolatedQueue = await (await fetch(`${apiRoot}/api/agri/review/queue`)).json();
    const saved = isolatedQueue.events[0].review_history[0];
    assert.equal(saved.payload.events[0].evidence[0].quote, exactQuote);
    assert.equal(saved.payload.events[0].dates[0].date, '2021-01-01');
    assert.equal(saved.payload.classification_decisions[0].decision, 'approved');
    assert.ok(queueCalls >= 2, 'queue should reload after successful save');
    assert.deepEqual(errors, []);
    const productionQueue = await (await page.request.get('http://127.0.0.1:3000/api/agri/review/queue?limit=200')).json();
    assert.equal(productionQueue.dataset_health.human_reviewed_articles, productionReviewCount, 'production database must remain unchanged');
    console.log(`PASS: Edge saved genuine PRID 1684194 form into isolated SQLite; body evidence, effective date, queue status, and history verified. Production review count unchanged at ${productionReviewCount}.`);
  } finally {
    await browser.close();
    if (fixtureServer && fixtureServer.exitCode === null) {
      fixtureServer.kill();
      await new Promise(resolve => fixtureServer.once('exit', resolve));
    }
    for (let attempt = 0; attempt < 10; attempt += 1) {
      try { fs.rmSync(tempDir, { recursive: true, force: true }); break; }
      catch (error) { if (attempt === 9) throw error; await new Promise(resolve => setTimeout(resolve, 100)); }
    }
  }
})().catch(error => { console.error(error); process.exit(1); });
