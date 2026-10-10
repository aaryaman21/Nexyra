// UI fixtures are intercepted explicitly; no production models/data are created.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');

(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    const exceptions = [];
    page.on('pageerror', e => exceptions.push(e.message));
    await page.goto('http://localhost:3000');
    await page.getByRole('button', { name: /skip/i }).click();
    await page.getByRole('heading', { name: 'Add market data' }).waitFor();
    assert.equal(await page.getByRole('button', { name: 'Validate & preview' }).isDisabled(), true);
    const templateDownload = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Download CSV template' }).click();
    assert.equal((await templateDownload).suggestedFilename(), 'nexyra-price-template.csv');
    const button = page.getByRole('button', { name: 'Download CSV template' });
    await button.hover();
    await page.waitForTimeout(250);
    assert.notEqual(await button.evaluate(el => getComputedStyle(el).transform), 'none');
    await page.getByText('What do I put in the file?', { exact: true }).click();
    await page.getByText('Use actual historical wholesale observations,', { exact: false }).waitFor();
    // Exercise the actual same-origin proxy and backend validation first.
    await page.getByLabel('Price history CSV', { exact: true }).setInputFiles({ name: 'invalid.csv', mimeType: 'text/csv', buffer: Buffer.from('bad,input\n1,2') });
    await page.getByRole('button', { name: 'Validate & preview' }).click();
    await page.getByRole('alert').filter({ hasText: 'Missing price columns' }).waitFor();

    const id = 'a'.repeat(20);
    let checked = false, evaluated = false;
    await page.route('**/api/agri/workspace/**', async route => {
      const url = new URL(route.request().url());
      const payload = route.request().method() === 'POST' ? route.request().postDataJSON() : null;
      if (url.pathname.endsWith('/datasets')) return route.fulfill({ status: 201, json: { dataset_id: 'b'.repeat(32), series: [{ series_id: id, market: 'UI fixture only', variety: 'Fixture', grade: 'Test', unit: 'INR/quintal', source: 'explicit-ui-fixture', availability_basis: { verified_source_timestamp: 300 }, rows: 300, start: '2022-01-01', end: '2022-10-27', missing_days: 0, coverage: 1, validation_start: '2022-06-01', test_start: '2022-08-29', semantic_archive: false, history: [{ date: '2022-01-01', price: 1000 }, { date: '2022-01-02', price: 1010 }] }] } });
      if (url.pathname.endsWith('/check')) {
        checked = true; assert.equal(payload.series_id, id);
        return route.fulfill({ json: { ready: true, message: 'Fixture: ready for evaluation', horizons: [1, 3, 7].map(h => ({ horizon: h, training: 90, validation: 63, test: 40, semantic_ready: false })) } });
      }
      if (url.pathname.endsWith('/evaluate')) { evaluated = true; return route.fulfill({ status: 202, json: { job_id: 'c'.repeat(32), status: 'queued' } }); }
      return route.fulfill({ json: { job_id: 'c'.repeat(32), status: 'completed', message: 'UI fixture completion only' } });
    });
    await page.getByLabel('Price history CSV', { exact: true }).setInputFiles({ name: 'ui-fixture.csv', mimeType: 'text/csv', buffer: Buffer.from('explicit mocked UI fixture') });
    await page.getByRole('button', { name: 'Validate & preview' }).click();
    await page.getByText('300 observations', { exact: false }).waitFor();
    assert.equal(await page.getByRole('button', { name: 'Run research evaluation', exact: true }).isDisabled(), true);
    await page.getByRole('button', { name: 'Check readiness', exact: true }).click();
    await page.getByText('Fixture: ready for evaluation').waitFor();
    assert.equal(checked, true);
    await page.getByLabel('Validation starts', { exact: true }).fill('2022-06-02');
    assert.equal(await page.getByRole('button', { name: 'Run research evaluation', exact: true }).isDisabled(), true);
    await page.getByRole('button', { name: 'Check readiness', exact: true }).click();
    await page.getByText('Fixture: ready for evaluation').waitFor();
    await page.getByRole('button', { name: 'Run research evaluation', exact: true }).click();
    await page.getByText('Research evaluation completed', { exact: true }).waitFor();
    assert.equal(evaluated, true);
    await page.setViewportSize({ width: 390, height: 844 });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await button.hover();
    await page.waitForTimeout(250);
    const devPreview = await page.evaluate(() => document.documentElement.dataset.motionPreview === 'true');
    const transform = await button.evaluate(el => getComputedStyle(el).transform);
    if (devPreview) assert.notEqual(transform, 'none');
    else assert.equal(transform, 'none');
    assert.deepEqual(exceptions, []);
    console.log('PASS: real proxy/invalid upload, template download, hover, input help, preview, readiness gating, edited-date invalidation, evaluation polling, mobile and reduced motion (successful workflow uses explicit mocks)');
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exit(1); });
