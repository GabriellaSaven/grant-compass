"""Report which report pages overflow their letter-size sheet (needs the report server on :8766)."""
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome"); pg = b.new_page(viewport={"width": 1200, "height": 1100})
    pg.goto("http://127.0.0.1:8766/report.html"); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(300)
    res = pg.evaluate("""[...document.querySelectorAll('.page')].map((p,i)=>{const top=p.getBoundingClientRect().top;
      const limit=p.clientHeight-0.75*96; let bottom=0;
      p.querySelectorAll(':scope > *:not(.pfoot)').forEach(c=>{bottom=Math.max(bottom,c.getBoundingClientRect().bottom-top)});
      return [i+1, Math.round(bottom), Math.round(limit)]})""")
    for n, bottom, limit in res:
        print(f"p{n:>2} {'OVER ' + str(bottom - limit) + 'px' if bottom > limit else 'ok   free ' + str(limit - bottom) + 'px'}")
    b.close()
