
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:18080"
OUT = r"C:/ai_workflow/antidetect-local"
results = []
def ok(name, cond, extra=""):
    results.append((name, bool(cond), extra))
    print(("PASS " if cond else "FAIL ") + name + (" | " + str(extra) if extra else ""))

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1600, "height": 1000})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(BASE + "/", wait_until="networkidle")
    page.wait_for_timeout(700)

    # bulk toolbar buttons visible
    for bid in ["bulk-randomize-btn", "bulk-audit-btn", "mass-create-btn"]:
        ok(f"toolbar {bid}", page.locator(f"#{bid}").count() == 1)

    # select 2 rows via checkboxes
    boxes = page.locator("#profiles-tbody .row-sel")
    boxes.nth(0).check()
    boxes.nth(1).check()
    page.wait_for_timeout(300)

    # open randomize modal
    page.locator("#bulk-randomize-btn").click()
    page.wait_for_timeout(300)
    ok("randomize modal opens", page.evaluate("document.getElementById('modal-randomize').classList.contains('show')"))
    ok("randomize shared checkboxes", page.locator("#modal-randomize .rnd-shared").count() == 7)
    ok("randomize preserve checkboxes", page.locator("#modal-randomize .rnd-preserve").count() == 6)
    # toggle overrides panel
    page.check("#rnd-overrides-enabled")
    page.wait_for_timeout(200)
    ok("overrides panel visible", page.evaluate("document.getElementById('rnd-overrides-panel').style.display !== 'none'"))
    page.keyboard.press("Escape")
    page.wait_for_timeout(200)
    ok("esc closes randomize", page.evaluate("!document.getElementById('modal-randomize').classList.contains('show')"))

    # mass create modal
    page.locator("#mass-create-btn").click()
    page.wait_for_timeout(200)
    ok("mass modal opens", page.evaluate("document.getElementById('modal-mass').classList.contains('show')"))
    page.fill("#mass-count", "3")
    page.fill("#mass-prefix", "TEST-MASS")
    page.locator("#mass-submit").click()
    page.wait_for_timeout(2500)
    n = page.locator("#profiles-tbody tr", has_text="TEST-MASS").count()
    ok("mass created 3 profiles", n == 3, f"found {n}")

    # bulk audit (2 selected still)
    page.locator("#bulk-audit-btn").click()
    page.wait_for_timeout(2000)
    ok("audit modal has rows", page.locator("#audit-body .activity-item").count() >= 1,
       f"rows={page.locator('#audit-body .activity-item').count()}")
    page.keyboard.press("Escape")

    # randomize actually runs on selection
    boxes.nth(0).check()
    page.locator("#bulk-randomize-btn").click()
    page.wait_for_timeout(200)
    page.locator("#rnd-submit").click()
    page.wait_for_timeout(1500)
    ok("randomize submitted (no JS errors so far)", len(errors) == 0, "; ".join(errors[:2]))

    # cleanup mass-created profiles
    page.fill("#global-search", "TEST-MASS")
    page.wait_for_timeout(500)
    del_rows = page.locator("#profiles-tbody tr", has_text="TEST-MASS")
    cnt = del_rows.count()
    page.on("dialog", lambda d: d.accept())
    for i in range(cnt):
        page.locator("#profiles-tbody tr", has_text="TEST-MASS").first.dblclick()
        page.wait_for_timeout(250)
        page.locator("#drawer [data-dact=delete]").click()
        page.wait_for_timeout(600)
    ok("mass profiles cleaned", page.locator("#profiles-tbody tr", has_text="TEST-MASS").count() == 0)

    ok("no JS errors", len(errors) == 0, "; ".join(errors[:3]))
    browser.close()

fails = [r for r in results if not r[1]]
print("\n=== BULK/E2E-2 SUMMARY:", f"{len(results)-len(fails)}/{len(results)} passed")
