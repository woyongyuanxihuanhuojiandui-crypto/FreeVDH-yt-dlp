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
        sidebar = context.new_page()
        sidebar.goto(f"chrome-extension://{extension_id}/content/sidebar.html")
        sidebar.locator("#sidebar-page-header").wait_for()
        sidebar.wait_for_function("window.freeVDHYtdlpHistory")
        sidebar.evaluate("chrome.storage.local.remove('sidebarYtdlpHistory')")
        sidebar.evaluate("""window.freeVDHYtdlpHistory.add({
          path: 'C:/Downloads/video.mp4',
          name: 'video.mp4',
          url: 'https://www.example.com/watch',
          timestamp: 1
        })""")
        sidebar.wait_for_timeout(100)

        items = sidebar.locator("com-main").locator("#sidebar-ytdlp-downloaded > com-media-downloaded")
        assert items.count() == 1
        filename = items.locator("#p_filename").text_content()
        assert filename == "video.mp4", repr(filename)

        sidebar.reload()
        sidebar.locator("#sidebar-page-header").wait_for()
        sidebar.wait_for_function("window.freeVDHYtdlpHistory")
        sidebar.wait_for_timeout(100)
        items = sidebar.locator("com-main").locator("#sidebar-ytdlp-downloaded > com-media-downloaded")
        assert items.count() == 1
        filename = items.locator("#p_filename").text_content()
        assert filename == "video.mp4", repr(filename)

        sidebar.evaluate("""() => { window.nativeHistoryActions = [];
          window.freeVDHYtdlpRequest = payload => {
            window.nativeHistoryActions.push(payload.action);
            return Promise.resolve({state: 'done'});
          }; }""")
        items.locator("#button_play").click()
        items.locator("#button_dir").click()
        items.locator("#button_rm").click()
        sidebar.wait_for_timeout(100)
        actions = sidebar.evaluate("window.nativeHistoryActions")
        assert actions == ["open", "show", "delete"], actions
        assert items.count() == 0
        print("PASS persistent unified completed history")
    finally:
        context.close()
