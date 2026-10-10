// Browser checks: production unavailable state and explicitly mocked UI fixtures.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');

(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto('http://localhost:3000');
    await page.getByRole('button', { name: /skip/i }).click();
    await page.getByText('No agricultural evaluation has been completed.', { exact: false }).waitFor();
    assert.equal(await page.getByLabel('Mandi, variety and grade').isDisabled(), false);
    await page.getByText('Observations present · evaluation unavailable', { exact: true }).waitFor();
    for (const theme of ['light', 'dark']) {
      await page.evaluate(t => { localStorage.setItem('nexyra_theme', t); }, theme);
      await page.reload();
      await page.getByRole('button', { name: /skip/i }).click();
      await page.getByRole('heading', { name: 'Market explorer' }).waitFor();
      await page.waitForTimeout(700);
      assert.equal(await page.evaluate(() => document.documentElement.classList.contains('dark')), theme === 'dark');
      for (const panel of await page.locator('main section').all()) {
        if (await panel.isVisible()) { await panel.scrollIntoViewIfNeeded(); await page.waitForTimeout(280); }
      }
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.screenshot({ path: `artifacts/agri-${theme}-desktop.png`, fullPage: true });
      const tokens = await page.evaluate(() => ['--bg-primary', '--text-primary', '--accent-brand'].map(k => getComputedStyle(document.documentElement).getPropertyValue(k)));
      await page.goto('http://localhost:3000/legacy');
      await page.getByRole('button', { name: /skip/i }).click();
      const legacyTokens = await page.evaluate(() => ['--bg-primary', '--text-primary', '--accent-brand'].map(k => getComputedStyle(document.documentElement).getPropertyValue(k)));
      assert.deepEqual(tokens, legacyTokens);
      await page.goto('http://localhost:3000');
      await page.getByRole('button', { name: /skip/i }).click();
    }
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({ path: 'artifacts/agri-mobile.png', fullPage: true });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);

    // Explicit synthetic response fixture; no backend data or registry is modified.
    const metrics = { n: 21, mae: 10, rmse: 12, smape: 1, directional_accuracy: .5, interval_coverage: .9, interval_width: 30 };
    const horizons = Object.fromEntries([1, 3, 7].map(h => [h, {
      selected_model: 'naive', baseline: 'naive', selection_reason: 'Fixture: baseline retained',
      training_period: { origin_start: '2022-01-01', target_end: '2022-06-01' },
      validation_period: { origin_start: '2022-04-01', origin_end: '2022-05-01' },
      test_period: { origin_start: '2022-06-02', target_end: '2022-07-01' },
      interval_method: 'Fixture', comparison: [{ id: 'naive', family: 'baseline', status: 'evaluated', validation: metrics, test: metrics, stability_mae_std: 1 }, { id: 'C', family: 'C', status: 'unavailable', reason: 'Fixture: semantic data unavailable' }]
    }]));
    await page.route('**/api/agri/**', route => {
      const url = new URL(route.request().url());
      let body;
      if (url.pathname.endsWith('/models')) body = { status: 'research_only', markets: [{ series_id: 'fixture', market: 'UI test only', variety: 'Fixture', grade: 'Test', source: 'explicit-ui-fixture', district: 'Fixture', version: 'fixture', horizons }] };
      else if (url.pathname.endsWith('/series')) body = { status: 'unavailable', series: [] };
      else if (url.pathname.includes('/forecast/')) body = { status: 'research_only', prediction: 1000 + Number(url.searchParams.get('horizon')), lower: 990, upper: 1020, origin: '2022-07-01', target_date: '2022-07-08', stale: true, interval_status: 'experimental_temporal_coverage_not_guaranteed', calibration: { nominal_coverage: .9 }, selected_model: 'naive', version: 'fixture' };
      else body = { latest_price: 1000, change: 0, volatility: .01, as_of: '2022-07-01', history: [{ date: '2022-07-01', price: 1000 }], news: [], limitations: [] };
      return route.fulfill({ json: body });
    });
    await page.reload();
    await page.getByRole('button', { name: /skip/i }).click();
    await page.getByText('Selected: naive', { exact: false }).waitFor();
    await page.getByLabel('Forecast horizon').selectOption('7');
    await page.getByText('₹1,007', { exact: true }).waitFor();
    await page.getByText('This forecast target is historical', { exact: false }).waitFor();
    assert.equal(await page.getByRole('table').count(), 1);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.route('**/api/agri/models', route => route.fulfill({ status: 503, json: { detail: 'Fixture unavailable' } }));
    await page.reload();
    await page.getByRole('button', { name: /skip/i }).click();
    await page.getByRole('alert').filter({ hasText: 'Fixture unavailable' }).waitFor();
    assert.deepEqual(errors, []);
    console.log('PASS: observation-only and unavailable statuses, both themes, protected tokens, mobile layout, comparison fixture, horizon selection, stale warning, API failure; no browser exceptions');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });
