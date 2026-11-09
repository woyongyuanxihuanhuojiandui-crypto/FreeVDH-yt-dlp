import json
from pathlib import Path

from playwright.sync_api import sync_playwright


extension = Path(__file__).parents[1]

with sync_playwright() as playwright:
    context = playwright.chromium.launch_persistent_context(
        '', executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe', headless=True,
        ignore_default_args=['--disable-extensions'], args=['--enable-unsafe-extension-debugging'])
    try:
        cdp = context.browser.new_browser_cdp_session()
        extension_id = cdp.send('Extensions.loadUnpacked', {'path': str(extension)})['id']
        worker = context.service_workers[0] if context.service_workers else context.wait_for_event('serviceworker')
        popup = context.new_page()
        popup.goto(f'chrome-extension://{extension_id}/content/popup.html')
        toolbar = popup.locator('com-toolbar')
        sidebar_button = toolbar.locator('#button_sidebar')
        sidebar_button.wait_for()
        popup.wait_for_timeout(1000)
        assert sidebar_button.evaluate('button => button.onclick !== null')
        sidebar_button.click()
        state = worker.evaluate('''async () => {
          for (let i = 0; i < 100 && globalThis._persistent_state?.dockmode !== 'sidebar'; i++)
            await new Promise(resolve => setTimeout(resolve, 50));
          return {
            dockmode: globalThis._persistent_state?.dockmode,
            popup: await chrome.action.getPopup({}),
            behavior: await chrome.sidePanel.getPanelBehavior(),
          };
        }''')
        assert state['dockmode'] == 'sidebar', state
        assert state['popup'] == '', state
        assert state['behavior']['openPanelOnActionClick'] is True, state
        print(json.dumps({'status': 'PASS', **state}))
    finally:
        context.close()
