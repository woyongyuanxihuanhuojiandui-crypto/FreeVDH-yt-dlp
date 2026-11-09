import json
import tempfile
import winreg
from pathlib import Path

from playwright.sync_api import sync_playwright


extension = Path(__file__).resolve().parents[1]
artifacts = extension / 'output' / 'playwright'
artifacts.mkdir(parents=True, exist_ok=True)
registry_path = r'Software\Google\Chrome\NativeMessagingHosts\com.freevdh.ytdlp'
video_url = 'https://www.bilibili.com/video/BV1UB4v67Exr'


def launch_chrome(playwright):
    return playwright.chromium.launch_persistent_context(
        '',
        executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',
        headless=False,
        viewport=None,
        ignore_default_args=['--disable-extensions'],
        args=['--enable-unsafe-extension-debugging', '--start-maximized'],
    )


def wait_for(page, check, message, timeout=90000):
    for _ in range(timeout // 200):
        value = check()
        if value:
            return value
        page.wait_for_timeout(200)
    raise AssertionError(message)


def card_state(sidebar):
    return sidebar.evaluate("""() => {
      const card = [...document.querySelector('#main').shadowRoot.querySelector('#media').querySelectorAll('com-media')]
        .find(item => item.meta?.url?.value?.href.startsWith('https://www.bilibili.com/video/'));
      if (!card?.dataset.sidebarEnhanced) return null;
      const discovered = card.shadowRoot.querySelector('com-media-discovered').shadowRoot;
      const notice = document.querySelector('body > div[role="status"]');
      return {
        text: discovered.querySelector('.sidebar-download-progress-text').textContent,
        progressVisible: !discovered.querySelector('.sidebar-download-progress-row').hidden,
        completeVisible: !discovered.querySelector('.sidebar-download-complete').hidden,
        stopVisible: !discovered.querySelector('.sidebar-download-stop').hidden,
        status: card.status,
        notice: notice.hidden ? '' : notice.textContent,
      };
    }""")


def click_stop(sidebar):
    sidebar.evaluate("""() => [...document.querySelector('#main').shadowRoot
      .querySelector('#media').querySelectorAll('com-media')]
      .find(item => item.meta?.url?.value?.href.startsWith('https://www.bilibili.com/video/')).shadowRoot
      .querySelector('com-media-discovered').shadowRoot
      .querySelector('.sidebar-download-stop').click()""")


with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as host_dir:
    host_dir = Path(host_dir)
    launcher = host_dir / 'host.bat'
    manifest = host_dir / 'host.json'
    previous = None
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, registry_path) as key:
            previous = winreg.QueryValueEx(key, '')[0]
    except FileNotFoundError:
        pass

    with sync_playwright() as playwright:
        context = launch_chrome(playwright)
        observations = {'url': video_url, 'errors': []}
        try:
            cdp = context.browser.new_browser_cdp_session()
            extension_id = cdp.send('Extensions.loadUnpacked', {'path': str(extension)})['id']
            launcher.write_text('@echo off\r\n"%~dp0..\\package-dist\\freevdh-setup.exe" --host\r\n', encoding='ascii')
            manifest.write_text(json.dumps({
                'name': 'com.freevdh.ytdlp',
                'description': 'FreeVDH yt-dlp test host',
                'path': str(launcher),
                'type': 'stdio',
                'allowed_origins': [f'chrome-extension://{extension_id}/'],
            }), encoding='utf-8')
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, registry_path) as key:
                winreg.SetValueEx(key, '', 0, winreg.REG_SZ, str(manifest))

            context.close()
            context = launch_chrome(playwright)
            cdp = context.browser.new_browser_cdp_session()
            loaded_id = cdp.send('Extensions.loadUnpacked', {'path': str(extension)})['id']
            assert loaded_id == extension_id
            worker = context.service_workers[0] if context.service_workers else context.wait_for_event('serviceworker')
            worker.on('pageerror', lambda error: observations['errors'].append(f'worker: {error}'))

            page = context.new_page()
            page.on('pageerror', lambda error: observations['errors'].append(f'page: {error}'))
            page.goto(video_url, wait_until='domcontentloaded', timeout=60000)
            page.locator('video').first.wait_for(timeout=30000)
            tab_id = worker.evaluate("async url => (await chrome.tabs.query({url: url + '*'}))[0].id", video_url)

            sidebar = context.new_page()
            sidebar.on('pageerror', lambda error: observations['errors'].append(f'sidebar: {error}'))
            sidebar.goto(f'chrome-extension://{extension_id}/content/sidebar.html')
            sidebar.locator('#sidebar-page-header').wait_for()
            observations['bridgeProbe'] = sidebar.evaluate("""() => new Promise(resolve => {
              const port = chrome.runtime.connectNative('com.freevdh.ytdlp');
              port.onMessage.addListener(message => { resolve(message); port.disconnect(); });
              port.onDisconnect.addListener(() => resolve({error: chrome.runtime.lastError?.message || 'disconnected'}));
              port.postMessage({action: 'ping'});
            })""")
            assert observations['bridgeProbe'].get('state') == 'ready', observations['bridgeProbe']
            page.bring_to_front()
            origins = wait_for(sidebar, lambda: sidebar.evaluate("""tabId => {
              const cards = [...document.querySelector('#main').shadowRoot.querySelector('#media').querySelectorAll('com-media')];
              const card = cards.find(item => item.meta?.tab_id === tabId && item.media?.type === 'http_playlist');
              if (!card?.dataset.sidebarEnhanced) return null;
              card.id = 'bilibili-cdn-card';
              return [...new Set(card.media.playlist.flatMap(item => [item.av.video, item.av.audio]).map(value => {
                const url = new URL(value.href ?? value);
                return `${url.protocol}//${url.hostname}:${url.port || '443'}`;
              }))];
            }""", tab_id), 'Bilibili media card was not discovered')
            observations['internalOrigins'] = origins
            assert all(origin.startswith('https://') and origin.endswith(':443') for origin in origins), origins

            sidebar.evaluate("""() => [...document.querySelector('#main').shadowRoot
              .querySelector('#media').querySelectorAll('com-media')]
              .find(item => item.meta?.url?.value?.href.startsWith('https://www.bilibili.com/video/')).shadowRoot
              .querySelector('com-media-discovered').shadowRoot
              .querySelector('#action_download').click()""")
            internal_progress = wait_for(sidebar, lambda: (
                state if (state := card_state(sidebar)) and (
                    state['status'] == 'downloaded' or state['text'].endswith('%') and state['text'] != '0%') else None
            ), 'FreeVDH internal download neither progressed nor completed', 45000)
            observations['internalProgress'] = internal_progress
            if internal_progress['status'] == 'downloaded':
                sidebar.evaluate("""() => [...document.querySelector('#main').shadowRoot
                  .querySelector('#media').querySelectorAll('com-media')]
                  .find(item => item.meta?.url?.value?.href.startsWith('https://www.bilibili.com/video/')).shadowRoot
                  .querySelector('com-media-discovered').shadowRoot
                  .querySelector('.sidebar-download-delete').click()""")
            else:
                click_stop(sidebar)
                wait_for(sidebar, lambda: not card_state(sidebar)['progressVisible'], 'FreeVDH internal download did not stop')

            page.bring_to_front()
            observations['activeTab'] = sidebar.evaluate("async () => (await chrome.tabs.query({active: true, currentWindow: true}))[0]?.url")
            sidebar.evaluate("""() => {
              window.__freeVDHNativeMessages = [];
              const connectNative = chrome.runtime.connectNative.bind(chrome.runtime);
              chrome.runtime.connectNative = (...args) => {
                const port = connectNative(...args);
                port.onMessage.addListener(message => window.__freeVDHNativeMessages.push(message));
                return port;
              };
            }""")
            sidebar.evaluate("""() => window.freeVDHYtdlpDownload(
              [...document.querySelector('#main').shadowRoot.querySelector('#media').querySelectorAll('com-media')]
                .find(item => item.meta?.url?.value?.href.startsWith('https://www.bilibili.com/video/')))""")
            connecting = wait_for(sidebar, lambda: (
                state if (state := card_state(sidebar)) and state['text'] == '正在连接…' else None
            ), 'yt-dlp did not show the connecting state')
            observations['ytdlpConnecting'] = connecting
            ytdlp_progress = wait_for(sidebar, lambda: (
                state if (state := card_state(sidebar)) and (
                    state['notice'] or state['text'].endswith('%') and state['text'] != '0%') else None
            ), 'yt-dlp did not report real progress')
            if ytdlp_progress['notice']:
                raise AssertionError(ytdlp_progress['notice'])
            observations['ytdlpProgress'] = ytdlp_progress
            terminal = wait_for(sidebar, lambda: sidebar.evaluate("""() => {
              const state = window.__freeVDHNativeMessages.at(-1)?.state;
              return state === 'done' || state === 'error' ? state : null;
            }"""), 'yt-dlp did not finish')
            if terminal == 'error':
                raise AssertionError(sidebar.evaluate("window.__freeVDHNativeMessages.at(-1).message"))
            observations['nativeMessages'] = sidebar.evaluate("window.__freeVDHNativeMessages")
            wait_for(sidebar, lambda: card_state(sidebar)['completeVisible'], 'yt-dlp completion controls did not appear')
            sidebar.evaluate("""() => [...document.querySelector('#main').shadowRoot
              .querySelector('#media').querySelectorAll('com-media')]
              .find(item => item.meta?.url?.value?.href.startsWith('https://www.bilibili.com/video/')).shadowRoot
              .querySelector('com-media-discovered').shadowRoot
              .querySelector('.sidebar-download-delete').click()""")
            wait_for(sidebar, lambda: not card_state(sidebar)['progressVisible'] and not card_state(sidebar)['completeVisible'],
                     'yt-dlp controls did not return to idle')

            sidebar.bring_to_front()
            sidebar.screenshot(path=str(artifacts / 'bilibili-download-cdn.png'))
            observations['errors'] = observations['errors']
            print(json.dumps(observations, ensure_ascii=False))
        except Exception as error:
            observations['failure'] = str(error)
            observations['card'] = card_state(sidebar) if 'sidebar' in locals() else None
            observations['nativeMessages'] = sidebar.evaluate("window.__freeVDHNativeMessages || []") if 'sidebar' in locals() else []
            if 'sidebar' in locals():
                sidebar.screenshot(path=str(artifacts / 'bilibili-download-cdn-failure.png'))
            print(json.dumps(observations, ensure_ascii=False), flush=True)
            raise
        finally:
            context.close()
            if previous is None:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, registry_path)
            else:
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER, registry_path) as key:
                    winreg.SetValueEx(key, '', 0, winreg.REG_SZ, previous)
