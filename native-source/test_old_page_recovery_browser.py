import json
import subprocess
import tempfile
from pathlib import Path

from playwright.sync_api import Error, sync_playwright


extension = Path(__file__).resolve().parents[1]
manifest = json.loads((extension / "manifest.json").read_text(encoding="utf-8"))
assert all(
    pattern.endswith("/*")
    for entry in manifest["content_scripts"]
    for pattern in entry["matches"]
), "recovery matcher must be extended when manifest paths stop ending in /*"

media_temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
video_path = Path(media_temp.name) / "late.mp4"
subprocess.run([
    "ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc2=s=640x360:r=30:d=6",
    "-c:v", "libx264", "-b:v", "1M", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
    str(video_path),
], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
video_bytes = video_path.read_bytes()
assert len(video_bytes) >= 500_000


def serve_old_page(route):
    url = route.request.url
    if url.endswith("/late.mp4"):
        route.fulfill(content_type="video/mp4", body=video_bytes)
    elif url.endswith("/frame"):
        route.fulfill(content_type="text/html", body='<video id="frame-video"></video>')
    else:
        route.fulfill(
            content_type="text/html",
            body='<video id="main-video"></video><iframe src="/frame"></iframe>',
        )


def wait_for(check, page, message):
    for _ in range(80):
        try:
            result = check()
            if result:
                return result
        except Error:
            pass
        page.wait_for_timeout(100)
    raise AssertionError(message)


with sync_playwright() as playwright:
    context = playwright.chromium.launch_persistent_context(
        "",
        executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe",
        headless=True,
        ignore_default_args=["--disable-extensions"],
        args=["--enable-unsafe-extension-debugging"],
    )
    try:
        context.route("http://old-page.test/*", serve_old_page)
        context.route(
            "http://idle.test/*",
            lambda route: route.fulfill(content_type="text/html", body="idle"),
        )

        old_page = context.new_page()
        old_page.goto("http://old-page.test/page")
        idle_page = context.new_page()
        idle_page.goto("http://idle.test/page")

        cdp = context.browser.new_browser_cdp_session()
        extension_id = cdp.send("Extensions.loadUnpacked", {"path": str(extension)})["id"]
        worker = context.service_workers[0] if context.service_workers else context.wait_for_event("serviceworker")

        old_page.bring_to_front()

        def recovered_frames():
            states = worker.evaluate("""async () => {
              const [tab] = await chrome.tabs.query({url: 'http://old-page.test/*'});
              const frames = await chrome.webNavigation.getAllFrames({tabId: tab.id});
              const states = [];
              for (const frame of frames.filter(item => item.url.startsWith('http://old-page.test/'))) {
                states.push({
                  url: frame.url,
                  state: await chrome.tabs.sendMessage(
                    tab.id,
                    {channel: 'freevdh-page-media', action: 'peek'},
                    {frameId: frame.frameId},
                  ),
                });
              }
              return states;
            }""")
            return states if len(states) == 2 and all(item["state"]["count"] == 1 for item in states) else None

        states = wait_for(recovered_frames, old_page, "old page and iframe did not recover without refresh")

        worker.evaluate("""async () => {
          const [tab] = await chrome.tabs.query({url: 'http://old-page.test/*'});
          const frames = await chrome.webNavigation.getAllFrames({tabId: tab.id});
          const frame = frames.find(item => item.url.endsWith('/frame'));
          for (const [action, value] of [['muted', true], ['volume', 0.25], ['speed', 1.5]]) {
            await chrome.tabs.sendMessage(
              tab.id,
              {channel: 'freevdh-page-media', action, value},
              {frameId: frame.frameId},
            );
          }
        }""")
        iframe_state = old_page.frame_locator('iframe[src="/frame"]').locator("video").evaluate(
            "video => ({muted: video.muted, volume: video.volume, speed: video.playbackRate})"
        )
        assert iframe_state == {"muted": True, "volume": 0.25, "speed": 1.5}, iframe_state

        with old_page.expect_request(lambda request: request.url.endswith("/late.mp4")):
            old_page.evaluate("""() => {
              const video = document.querySelector('#main-video');
              video.src = '/late.mp4';
              video.load();
            }""")

        def loaded_state():
            state = worker.evaluate("""async () => {
              const [tab] = await chrome.tabs.query({url: 'http://old-page.test/*'});
              return chrome.tabs.sendMessage(
                tab.id,
                {channel: 'freevdh-page-media', action: 'peek'},
                {frameId: 0},
              );
            }""")
            return state if state["duration"] > 0 else None

        state = wait_for(loaded_state, old_page, "old page duration did not recover")
        old_page.locator("#main-video").evaluate("video => video.play()")

        sidebar = context.new_page()
        sidebar.goto(f"chrome-extension://{extension_id}/content/sidebar.html")
        sidebar.locator("#sidebar-page-header").wait_for()
        old_page.bring_to_front()
        cards = sidebar.locator("com-main").locator("#media > com-media")
        wait_for(lambda: cards.count() == 1, sidebar, "late media request was not recorded before the sidebar opened")

        idle_page.bring_to_front()
        stream = cards.first.locator("com-media-preview").locator(".sidebar-stream-video")
        wait_for(
            lambda: stream.evaluate("video => video.srcObject?.getVideoTracks()[0]?.readyState === 'live'"),
            sidebar,
            "old page media stream did not recover",
        )
        wait_for(
            lambda: worker.evaluate("""async () => {
              const [tab] = await chrome.tabs.query({url: 'http://idle.test/*'});
              return chrome.tabs.sendMessage(
                tab.id,
                {channel: 'freevdh-page-media', action: 'peek'},
                {frameId: 0},
              );
            }""") == {"count": 0},
            idle_page,
            "second old tab did not finish its first recovery",
        )
        old_page.bring_to_front()
        old_page.wait_for_timeout(100)

        worker.evaluate("""() => {
          self.freevdhRecoveryIdentifies = 0;
          chrome.runtime.onMessage.addListener(message => {
            if (message?.channel === 'freevdh-playback-session' && message.event === 'identify') {
              self.freevdhRecoveryIdentifies += 1;
            }
          });
        }""")
        for _ in range(10):
            idle_page.bring_to_front()
            idle_page.wait_for_timeout(50)
            old_page.bring_to_front()
            old_page.wait_for_timeout(50)

        old_page.wait_for_timeout(300)
        assert cards.count() == 1, cards.count()
        identify_count = worker.evaluate("() => self.freevdhRecoveryIdentifies")
        assert identify_count == 0, identify_count
        print(f"PASS old page recovery frames={len(states)} cards={cards.count()} duration={state['duration']}")
    finally:
        context.close()
        media_temp.cleanup()
