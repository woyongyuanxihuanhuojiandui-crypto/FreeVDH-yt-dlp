import subprocess
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright


extension = Path(__file__).resolve().parents[1]
media_temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
video_a = Path(media_temp.name) / "a.mp4"
video_b = Path(media_temp.name) / "b.mp4"
for source, frequency, output in (
    ("testsrc2=s=160x90:r=30:d=8", 440, video_a),
    ("smptebars=s=160x90:r=30:d=8", 660, video_b),
):
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", source,
        "-f", "lavfi", "-i", f"sine=frequency={frequency}:sample_rate=48000:duration=8",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
        "-movflags", "+faststart", str(output),
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def serve_media(route, path):
    data = path.read_bytes()
    requested = route.request.headers.get("range")
    if not requested:
        route.fulfill(content_type="video/mp4", body=data)
        return
    start_text, end_text = requested.removeprefix("bytes=").split("-", 1)
    start = int(start_text)
    end = int(end_text) if end_text else len(data) - 1
    route.fulfill(
        status=206,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Range": f"bytes {start}-{end}/{len(data)}",
            "Content-Type": "video/mp4",
        },
        body=data[start:end + 1],
    )


def serve(route):
    url = route.request.url
    if url.endswith("/video.mp4"):
        serve_media(route, video_a if "owner-a" in url else video_b)
        return
    route.fulfill(content_type="text/html", body="""
      <button id="play">play</button><button id="pip">pip</button>
      <video loop src="/video.mp4"></video>
      <script>
        play.onclick = () => document.querySelector('video').play();
        pip.onclick = () => document.pictureInPictureElement
          ? document.exitPictureInPicture()
          : document.querySelector('video').requestPictureInPicture();
      </script>
    """)


def wait_for(check, pages, message):
    for _ in range(50):
        if check():
            return
        pages[0].wait_for_timeout(100)
    raise AssertionError(message)


with sync_playwright() as playwright:
    context = playwright.chromium.launch_persistent_context(
        "",
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
        worker = context.service_workers[0] if context.service_workers else context.wait_for_event("serviceworker")
        worker.on("pageerror", lambda error: print(f"WORKER ERROR: {error.stack}"))

        page_a = context.new_page()
        page_a.goto("http://owner-a.test/page")
        page_a.locator("#play").click()
        tab_a = worker.evaluate("async () => (await chrome.tabs.query({url: 'http://owner-a.test/*'}))[0].id")
        session_state = lambda: worker.evaluate("async () => (await chrome.storage.session.get('freevdhPlaybackSession')).freevdhPlaybackSession")
        wait_for(lambda: (session_state() or {}).get("tabId") == tab_a, [page_a], "A did not claim the playback session")

        sidebar = context.new_page()
        sidebar.goto(f"chrome-extension://{extension_id}/content/sidebar.html")
        sidebar.locator("#sidebar-page-header").wait_for()
        page_a.bring_to_front()
        sidebar.wait_for_timeout(300)
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
        card = sidebar.locator("com-main").locator("#owner-a-card")
        card.locator(".sidebar-card-header").wait_for()

        def card_state():
            return card.evaluate("""card => {
              const preview = card.shadowRoot.querySelector('com-media-preview').shadowRoot;
              const video = preview.querySelector('.sidebar-stream-video');
              const track = video?.srcObject?.getVideoTracks()[0];
              return {
                streamActive: track?.readyState === 'live',
                streamMuted: video?.muted,
                coverVisible: !preview.querySelector('.sidebar-pip-cover').hidden,
                fallbackVisible: preview.querySelector('.sidebar-stream-fallback')
                  ? !preview.querySelector('.sidebar-stream-fallback').hidden
                  : false,
                frames: Number(card.dataset.testFrames || 0),
              };
            }""")

        card.evaluate("""card => {
          const video = card.shadowRoot.querySelector('com-media-preview').shadowRoot
            .querySelector('.sidebar-stream-video');
          if (!video) return;
          const count = () => {
            card.dataset.testFrames = String(Number(card.dataset.testFrames || 0) + 1);
            video.requestVideoFrameCallback(count);
          };
          video.requestVideoFrameCallback(count);
        }""")
        wait_for(lambda: card_state()["coverVisible"], [sidebar], "source-page playback must hide the sidebar picture")
        assert not card_state()["streamActive"], card_state()
        assert not page_a.locator("video").evaluate("video => video.paused")

        page_b = context.new_page()
        page_b.goto("http://owner-b.test/page")
        page_b.bring_to_front()
        wait_for(lambda: card_state()["streamActive"], [sidebar], "background source did not start media-stream projection")
        assert card_state()["streamMuted"], card_state()
        sidebar.bring_to_front()
        before = card_state()["frames"]
        sidebar.wait_for_timeout(1200)
        assert card_state()["frames"] - before >= 10, card_state()
        page_b.bring_to_front()

        page_a.bring_to_front()
        page_a.locator("#pip").click()
        page_b.bring_to_front()
        wait_for(lambda: page_a.evaluate("document.pictureInPictureElement !== null"), [page_a], "native picture-in-picture did not open")
        wait_for(lambda: page_a.evaluate("document.documentElement.dataset.freevdhPip === '1'"), [page_a], "main-world picture-in-picture bridge did not publish")
        isolated_state = lambda: worker.evaluate("""async tabId => chrome.tabs.sendMessage(
          tabId, {channel: 'freevdh-page-media', action: 'state'}, {frameId: 0})""", tab_a)
        wait_for(lambda: isolated_state().get("pip"), [page_a], "isolated content script did not observe picture-in-picture")
        assert session_state()["mediaId"] == isolated_state()["mediaId"], (session_state(), isolated_state())
        wait_for(lambda: bool((session_state() or {}).get("pip")), [sidebar], "picture-in-picture did not update the session")
        assert page_a.evaluate("document.pictureInPictureElement === document.querySelector('video')")
        assert card_state()["coverVisible"]
        wait_for(lambda: not card_state()["streamActive"], [sidebar], "picture-in-picture did not stop sidebar projection")
        assert not page_a.locator("video").evaluate("video => video.paused")

        page_a.evaluate("document.exitPictureInPicture()")
        wait_for(lambda: not bool((session_state() or {}).get("pip")), [sidebar], "picture-in-picture exit did not update the session")
        wait_for(lambda: card_state()["streamActive"], [sidebar], "leaving picture-in-picture did not restore projection")
        assert not card_state()["coverVisible"]
        assert not page_a.locator("video").evaluate("video => video.paused")

        page_a.bring_to_front()
        page_a.locator("#pip").click()
        page_b.bring_to_front()
        wait_for(lambda: page_a.evaluate("document.pictureInPictureElement !== null"), [page_a], "second picture-in-picture did not open")
        wait_for(lambda: bool((session_state() or {}).get("pip")), [page_a], "second picture-in-picture did not update the session")
        sidebar.close()
        page_b.bring_to_front()
        page_b.locator("#play").click()
        wait_for(lambda: page_a.locator("video").evaluate("video => video.paused"), [page_b], "B playback did not stop A")
        wait_for(lambda: page_a.evaluate("document.pictureInPictureElement === null"), [page_a], "B playback did not close A picture-in-picture")
        wait_for(lambda: not page_b.locator("video").evaluate("video => video.paused"), [page_b], "B playback did not resume after claiming ownership")
        page_a.bring_to_front()
        page_a.wait_for_timeout(300)
        assert page_a.locator("video").evaluate("video => video.paused")
        print("PASS single playback owner")
    finally:
        context.close()
        media_temp.cleanup()
