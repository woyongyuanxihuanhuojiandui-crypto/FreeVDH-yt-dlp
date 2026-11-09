from pathlib import Path

from playwright.sync_api import sync_playwright


extension = Path(__file__).resolve().parents[1]


with sync_playwright() as playwright:
    context = playwright.chromium.launch_persistent_context(
        "",
        executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe",
        headless=True,
        ignore_default_args=["--disable-extensions"],
        args=["--enable-unsafe-extension-debugging"],
    )
    try:
        cdp = context.browser.new_browser_cdp_session()
        extension_id = cdp.send("Extensions.loadUnpacked", {"path": str(extension)})["id"]
        page = context.new_page()
        page.goto(f"chrome-extension://{extension_id}/content/sidebar.html")
        page.locator("#sidebar-page-header").wait_for()
        page.evaluate("() => window.freeVDHPlayingCards.ready")

        page.evaluate("() => window.freeVDHPlayingCards.add(101, 'playing-card')")
        page.reload()
        page.locator("#sidebar-page-header").wait_for()
        page.evaluate("() => window.freeVDHPlayingCards.ready")
        assert page.evaluate("() => window.freeVDHPlayingCards.has(101, 'playing-card')")
        page.evaluate("() => window.freeVDHPlayingCards.remove(101, 'playing-card')")
        assert not page.evaluate("() => window.freeVDHPlayingCards.has(101, 'playing-card')")

        source_tab = page.evaluate(
            "async () => (await chrome.tabs.create({url: 'about:blank', active: false})).id"
        )
        page.evaluate("tabId => window.freeVDHPlayingCards.add(tabId, 'source-card')", source_tab)
        page.evaluate("tabId => chrome.tabs.remove(tabId)", source_tab)
        page.wait_for_function(
            "([tabId]) => !window.freeVDHPlayingCards.has(tabId, 'source-card')",
            arg=[source_tab],
        )
        print("PASS playing card session retention")
    finally:
        context.close()
