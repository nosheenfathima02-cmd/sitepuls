const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1200, height: 900 }, deviceScaleFactor: 2 });
  for (const role of ['data_steward', 'pm_P2']) {
    await p.goto('file://' + process.cwd() + `/sample_data/dashboard_${role}.html`);
    await p.screenshot({ path: `docs/dashboard_${role}.png`, fullPage: true });
  }
  await b.close();
})();
