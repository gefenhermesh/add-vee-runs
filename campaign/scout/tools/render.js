// Render a JavaScript page and print its final HTML: node render.js <url> [wait_ms]
const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage();
  await p.goto(process.argv[2], { waitUntil: 'networkidle', timeout: 60000 }).catch(() => {});
  await p.waitForTimeout(Number(process.argv[3] || 2500));
  process.stdout.write(await p.content());
  await b.close();
})();
