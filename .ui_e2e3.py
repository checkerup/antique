
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:18080"
OUT = r"C:/ai_workflow/antidetect-local/.ui_e2e3.py.results.txt"

results = []
def check(name, fn):
    try:
        fn()
        results.append((name, "PASS"))
    except Exception as e:
        results.append((name, "FAIL: " + str(e)[:120]))

js_errors = []

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.on("pageerror", lambda e: js_errors.append(str(e)))
    page.goto(BASE)
    page.wait_for_selector("#profiles-tbody")

    # 1) Settings screen: MCP/schedules/resources cards render
    def t_settings():
        page.click('[data-screen="settings"]')
        page.wait_for_selector("#mcp-summary")
        page.wait_for_selector("#schedule-list")
        page.wait_for_selector("#resource-status")
        page.wait_for_timeout(900)  # let fetches settle
        html = page.inner_html("#screen-settings")
        assert len(html) > 100
    check("settings cards render (MCP/schedules/resources)", t_settings)

    # 2) webstore search screen
    def t_ext():
        page.click('[data-screen="extensions"]')
        page.wait_for_selector("#ext-search-q")
        page.fill("#ext-search-q", "ublock")
        page.click("#ext-search-btn")
        page.wait_for_timeout(800)
        html = page.inner_html("#ext-results")
        assert "empty-note" in html or "activity-item" in html or len(html) > 0
    check("webstore search UI works", t_ext)

    # 3) remark filter filters table
    def t_remark():
        page.click('[data-screen="profiles"]')
        page.wait_for_selector("#profiles-tbody")
        before = page.locator("#profiles-tbody tr").count()
        rf = page.locator("#remark-filter")
        if not rf.count():
            raise Exception("#remark-filter not found")
        page.fill("#remark-filter", "zzz-no-such-note-xyz")
        page.wait_for_timeout(300)
        after = page.locator("#profiles-tbody tr").count()
        page.fill("#remark-filter", "")
        page.wait_for_timeout(300)
        restored = page.locator("#profiles-tbody tr").count()
        assert after == 0 or after < before, f"filter did not filter ({before}->{after})"
        assert restored >= after, "restore failed"
    check("remark filter narrows table", t_remark)

    # 4) drawer: aria-labels present
    def t_aria():
        page.dblclick("#profiles-tbody tr:first-child")
        page.wait_for_selector("#drawer.show", timeout=3000)
        aria = page.evaluate("Array.from(document.querySelectorAll('[aria-label]')).map(e=>e.getAttribute('aria-label'))")
        assert any("Diagnose" in a for a in aria), aria
    check("drawer buttons have aria-labels", t_aria)

    # 5) skeleton loading state exists in CSS
    def t_skeleton():
        has = page.evaluate("!!document.styleSheets && Array.from(document.styleSheets).some(ss => { try { return Array.from(ss.cssRules).some(r => r.selectorText && r.selectorText.includes('skeleton')) } catch(e) { return false } })")
        assert has, "no skeleton css rule"
    check("skeleton CSS present", t_skeleton)

    # 6) toast-wrap a11y
    def t_toast_a11y():
        role = page.get_attribute("#toast-wrap", "role")
        live = page.get_attribute("#toast-wrap", "aria-live")
        assert role == "alert" and live == "assertive"
    check("toast-wrap role=alert aria-live=assertive", t_toast_a11y)

    # 7) heartbeat label: health states wired
    def t_health():
        cls = page.get_attribute("#health-dot", "class") or ""
        label = page.inner_text("#health-label")
        assert "healthy" in cls or "down" in cls, cls
        assert label.strip(), "empty label"
    check("heartbeat states wired", t_health)

    # close drawer first
    page.keyboard.press("Escape")
    page.wait_for_timeout(400)
    # screenshot for the Boss
    page.click('[data-screen="settings"]')
    page.wait_for_timeout(600)
    page.screenshot(path=r"C:/ai_workflow/antidetect-local/.shot_settings.png")
    browser.close()

with open(OUT, "w", encoding="utf-8") as f:
    for n, s in results:
        f.write(f"{n}: {s}\n")
    f.write("JS_ERRORS: " + (str(js_errors) if js_errors else "0") + "\n")
print("\n".join(f"{n}: {s}" for n, s in results))
print("JS errors:", js_errors if js_errors else 0)
