const { chromium } = require('playwright');
const assert = require('node:assert/strict');

(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(process.env.NEXYRA_BASE_URL || 'http://127.0.0.1:3010');
    const skip = page.getByRole('button', { name: /skip/i });
    if (await skip.count()) await skip.click();
    await page.getByRole('heading', { name: 'Semantic intelligence' }).waitFor();
    const apiHealth = await page.evaluate(async () => (await fetch('/api/agri/events/recent?limit=50')).json());
    console.log('API dataset health:', JSON.stringify(apiHealth.dataset_health));
    const expected = ['1684194', '1869581', '1950595', '1972618', '2003590', '2016405', '2042765', '2054873', '2057920', '2088051', '2102360', '2114060', '2163638', '2280999', '2303587', '2303921', '2313926', '2320278'];
    const cards = page.locator('article');
    assert.equal(await cards.count(), expected.length, 'one card per unique PIB release');
    for (const prid of expected) {
      assert.equal(await cards.filter({ hasText: `PIB release ${prid}` }).count(), 1, `one dashboard card for PRID ${prid}`);
    }
    const panelText = await page.getByRole('heading', { name: 'Semantic intelligence' }).locator('..').innerText();
    assert.match(panelText, /18 unique source articles/);
    assert.match(panelText, /18 full-body texts/);
    assert.match(panelText, /0 human-reviewed/);
    assert.match(panelText, /evaluation: insufficient labels/);
    const duty = cards.filter({ hasText: 'PIB release 2114060' });
    await duty.getByText('export_duty_reduction', { exact: false }).first().waitFor();
    await duty.getByText('Published: 2025-03-22', { exact: false }).waitFor();
    assert.deepEqual(errors, []);
    console.log('PASS: 18 distinct release cards, 18 full-text articles, zero human labels, original design renders, and no browser exceptions');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });
