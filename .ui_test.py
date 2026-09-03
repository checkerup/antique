
from playwright.sync_api import sync_playwright
import json, sys

BASE = "http://127.0.0.1:18080"
results = []
def ok(name, cond, extra=""):
    results.append((name, bool(cond), extra))
    print(("PASS " if cond else "FAIL ") + name + (" | " + extra if extra else ""))

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append("console." + m.type + ": " + m.text) if m.type == "error" else None)

    page.goto(BASE + "/", wait_until="networkidle")

    # 1. boot: sidebar + brand
    ok("page title", page.title() == "Antique", page.title())
    ok("sidebar rendered", page.locator("#sidebar").count() == 1)
    ok("logo present", page.locator("#brand img").count() >= 1)

    # 2. profiles table
    rows = page.locator("#profiles-tbody tr")
    page.wait_for_timeout(800)
    n = rows.count()
    ok("profiles table rows > 0", n > 0, f"rows={n}")

    # 3. i18n switch to RU
    page.locator("#lang-switch button[data-lang=ru]").click()
    page.wait_for_timeout(300)
    brand_sub = page.locator(".brand-sub").inner_text()
    ok("i18n RU brand.sub", "Антидетект".lower() in brand_sub.lower(), brand_sub)

    # 4. i18n ZH
    page.locator("#lang-switch button[data-lang=zh]").click()
    page.wait_for_timeout(300)
    brand_sub = page.locator(".brand-sub").inner_text()
    ok("i18n ZH brand.sub", "防关联" in brand_sub, brand_sub)

    page.locator("#lang-switch button[data-lang=en]").click()
    page.wait_for_timeout(300)

    # 5. theme toggle
    body_theme_before = page.locator("html").get_attribute("data-theme") or ""
    page.locator("#theme-toggle").click()
    page.wait_for_timeout(200)
    body_theme_after = page.locator("html").get_attribute("data-theme") or ""
    ok("theme toggles class", body_theme_before != body_theme_after, f"{body_theme_before} -> {body_theme_after}")
    page.locator("#theme-toggle").click()
    page.wait_for_timeout(200)

    # 6. drawer open
    page.locator("#profiles-tbody tr").first.dblclick()
    page.wait_for_timeout(400)
    ok("drawer opens", page.locator("#drawer").get_attribute("class") is not None and page.evaluate("document.getElementById('drawer').classList.contains('show')"))

    # 7. console errors
    ok("no JS errors", len(errors) == 0, "; ".join(errors[:3]))

    page.screenshot(path=r"C:/ai_workflow/antidetect-local/.ui_test_dark.png", full_page=False)
    browser.close()

fails = [r for r in results if not r[1]]
print("\n=== SUMMARY:", f"{len(results)-len(fails)}/{len(results)} passed")
sys.exit(1 if fails else 0)
