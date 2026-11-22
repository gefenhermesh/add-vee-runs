const { chromium } = require('playwright');
const http = require('http'), fs = require('fs'), path = require('path');
const dir = process.argv[2], out = process.argv[3];
const srv = http.createServer((q, r) => { const f = path.join(dir, decodeURIComponent(q.url.split('?')[0]) === '/' ? 'visibility_action_plan.html' : decodeURIComponent(q.url.split('?')[0]));
  fs.readFile(f, (e, d) => { if (e) { r.writeHead(404); r.end(); return; } r.writeHead(200, {'Content-Type': f.endsWith('.json') ? 'application/json' : 'text/html'}); r.end(d); }); }).listen(8765);
(async () => {
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 760, height: 1200 }, deviceScaleFactor: 2, colorScheme: 'light' });
  await p.goto('http://localhost:8765/visibility_action_plan.html'); await p.waitForSelector('#diagnosisTiles > *'); await p.waitForTimeout(1500);
  // findings: section.execsum top to bottom of #diagnosisTiles
  const box = await p.evaluate(() => { const s = document.querySelector('section.execsum').getBoundingClientRect(); const d = document.getElementById('diagnosisTiles').getBoundingClientRect();
    return { x: Math.max(0, s.left + scrollX - 18), y: s.top + scrollY, w: Math.min(document.documentElement.scrollWidth, s.width + 36), h: d.bottom - s.top + 16 }; });
  await p.screenshot({ path: out + '/findings.png', clip: { x: box.x, y: box.y, width: box.w, height: box.h }, fullPage: true });
  // plan: build a composite of plan-intro heading+sub, first clusters (4th fading), off-page heading + 2 moves (3rd fading)
  await p.evaluate(() => {
    const fade = (el) => { el.style.maskImage = 'linear-gradient(to bottom, #000 0%, transparent 85%)'; el.style.webkitMaskImage = el.style.maskImage; el.style.maxHeight = '90px'; el.style.overflow = 'hidden'; };
    const wrap = document.createElement('div'); wrap.id = 'shot'; wrap.style.cssText = 'padding:20px 24px;background:var(--bg,#fff);width:712px';
    const intro = document.querySelector('section.plan-intro'); const ic = intro.cloneNode(true); ic.querySelector('.plan-controls')?.remove(); ic.style.borderTop='none'; wrap.appendChild(ic);
    const cl = document.getElementById('clusterList'); const cc = cl.cloneNode(false); [...cl.children].slice(0, 4).forEach((c, i) => { const k = c.cloneNode(true); if (i === 3) fade(k); cc.appendChild(k); }); wrap.appendChild(cc);
    const om = document.getElementById('offpageMoves'); const head = om.previousElementSibling?.tagName === 'H3' ? om.previousElementSibling : om.parentElement.querySelector('h3');
    const h = head.cloneNode(true); h.style.marginTop = '22px'; wrap.appendChild(h);
    const mc = om.cloneNode(false); [...om.children].slice(0, 3).forEach((c, i) => { const k = c.cloneNode(true); if (i === 2) fade(k); mc.appendChild(k); }); wrap.appendChild(mc);
    document.querySelectorAll('#expandAllBtn').forEach(e => e.remove());
    document.body.prepend(wrap); window.scrollTo(0, 0);
  });
  await p.locator('#shot').screenshot({ path: out + '/plan.png' });
  await b.close(); srv.close();
})();
