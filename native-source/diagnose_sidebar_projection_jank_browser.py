import json
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright


here = Path(__file__).parent
extension = Path(sys.argv[1]) if len(sys.argv) > 1 else here.parent
source_rate = int(sys.argv[2]) if len(sys.argv) > 2 else 60
profile = tempfile.TemporaryDirectory(dir=here)
media_temp = tempfile.TemporaryDirectory(dir=here)
video_path = Path(media_temp.name) / "video.mp4"
subprocess.run([
    "ffmpeg", "-y", "-f", "lavfi", "-i", f"testsrc2=s=640x360:r={source_rate}:d=12",
    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(video_path),
], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
video_data = video_path.read_bytes()


def serve(route):
    if route.request.url.endswith("/video.mp4"):
        route.fulfill(content_type="video/mp4", body=video_data)
        return
    if "owner-b.test" in route.request.url:
        route.fulfill(content_type="text/html", body="<h1>Page B</h1>")
        return
    route.fulfill(content_type="text/html", body="""
      <button id="play">play</button>
      <video loop src="/video.mp4"></video>
      <script>play.onclick = () => document.querySelector('video').play()</script>
    """)


def sample(sidebar, waiting_page, seconds=3):
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
    }


with sync_playwright() as playwright:
    context = playwright.chromium.launch_persistent_context(
        profile.name,
        executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe",
        headless=False,
        ignore_default_args=["--disable-extensions"],
        args=["--enable-unsafe-extension-debugging"],
    )
    try:
        context.route("http://owner-a.test/*", serve)
        context.route("http://owner-b.test/*", serve)
        cdp = context.browser.new_browser_cdp_session()
        extension_id = cdp.send("Extensions.loadUnpacked", {"path": str(extension)})["id"]
        worker = next((item for item in context.service_workers if extension_id in item.url), None)
        if worker is None:
            worker = context.wait_for_event("serviceworker", predicate=lambda item: extension_id in item.url)

        page_a = context.new_page()
        page_a.goto("http://owner-a.test/page")
        page_a.locator("#play").click()
        tab_a = worker.evaluate("async () => (await chrome.tabs.query({url: 'http://owner-a.test/*'}))[0].id")

        sidebar = context.new_page()
        sidebar.goto(f"chrome-extension://{extension_id}/content/sidebar.html")
        sidebar.locator("#sidebar-page-header").wait_for()
        sidebar.evaluate("""
          globalThis.projectionFrames = [];
          chrome.runtime.onMessage.addListener((message, sender) => {
            if (message?.channel === 'freevdh-page-media-frame') {
              globalThis.projectionFrames.push([performance.now(), message.frame.length, sender.tab?.id]);
            }
          });
        """)
        sidebar.evaluate("""tabId => {
          const media = document.querySelector('#main').shadowRoot.querySelector('#media');
          const card = document.createElement('com-media');
          card.id = 'owner-a-card';
          card.meta = {tab_id: tabId, url: {value: new URL('http://owner-a.test/page')}};
          card.media = {
            type: 'youtube_format',
            sent_headers: new Headers(),
            playlist: [{av: {video: {url: new URL('http://owner-a.test/video.mp4')}}}],
          };
          card.shadowRoot.querySelector('com-media-discovered').shadowRoot.querySelector('#menu_options')
            .invalidateState([{id: 'menu_do_details', text: 'details', enabled: true, onclick: () => {}}]);
          media.append(card);
        }""", tab_a)
        sidebar.locator("com-main").locator("#owner-a-card").locator(".sidebar-card-header").wait_for()
        sidebar.evaluate("""() => {
          globalThis.renderedFrames = [];
          const card = document.querySelector('#main').shadowRoot.querySelector('#owner-a-card');
          const image = card.shadowRoot.querySelector('com-media-preview').shadowRoot.querySelector('.sidebar-page-frame');
          image.addEventListener('load', () => globalThis.renderedFrames.push(performance.now()));
        }""")
        for _ in range(50):
            if sidebar.evaluate("globalThis.projectionFrames.length") >= 3:
                break
            sidebar.wait_for_timeout(100)
        assert sidebar.evaluate("globalThis.projectionFrames.length") >= 3

        page_a.bring_to_front()
        active = sample(sidebar, page_a)

        page_b = context.new_page()
        page_b.goto("http://owner-b.test/page")
        page_b.bring_to_front()
        before = page_a.locator("video").evaluate("video => video.currentTime")
        background = sample(sidebar, page_b)
        after = page_a.locator("video").evaluate("video => video.currentTime")

        result = {
            "source_fps": source_rate,
            "source_advanced_seconds_while_background": round(after - before, 3),
            "source_tab_active": active,
            "source_tab_background": background,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        assert after - before > 2.5
        assert 55 <= background["image_fps"] <= 61 and background["image_max_gap_ms"] < 50, (
            "source video is smooth, sidebar projection is not"
        )
    finally:
        context.close()
        media_temp.cleanup()
        profile.cleanup()
