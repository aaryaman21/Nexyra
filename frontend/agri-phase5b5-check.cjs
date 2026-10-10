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
    const heading = page.getByRole('heading', { name: 'Semantic intelligence' });
    await heading.waitFor();
    const card = prid => page.locator('article').filter({ hasText: `PIB release ${prid}` });
    for (const prid of ['1684194', '1972618', '2042765', '2114060']) {
      assert.equal(await card(prid).count(), 1, `exactly one dashboard card for PRID ${prid}`);
    }
    const removal = card('1684194');
    await removal.getByText('export_restriction_removal', { exact: false }).first().waitFor();
    const mep = card('1972618');
    await mep.getByText('mep_introduction', { exact: false }).first().waitFor();
    await mep.getByText('government_procurement', { exact: false }).first().waitFor();
    const volume = card('2042765');
    await volume.getByText('reported_export_volume', { exact: false }).first().waitFor();
    await volume.getByText('2.60 lakh tons', { exact: false }).first().waitFor();
    await volume.getByText('FY 2024-25 through 31 July 2024', { exact: false }).first().waitFor();
    await volume.getByText('market_price_report', { exact: false }).first().waitFor();
    await volume.getByText('Rs.1,230–2,578 per quintal vs Rs.693–1,205 per quintal', { exact: false }).waitFor();
    const duty = card('2114060');
    await duty.getByText('export_duty_reduction', { exact: false }).first().waitFor();
    await duty.getByText('Published: 2025-03-22', { exact: false }).waitFor();
    await duty.getByText('effective 1 April 2025', { exact: false }).waitFor();
    await duty.getByText('reported_export_volume', { exact: false }).first().waitFor();
    await duty.getByText('market_arrivals', { exact: false }).first().waitFor();
    await duty.getByText('production_estimate', { exact: false }).first().waitFor();
    await duty.getByText('market_price_report', { exact: false }).first().waitFor();
    await duty.getByText('Rs.1330/qtl and Rs.1325/qtl', { exact: false }).first().waitFor();
    await duty.getByText('10% decline', { exact: false }).waitFor();
    await duty.getByText('actual causal effects and Nashik price direction remain unknown and unvalidated', { exact: false }).waitFor();
    await volume.getByText('Best available source text', { exact: false }).click();
    await volume.getByText('State-wise production of Onion', { exact: false }).waitFor();
    await duty.getByText('Best available source text', { exact: false }).click();
    await duty.getByText('The Government of India has withdrawn 20% duty', { exact: false }).first().waitFor();
    assert.deepEqual(errors, []);
    console.log('PASS: production dashboard shows four unique PIB cards, full text, dates, classifications, evidence, reported quantities, and no browser exceptions');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });
