import json
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright


extension = Path(__file__).resolve().parents[1]
artifacts = extension / "output" / "playwright"
artifacts.mkdir(parents=True, exist_ok=True)
profile = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
observations = {"steps": [], "errors": []}


def record_error(page, error):
    observations["errors"].append(f"{page}: {error.stack}")


def install_controls(page):
    page.evaluate("""() => {
      const currentVideo = () => [...document.querySelectorAll('video')]
        .sort((left, right) => right.clientWidth * right.clientHeight - left.clientWidth * left.clientHeight)[0];
      const video = currentVideo();
      video.pause();
      video.muted = false;
      const play = document.createElement('button');
      play.id = 'codex-real-play';
      play.textContent = 'play';
      play.style = 'position:fixed;z-index:2147483647;left:10px;top:10px';
      play.onclick = () => {
        const current = currentVideo();
        current.muted = false;
        current.play();
      };
      const pip = document.createElement('button');
      pip.id = 'codex-real-pip';
      pip.textContent = 'pip';
      pip.style = 'position:fixed;z-index:2147483647;left:70px;top:10px';
      pip.onclick = () => document.pictureInPictureElement
        ? document.exitPictureInPicture()
        : currentVideo().requestPictureInPicture();
      document.body.append(play, pip);
    }""")


def open_pip(page):
    page.locator("#codex-real-pip").click()


def media_state(page):
    return page.evaluate("""() => {
      const video = document.pictureInPictureElement || [...document.querySelectorAll('video')]
        .sort((left, right) => right.clientWidth * right.clientHeight - left.clientWidth * left.clientHeight)[0];
      return video
        ? {
            paused: video.paused,
            time: video.currentTime,
            pip: document.pictureInPictureElement === video,
            muted: video.muted,
            volume: video.volume,
            userActive: navigator.userActivation.isActive,
          }
        : {paused: true, time: 0, pip: false};
    }""")


def card_state(sidebar, tab_id):
    return sidebar.evaluate("""tabId => {
      const cards = [...document.querySelector('#main').shadowRoot.querySelector('#media').querySelectorAll('com-media')];
      const card = cards.find(item => item.meta?.tab_id === tabId);
      if (!card?.dataset.sidebarEnhanced) return null;
      const preview = card.shadowRoot.querySelector('com-media-preview').shadowRoot;
      return {
        title: card.shadowRoot.querySelector('.sidebar-card-title')?.textContent,
        collapsed: card.classList.contains('sidebar-collapsed'),
        coverVisible: !preview.querySelector('.sidebar-pip-cover').hidden,
        framePresent: Boolean(preview.querySelector('.sidebar-page-frame').getAttribute('src')),
        directPaused: preview.querySelector('.sidebar-direct-video').paused,
        time: card.shadowRoot.querySelector('#sidebar-time-label')?.textContent,
      };
    }""", tab_id)


