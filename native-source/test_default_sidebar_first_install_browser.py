import tempfile
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


extension = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as profile:
    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            profile,
            executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe",
            headless=False,
            ignore_default_args=["--disable-extensions"],
            args=["--enable-unsafe-extension-debugging"],
        )
        try:
            cdp = context.browser.new_browser_cdp_session()
            cdp.send("Extensions.loadUnpacked", {"path": str(extension)})
            worker = context.service_workers[0] if context.service_workers else context.wait_for_event("serviceworker")
            dockmode = None
            for _ in range(50):
                dockmode = worker.evaluate("globalThis._persistent_state?.dockmode")
                if dockmode:
                    break
                time.sleep(0.1)
            popup = worker.evaluate("async () => chrome.action.getPopup({})")
            options = worker.evaluate("async () => chrome.sidePanel.getOptions({})")
            assert dockmode == "sidebar", f"fresh install dock mode is {dockmode}"
            assert popup == "", f"fresh install still uses popup: {popup}"
            assert options["enabled"] is True, options
            print("PASS fresh install defaults to sidebar")
        finally:
            context.close()
