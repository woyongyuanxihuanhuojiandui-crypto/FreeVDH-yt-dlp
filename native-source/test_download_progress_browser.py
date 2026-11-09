from pathlib import Path

from playwright.sync_api import sync_playwright


extension = Path(__file__).resolve().parents[1]


with sync_playwright() as playwright:
    context = playwright.chromium.launch_persistent_context(
        '',
        executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',
        headless=True,
        ignore_default_args=['--disable-extensions'],
        args=['--enable-unsafe-extension-debugging'],
    )
    try:
        cdp = context.browser.new_browser_cdp_session()
        extension_id = cdp.send('Extensions.loadUnpacked', {'path': str(extension)})['id']
        worker = context.service_workers[0] if context.service_workers else context.wait_for_event('serviceworker')

        page = context.new_page()
        page.route('http://download-progress.test/*', lambda route: route.fulfill(
            content_type='text/html', body='<video></video>'))
        page.goto('http://download-progress.test/')
        tab_id = worker.evaluate("async () => (await chrome.tabs.query({url: 'http://download-progress.test/*'}))[0].id")

        sidebar = context.new_page()
        sidebar.goto(f'chrome-extension://{extension_id}/content/sidebar.html')
        sidebar.locator('#sidebar-page-header').wait_for()
        def add_card():
            sidebar.evaluate("""tabId => {
              const media = document.querySelector('#main').shadowRoot.querySelector('#media');
              media.querySelector('#download-progress-card')?.remove();
              const card = document.createElement('com-media');
              card.id = 'download-progress-card';
              card.meta = {tab_id: tabId, url: {value: new URL('https://www.bilibili.com/video/example')}};
              const menu = card.shadowRoot.querySelector('com-media-discovered').shadowRoot.querySelector('#menu_options');
              menu.invalidateState([{id: 'menu_do_details', text: 'details', enabled: true, onclick: () => {}}]);
              media.append(card);
            }""", tab_id)
            card.locator('.sidebar-card-header').wait_for()

        card = sidebar.locator('com-main').locator('#download-progress-card')
        add_card()
        discovered = card.locator('com-media-discovered')
        main = discovered.locator('.sidebar-download-main')
        side = discovered.locator('.sidebar-download-side')
        text = main.locator('.sidebar-download-progress-text')
        fill = main.locator('.sidebar-download-progress-fill')
        card.evaluate('card => card.sidebarSetDownloadProgress(undefined, () => {})')
        assert text.text_content() == '正在连接…'
        assert main.evaluate("node => node.classList.contains('undefined')")
        assert fill.evaluate('node => getComputedStyle(node).animationName') == 'sidebar-download-connecting'

        card.evaluate('card => card.sidebarSetDownloadProgress(42, () => window.cancelled = true)')
        assert text.text_content() == '42%'
        assert fill.evaluate('node => node.style.width') == '42%'
        assert not main.evaluate("node => node.classList.contains('undefined')")
        assert side.get_attribute('aria-label') == '取消下载'
        side.evaluate('button => button.click()')
        assert sidebar.evaluate('window.cancelled')

        card.evaluate('card => card.sidebarSetDownloadIdle()')
        side.evaluate('button => button.click()')
        menu = discovered.locator('.sidebar-ytdlp-menu')
        assert menu.locator('button').count() == 1
        assert menu.locator('button').text_content() == '通过 yt-dlp 下载'

        controls = card.locator('#sidebar-page-controls')
        timeline_order = controls.locator('.sidebar-timeline-row > *').evaluate_all(
            "nodes => nodes.map(node => node.id || node.className)"
        )
        assert timeline_order == ['sidebar-play', 'sidebar-timeline-stack']
        speed_order = controls.locator('.sidebar-speed-row > *').evaluate_all('nodes => nodes.map(node => node.id)')
        assert speed_order == [
            'sidebar-speed-value',
            'sidebar-speed',
        ]
        action_order = controls.locator('.sidebar-action-grid > *').evaluate_all('nodes => nodes.map(node => node.id)')
        assert action_order == [
            'sidebar-loop',
            'sidebar-pip',
            'sidebar-fullscreen',
            'sidebar-screenshot',
        ]
        assert controls.locator('#sidebar-time, #sidebar-volume').evaluate_all(
            "nodes => nodes.map(node => getComputedStyle(node).backgroundSize)"
        ) == ['100% 3px', '100% 3px']
        controls.locator('#sidebar-volume-zero').evaluate('button => button.click()')
        page.wait_for_function('document.querySelector("video").volume === 0')
        controls.locator('#sidebar-volume-zero').evaluate('button => button.click()')
        page.wait_for_function('document.querySelector("video").volume === 1')

        card.evaluate('card => card.sidebarSetDownloadComplete({open: () => window.opened = true, remove: () => window.removed = true})')
        main.evaluate('button => button.click()')
        side.evaluate('button => button.click()')
        assert sidebar.evaluate('window.opened && window.removed')

        results = extension / 'native-source' / 'real-browser-results'
        results.mkdir(exist_ok=True)
        sidebar.wait_for_timeout(500)
        for width in (360, 370, 420):
            sidebar.set_viewport_size({'width': width, 'height': 900})
            add_card()
            card.evaluate('card => card.sidebarSetDownloadIdle()')
            sidebar.evaluate('''() => {
              document.querySelector('#sidebar-current-count').textContent = '当前页面 · 1';
              document.querySelector('#sidebar-current-host').textContent = 'www.bilibili.com';
              const style = document.createElement('style');
              style.textContent = '#loading { display: none !important; }';
              document.querySelector('#main').shadowRoot.append(style);
            }''')
            assert sidebar.evaluate('''() => {
              const card = document.querySelector('#main').shadowRoot.querySelector('#download-progress-card');
              const root = card.shadowRoot;
              const cardBox = card.getBoundingClientRect();
              const rows = ['.sidebar-timeline-row', '.sidebar-volume-row', '.sidebar-speed-row', '.sidebar-action-grid']
                .map(selector => root.querySelector(selector));
              const volume = root.querySelector('#sidebar-volume').getBoundingClientRect();
              const time = root.querySelector('#sidebar-time').getBoundingClientRect();
              const label = root.querySelector('#sidebar-time-label').getBoundingClientRect();
              const actions = [...root.querySelectorAll('.sidebar-action-grid > button')]
                .map(button => button.getBoundingClientRect());
              return rows.every(row => {
                const box = row.getBoundingClientRect();
                return box.left >= cardBox.left && box.right <= cardBox.right && row.scrollWidth <= row.clientWidth + 1;
              })
                && volume.width <= cardBox.width * .4
                && label.bottom <= time.top + 2
                && Math.abs(actions[0].left - actions[2].left) < 1
                && Math.abs(actions[1].left - actions[3].left) < 1
                && Math.abs(actions[0].top - actions[1].top) < 1
                && Math.abs(actions[2].top - actions[3].top) < 1;
            }''')
            sidebar.screenshot(path=str(results / f'reference-sidebar-{width}.png'))

        card.evaluate("""card => {
          card.shadowRoot.querySelector('com-media-downloading').invalidateState = () => {};
          card.isDownloading({percent: {is_known: false}});
          card.isDiscovered();
        }""")
        assert text.text_content() == '媒体 CDN 连接失败'
        print('PASS download progress states')
    finally:
        context.close()