def wait_for(page, check, message, timeout=30000):
    for _ in range(timeout // 200):
        value = check()
        if value:
            return value
        page.wait_for_timeout(200)
    raise AssertionError(message)


def video_links(page):
    links = page.locator('a[href*="/video/"]').evaluate_all("""items =>
      [...new Set(items.map(item => item.href.split('?')[0]))]
        .filter(url => url.startsWith('https://www.bilibili.com/video/'))""")
    return links if len(links) >= 2 else []


with sync_playwright() as playwright:
    context = playwright.chromium.launch_persistent_context(
        profile.name,
        executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe",
        headless=False,
        viewport=None,
        ignore_default_args=["--disable-extensions"],
        args=[
            "--enable-unsafe-extension-debugging",
            "--autoplay-policy=user-gesture-required",
            "--start-maximized",
        ],
    )
    try:
        cdp = context.browser.new_browser_cdp_session()
        extension_id = cdp.send("Extensions.loadUnpacked", {"path": str(extension)})["id"]
        worker = context.service_workers[0] if context.service_workers else context.wait_for_event("serviceworker")

        listing = context.new_page()
        listing.goto("https://www.bilibili.com/v/popular/all", wait_until="domcontentloaded", timeout=60000)
        links = wait_for(listing, lambda: video_links(listing), "fewer than two Bilibili video links")
        url_a, url_b = links[0], links[1]
        observations["urls"] = {"a": url_a, "b": url_b}

        page_b = context.new_page()
        page_b.on("pageerror", lambda error: record_error("B", error))
        page_b.goto(url_b, wait_until="domcontentloaded", timeout=60000)
        page_b.locator("video").first.wait_for(timeout=30000)
        install_controls(page_b)

        page_a = context.new_page()
        page_a.on("pageerror", lambda error: record_error("A", error))
        page_a.goto(url_a, wait_until="domcontentloaded", timeout=60000)
        page_a.locator("video").first.wait_for(timeout=30000)
        install_controls(page_a)
        page_a.locator("#codex-real-play").click()
        wait_for(page_a, lambda: not media_state(page_a)["paused"], "A did not play")
        tab_a = worker.evaluate("async url => (await chrome.tabs.query({url: url + '*'}))[0].id", url_a)

        sidebar = context.new_page()
        sidebar.on("pageerror", lambda error: record_error("sidebar", error))
        sidebar.goto(f"chrome-extension://{extension_id}/content/sidebar.html")
        sidebar.locator("#sidebar-page-header").wait_for()
        page_a.bring_to_front()
        card_a = wait_for(sidebar, lambda: card_state(sidebar, tab_a), "FreeVDH did not create an A card", 45000)
        observations["steps"].append({"name": "A page owns", "pageA": media_state(page_a), "cardA": card_a})
        page_a.screenshot(path=str(artifacts / "bilibili-a-page.png"))

        open_pip(page_a)
        wait_for(page_a, lambda: media_state(page_a)["pip"], "A picture-in-picture did not open")
        wait_for(sidebar, lambda: card_state(sidebar, tab_a)["coverVisible"], "sidebar did not hide during picture-in-picture")
        observations["steps"].append({"name": "A picture-in-picture owns", "pageA": media_state(page_a), "cardA": card_state(sidebar, tab_a)})

        page_b.bring_to_front()
        before = media_state(page_a)["time"]
        page_b.wait_for_timeout(1500)
        after = media_state(page_a)["time"]
        observations["steps"].append({
            "name": "switch to B while A picture-in-picture owns",
            "pageA": media_state(page_a),
            "pageB": media_state(page_b),
            "cardA": card_state(sidebar, tab_a),
            "advanced": after - before,
        })
        print(json.dumps(observations["steps"][-1], ensure_ascii=False), flush=True)
        page_b.screenshot(path=str(artifacts / "bilibili-a-pip-on-b.png"))

        assert media_state(page_a)["pip"], "A picture-in-picture closed before B was played"
        page_a.evaluate("document.exitPictureInPicture()")
        wait_for(page_b, lambda: not media_state(page_a)["pip"], "A picture-in-picture did not close")
        wait_for(sidebar, lambda: not card_state(sidebar, tab_a)["coverVisible"], "sidebar did not resume its projection")
        before = media_state(page_a)["time"]
        page_b.wait_for_timeout(1500)
        after = media_state(page_a)["time"]
        observations["steps"].append({
            "name": "sidebar projection after picture-in-picture exit",
            "pageA": media_state(page_a),
            "cardA": card_state(sidebar, tab_a),
            "advanced": after - before,
        })
        sidebar.screenshot(path=str(artifacts / "bilibili-sidebar-projection.png"))

        page_a.bring_to_front()
        open_pip(page_a)
        wait_for(page_a, lambda: media_state(page_a)["pip"], "second A picture-in-picture did not open")
        page_b.bring_to_front()
        page_b.locator("#codex-real-play").click()
        wait_for(page_b, lambda: not media_state(page_b)["paused"], "B did not play")
        wait_for(page_b, lambda: media_state(page_a)["paused"], "B did not stop A")
        wait_for(page_b, lambda: not media_state(page_a)["pip"], "B did not close A picture-in-picture")
        observations["steps"].append({
            "name": "B claims playback",
            "pageA": media_state(page_a),
            "pageB": media_state(page_b),
            "cardA": card_state(sidebar, tab_a),
        })
        page_b.screenshot(path=str(artifacts / "bilibili-b-claims.png"))

        page_a.bring_to_front()
        page_a.wait_for_timeout(500)
        observations["steps"].append({"name": "return to A", "pageA": media_state(page_a), "pageB": media_state(page_b)})
        page_a.screenshot(path=str(artifacts / "bilibili-return-a.png"))
        print(json.dumps(observations, ensure_ascii=False))
    finally:
        context.close()
        profile.cleanup()
