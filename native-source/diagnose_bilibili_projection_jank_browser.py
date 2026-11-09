import json
import statistics
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright


here = Path(__file__).parent
extension = here.parent
profile = tempfile.TemporaryDirectory(dir=here)


def wait_for(page, check, message, timeout=45000):
    for _ in range(timeout // 200):
        value = check()
        if value:
            return value
        page.wait_for_timeout(200)
    raise AssertionError(message)


def sample(sidebar, waiting_page, seconds=5):
    sidebar.evaluate("globalThis.projectionFrames = []; globalThis.renderedFrames = []")
    waiting_page.wait_for_timeout(seconds * 1000)
    frames = sidebar.evaluate("globalThis.projectionFrames")
    rendered = sidebar.evaluate("globalThis.renderedFrames")
    gaps = [right[0] - left[0] for left, right in zip(frames, frames[1:])]
    rendered_gaps = [right - left for left, right in zip(rendered, rendered[1:])]
    return {
        "messages": len(frames),
        "message_fps": round(len(frames) / seconds, 1),
        "message_median_gap_ms": round(statistics.median(gaps), 1),
        "message_max_gap_ms": round(max(gaps), 1),
        "image_loads": len(rendered),
        "image_fps": round(len(rendered) / seconds, 1),
        "image_median_gap_ms": round(statistics.median(rendered_gaps), 1),
        "image_max_gap_ms": round(max(rendered_gaps), 1),
        "mean_frame_chars": round(statistics.mean(frame[1] for frame in frames)),
        "largest_frame_chars": max(frame[1] for frame in frames),
    }


with sync_playwright() as playwright:
    context = playwright.chromium.launch_persistent_context(
        profile.name,
        executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe",
        headless=False,
        viewport=None,
        ignore_default_args=["--disable-extensions"],
        args=["--enable-unsafe-extension-debugging", "--autoplay-policy=user-gesture-required", "--start-maximized"],
    )
    try:
        context.route("http://owner-b.test/*", lambda route: route.fulfill(content_type="text/html", body="<h1>Page B</h1>"))
        cdp = context.browser.new_browser_cdp_session()
        extension_id = cdp.send("Extensions.loadUnpacked", {"path": str(extension)})["id"]
        worker = next((item for item in context.service_workers if extension_id in item.url), None)
        if worker is None:
            worker = context.wait_for_event("serviceworker", predicate=lambda item: extension_id in item.url)

        page_a = context.new_page()
        page_a.goto("https://www.bilibili.com/v/popular/all", wait_until="domcontentloaded", timeout=60000)
        video_url = wait_for(page_a, lambda: page_a.locator('a[href*="/video/"]').evaluate_all("""items =>
          [...new Set(items.map(item => item.href.split('?')[0]))]
            .find(url => url.startsWith('https://www.bilibili.com/video/'))"""), "Bilibili video link not found")
        page_a.goto(video_url, wait_until="domcontentloaded", timeout=60000)
        page_a.locator("video").first.wait_for(timeout=30000)
        page_a.evaluate("""() => {
          const video = [...document.querySelectorAll('video')]
            .sort((left, right) => right.clientWidth * right.clientHeight - left.clientWidth * left.clientHeight)[0];
          video.pause();
          video.muted = true;
          const button = document.createElement('button');
          button.id = 'codex-real-play';
          button.style = 'position:fixed;z-index:2147483647;left:10px;top:10px';
          button.onclick = () => video.play();
          document.body.append(button);
        }""")
        page_a.locator("#codex-real-play").click()
        video_time = lambda: page_a.locator("video").first.evaluate("video => video.currentTime")
        wait_for(page_a, lambda: video_time() > 0.5, "Bilibili video did not play")
        tab_a = worker.evaluate("async () => (await chrome.tabs.query({url: 'https://www.bilibili.com/video/*'}))[0].id")

        sidebar = context.new_page()
        sidebar.goto(f"chrome-extension://{extension_id}/content/sidebar.html")
        sidebar.locator("#sidebar-page-header").wait_for()
        sidebar.evaluate("""
          globalThis.projectionFrames = [];
          globalThis.renderedFrames = [];
          chrome.runtime.onMessage.addListener((message, sender) => {
            if (message?.channel === 'freevdh-page-media-frame') {
              globalThis.projectionFrames.push([performance.now(), message.frame.length, sender.tab?.id]);
            }
          });
        """)

        def card_ready():
            return sidebar.evaluate("""tabId => {
              const card = [...document.querySelector('#main').shadowRoot.querySelector('#media').querySelectorAll('com-media')]
                .find(item => item.meta?.tab_id === tabId && item.dataset.sidebarEnhanced);
              return Boolean(card);
            }""", tab_a)

        wait_for(sidebar, card_ready, "FreeVDH did not create the Bilibili card")
        sidebar.evaluate("""tabId => {
          const card = [...document.querySelector('#main').shadowRoot.querySelector('#media').querySelectorAll('com-media')]
            .find(item => item.meta?.tab_id === tabId);
          card.shadowRoot.querySelector('.sidebar-card-header').click();
          const image = card.shadowRoot.querySelector('com-media-preview').shadowRoot.querySelector('.sidebar-page-frame');
          image.addEventListener('load', () => globalThis.renderedFrames.push(performance.now()));
        }""", tab_a)
        wait_for(sidebar, lambda: sidebar.evaluate("globalThis.projectionFrames.length >= 3"), "projection did not start")

        page_a.bring_to_front()
        active = sample(sidebar, page_a)

        page_b = context.new_page()
        page_b.goto("http://owner-b.test/page")
        page_b.bring_to_front()
        before = video_time()
        background = sample(sidebar, page_b)
        after = video_time()

        print(json.dumps({
            "source_advanced_seconds_while_background": round(after - before, 3),
            "source_tab_active": active,
            "source_tab_background": background,
        }, ensure_ascii=False, indent=2))
    finally:
        context.close()
        profile.cleanup()
