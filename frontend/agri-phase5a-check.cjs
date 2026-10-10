// Real-data browser smoke check. No route interception or screenshots.
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
    await page.getByRole('heading', { name: 'Market explorer' }).waitFor();
    const select = page.getByLabel('Mandi, variety and grade');
    const option = await select.locator('option').evaluateAll(options => {
      const match = options.find(item => item.textContent.includes('Lasalgaon (Niphad) / Other / FAQ'));
      return match ? { value: match.value, text: match.textContent } : null;
    });
    assert.ok(option, 'Exact FAQ historical series is listed');
    assert.match(option.text, /Kaggle/);
    await select.selectOption(option.value);
    await page.getByRole('heading', { name: 'Historical research replay' }).waitFor();
    assert.equal(await page.getByLabel('Historical replay origin').inputValue(), '2024-11-20');
    assert.equal(await page.getByText(/stale for a current market forecast/).count(), 1);

    const checks = [
      { horizon: '1', target: '2024-11-21', actual: '4,800', error: '800' },
      { horizon: '3', target: '2024-11-23', actual: '5,100', error: '500' },
      { horizon: '7', target: '2024-11-27', actual: '5,261', error: '339' },
    ];
    for (const item of checks) {
      await page.getByLabel('Forecast horizon').selectOption(item.horizon);
      await page.getByRole('button', { name: `Run ${item.horizon}-day replay` }).click();
      await page.getByText(new RegExp(`historical forecast: origin 2024-11-20, target ${item.target}`)).waitFor();
      await page.getByText(new RegExp(`Recorded outcome:.*${item.actual}.*forecast error.*${item.error}`)).waitFor();
      await page.getByText(/Selected model\/baseline: naive/).waitFor();
    }
    await page.getByText(/Historical diagnostics only: the 2024 test outcomes were previously examined/).waitFor();
    assert.deepEqual(errors, []);
    console.log('PASS: real Phase 5A series selection and database-derived 1/3/7-day historical replay predictions/outcomes; no mocked routes or screenshots');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });
