
from playwright.sync_api import sync_playwright
BASE = "http://127.0.0.1:18080"
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto(BASE)
    page.wait_for_selector("#profiles-tbody")
    page.wait_for_timeout(2500)  # let heartbeat fire (/info poll)
    cls = page.get_attribute("#health-dot", "class") or ""
    label = page.inner_text("#health-label")
    print("class:", repr(cls), "| label:", repr(label))
    # check errors in console
    errs = []
    page.on("pageerror", lambda e: errs.append(str(e)))
    page.wait_for_timeout(1000)
    print("errors:", errs)
    browser.close()
