
from playwright.sync_api import sync_playwright
import json

BASE = "http://127.0.0.1:18080"
OUT = r"C:/ai_workflow/antidetect-local"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1600, "height": 1000})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(BASE + "/", wait_until="networkidle")
    page.wait_for_timeout(600)

    checks = {}

    # --- DOM-based visual audit ---
    checks["bg_color_dark"] = page.evaluate("getComputedStyle(document.body).backgroundColor")
    checks["font"] = page.evaluate("getComputedStyle(document.body).fontFamily")
    checks["font_size"] = page.evaluate("getComputedStyle(document.body).fontSize")
    checks["wallpaper_display"] = page.evaluate("getComputedStyle(document.getElementById('wallpaper')).opacity")
    checks["logo_natural_w"] = page.evaluate("document.querySelector('#brand img').naturalWidth")
    checks["table_cols"] = page.evaluate("document.querySelectorAll('#profiles-table thead th').length")
    checks["overflow_x"] = page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
    # nav icons present?
    checks["nav_items"] = page.evaluate("document.querySelectorAll('#nav .nav-item').length")
    checks["nav_svgs"] = page.evaluate("document.querySelectorAll('#nav .nav-item svg').length")
    # avatar in row?
    checks["row_avatar"] = page.evaluate("!!document.querySelector('#profiles-tbody .row-avatar') || !!document.querySelector('#profiles-tbody tr img')")

    # --- drawer Escape test ---
    page.locator("#profiles-tbody tr").first.dblclick()
    page.wait_for_timeout(300)
    checks["drawer_open"] = page.evaluate("document.getElementById('drawer').classList.contains('show')")
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    checks["drawer_esc"] = page.evaluate("!document.getElementById('drawer').classList.contains('show')")
    # close via X if still open
    if page.evaluate("document.getElementById('drawer').classList.contains('show')"):
        page.locator("#drawer-close").click()
        page.wait_for_timeout(200)

    # --- modal shot ---
    page.locator("#new-profile-btn").click()
    page.wait_for_timeout(300)
    checks["modal_open"] = page.evaluate("document.getElementById('modal-new-profile').classList.contains('show')")
    page.screenshot(path=OUT + "/.shot_modal.png")
    page.keyboard.press("Escape")
    page.wait_for_timeout(200)

    # --- switch all screens, catch JS errors ---
    for scr in ["groups", "proxies", "automation", "extensions", "import", "activity", "settings"]:
        page.locator(f".nav-item[data-screen={scr}]").click()
        page.wait_for_timeout(350)
        visible = page.evaluate(f"!document.getElementById('screen-{scr}').hidden")
        checks[f"screen_{scr}_visible"] = visible
    # back to profiles
    page.locator(".nav-item[data-screen=profiles]").click()
    page.wait_for_timeout(300)

    checks["js_errors"] = errors

    print(json.dumps(checks, indent=1, ensure_ascii=False))
    browser.close()
