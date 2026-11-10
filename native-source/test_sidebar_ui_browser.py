import os
import subprocess
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright


extension = Path(__file__).resolve().parents[1]
frame_temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
frame_path = Path(frame_temp.name) / "frame.mp4"
subprocess.run([
    "ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc2=s=160x90:r=60:d=2",
    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(frame_path),
], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
frame_bytes = frame_path.read_bytes()


def serve_page(route):
    if route.request.url.endswith("/frame.mp4"):
        route.fulfill(content_type="video/mp4", body=frame_bytes)
    elif route.request.url.endswith("/frame"):
        route.fulfill(content_type="text/html", body='<video autoplay muted loop src="/frame.mp4"></video>')
    elif route.request.url.endswith("/control"):
        route.fulfill(content_type="text/html", body="<video></video>")
    else:
        route.fulfill(content_type="text/html", body='<iframe src="/frame"></iframe><iframe src="/control"></iframe>')


with sync_playwright() as playwright:
    context = playwright.chromium.launch_persistent_context(
        "",
        executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe",
        headless=True,
        ignore_default_args=["--disable-extensions"],
        args=["--enable-unsafe-extension-debugging"],
    )
    errors = []
    try:
        cdp = context.browser.new_browser_cdp_session()
        extension_id = cdp.send("Extensions.loadUnpacked", {"path": str(extension)})["id"]
        worker = context.service_workers[0] if context.service_workers else context.wait_for_event("serviceworker")

        page = context.new_page()
        page.route("http://vcatch.test/*", serve_page)
        page.goto("http://vcatch.test/")
        page.wait_for_timeout(300)
        web_tab_id = worker.evaluate("async () => (await chrome.tabs.query({url: 'http://vcatch.test/*'}))[0].id")
        state = worker.evaluate("""async () => {
          const [tab] = await chrome.tabs.query({url: 'http://vcatch.test/*'});
          const frames = await chrome.webNavigation.getAllFrames({tabId: tab.id});
          const frame = frames.find(item => item.url.endsWith('/frame'));
          return chrome.tabs.sendMessage(tab.id, {channel: 'vcatch-page-media', action: 'state'}, {frameId: frame.frameId});
        }""")
        assert state["count"] == 1, state
        assert "frame" not in state, state
        worker.evaluate("""async () => {
          const [tab] = await chrome.tabs.query({url: 'http://vcatch.test/*'});
          const frames = await chrome.webNavigation.getAllFrames({tabId: tab.id});
          const frame = frames.find(item => item.url.endsWith('/control'));
          for (const [action, value] of [['muted', true], ['volume', 0.25], ['speed', 1.5]])
            await chrome.tabs.sendMessage(tab.id, {channel: 'vcatch-page-media', action, value}, {frameId: frame.frameId});
        }""")
        media_state = page.frame_locator('iframe[src="/control"]').locator("video").evaluate("video => ({muted: video.muted, volume: video.volume, speed: video.playbackRate})")
        assert media_state == {"muted": True, "volume": 0.25, "speed": 1.5}, media_state

        sidebar = context.new_page()
        sidebar.on("pageerror", lambda error: errors.append(str(error)))
        sidebar.goto(f"chrome-extension://{extension_id}/content/sidebar.html")
        sidebar.locator("#sidebar-page-header").wait_for()
        page.bring_to_front()
        sidebar.wait_for_timeout(700)
        sidebar.evaluate("""async () => {
          const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
          const media = document.querySelector('#main').shadowRoot.querySelector('#media');
          const current = document.createElement('com-media');
          const other = document.createElement('com-media');
          current.meta = {tab_id: tab.id};
          other.meta = {tab_id: tab.id + 1};
          for (const card of [current, other]) {
            const menu = card.shadowRoot.querySelector('com-media-discovered').shadowRoot.querySelector('#menu_options');
            menu.invalidateState([{id: 'menu_do_details', text: '详情', enabled: true, onclick: () => {}}]);
          }
          media.append(current, other);
        }""")
        sidebar.wait_for_timeout(800)

        cards = sidebar.locator("com-main").locator("#media > com-media")
        assert cards.count() == 2
        assert sidebar.locator("#sidebar-current-count").text_content() == "当前页面 · 1", errors
        assert not cards.nth(0).evaluate("card => card.classList.contains('sidebar-collapsed')")
        assert cards.nth(1).evaluate("card => card.classList.contains('sidebar-collapsed')")
        assert cards.nth(0).locator(".sidebar-card-header").count() == 1
        assert cards.nth(0).locator(".sidebar-card-select").is_checked()
        assert not cards.nth(1).locator(".sidebar-card-select").is_checked()
        assert cards.nth(0).locator("#sidebar-page-controls").count() == 1
        assert cards.nth(0).locator("#sidebar-page-controls").evaluate("node => getComputedStyle(node).zoom") == "1"
        assert cards.nth(0).locator("#vbox_right").evaluate("node => getComputedStyle(node).zoom") == "1"
        sidebar.set_viewport_size({"width": 438, "height": 900})
        sidebar.wait_for_timeout(100)
        content_box = cards.nth(0).locator(".sidebar-card-content").bounding_box()
        control_boxes = cards.nth(0).locator(".sidebar-action-grid > *").evaluate_all(
            "items => items.map(item => ({left: item.getBoundingClientRect().left, right: item.getBoundingClientRect().right, top: item.getBoundingClientRect().top}))"
        )
        assert all(
            item["left"] >= content_box["x"] - 1
            and item["right"] <= content_box["x"] + content_box["width"] + 1
            for item in control_boxes
        ), (content_box, cards.nth(0).locator("#sidebar-page-controls").bounding_box(), control_boxes)
        assert len({round(item["top"]) for item in control_boxes}) == 2, control_boxes
        sidebar.set_viewport_size({"width": 455, "height": 900})
        sidebar.wait_for_timeout(100)
        assert cards.nth(0).locator(".sidebar-speed-row").evaluate("row => getComputedStyle(row).display") == "grid"
        speed_button = cards.nth(0).locator("#sidebar-speed")
        assert speed_button.text_content() == "倍速播放"
        speed_button.evaluate("button => button.click()")
        page.wait_for_function("document.querySelector('iframe[src=\"/frame\"]').contentDocument.querySelector('video').playbackRate === 2", timeout=2000)
        sidebar.wait_for_timeout(600)
        assert speed_button.evaluate("button => button.classList.contains('active')")
        speed_button.evaluate("button => button.click()")
        page.wait_for_function("document.querySelector('iframe[src=\"/frame\"]').contentDocument.querySelector('video').playbackRate === 1", timeout=2000)
        sidebar.wait_for_timeout(600)
        assert not speed_button.evaluate("button => button.classList.contains('active')")
        header_box = sidebar.locator("#sidebar-page-header").bounding_box()
        assert 91 <= header_box["height"] <= 93, header_box
        logo = sidebar.locator("#sidebar-page-header > img")
        logo_box = logo.bounding_box()
        assert logo.get_attribute("src") == "/bitmaps/logo-128-nooutline.png"
        assert 42 <= logo_box["width"] <= 44 and 42 <= logo_box["height"] <= 44, logo_box
        count_style = sidebar.locator("#sidebar-current-count").evaluate(
            "node => ({fontSize: getComputedStyle(node).fontSize, whiteSpace: getComputedStyle(node).whiteSpace})"
        )
        assert count_style == {"fontSize": "18px", "whiteSpace": "nowrap"}, count_style
        header_actions = sidebar.locator("#sidebar-page-actions > button")
        assert header_actions.count() == 3
        assert sidebar.locator("#sidebar-page-refresh").text_content().strip() == "↻"
        assert sidebar.locator("#sidebar-page-refresh svg").count() == 0
        action_boxes = header_actions.evaluate_all(
            "buttons => buttons.map(button => ({width: button.getBoundingClientRect().width, height: button.getBoundingClientRect().height, top: button.getBoundingClientRect().top}))"
        )
        assert all(31 <= item["width"] <= 33 and 31 <= item["height"] <= 33 for item in action_boxes), action_boxes
        assert max(item["top"] for item in action_boxes) - min(item["top"] for item in action_boxes) <= 1, action_boxes
        sidebar.locator("#sidebar-page-more").click()
        toolbar = sidebar.locator("body > #toolbar")
        assert toolbar.is_visible()
        assert toolbar.locator(".sidebar-menu-heading").all_text_contents() == ["媒体与下载", "帮助"]
        menu_labels = {
            "#button_show_nomedia": "找不到视频？",
            "#button_show_history": "下载历史",
            "#button_show_dir": "打开下载文件夹",
            "#button_trash": "清除已完成下载",
            "#button_show_translate": "协助翻译 vcatch",
            "#button_help": "帮助",
            "#button_debug": "调试",
            "#toolbar_button_settings": "设置",
        }
        for selector, label in menu_labels.items():
            actual = toolbar.locator(selector).text_content().strip()
            assert actual == label, (selector, actual, label, errors)
        menu_text = toolbar.text_content()
        assert not any(text in menu_text for text in ["视频录制", "录制webRTC", "数据发送", "在线合并", "深度搜索"])
        toolbar_box = toolbar.bounding_box()
        assert 269 <= toolbar_box["width"] <= 271, toolbar_box
        assert 71 <= toolbar_box["y"] <= 73, toolbar_box
        assert 13 <= 455 - toolbar_box["x"] - toolbar_box["width"] <= 15, toolbar_box
        menu_style = toolbar.evaluate(
            "node => ({borderRadius: getComputedStyle(node).borderRadius, boxShadow: getComputedStyle(node).boxShadow, background: getComputedStyle(node).backgroundColor})"
        )
        assert menu_style["borderRadius"] == "24px", menu_style
        assert menu_style["boxShadow"] != "none", menu_style
        assert menu_style["background"] != "rgba(0, 0, 0, 0)", menu_style
        if screenshot_dir := os.environ.get("VCATCH_UI_SCREENSHOT_DIR"):
            Path(screenshot_dir).mkdir(parents=True, exist_ok=True)
            sidebar.screenshot(path=str(Path(screenshot_dir) / "three-dot-menu-455.png"))
        sidebar.keyboard.press("Escape")
        assert not toolbar.is_visible()
        sidebar.locator("#sidebar-page-more").click()
        toolbar.locator("#toolbar_button_settings").click()
        assert not toolbar.is_visible()
        settings = sidebar.locator("#settings")
        assert settings.is_visible()
        assert not sidebar.locator("#sidebar-page-header").is_visible()
        assert not sidebar.locator("#main").is_visible()
        assert settings.locator('input[name="settings_popup_size"], input[name="settings_dock"]').count() == 0
        settings_box = settings.bounding_box()
        settings_toolbar_box = settings.locator("#settings-toolbar").bounding_box()
        first_settings_card = settings.locator("#box_main > .roundedbox").first
        first_card_box = first_settings_card.bounding_box()
        assert 13 <= settings_box["x"] <= 15 and 13 <= settings_box["y"] <= 15, settings_box
        assert settings_toolbar_box["y"] <= settings_box["y"] + 1, (settings_box, settings_toolbar_box)
        assert first_settings_card.is_visible() and first_card_box["y"] > settings_toolbar_box["y"], first_card_box
        assert settings.evaluate("node => node.scrollWidth <= node.clientWidth")
        if screenshot_dir := os.environ.get("VCATCH_UI_SCREENSHOT_DIR"):
            sidebar.screenshot(path=str(Path(screenshot_dir) / "settings-page-455.png"))
        settings_translations = {
            "appearance_title": "外观",
            "back": "返回",
            "bad_download_subdirectory_warning": "指定的子目录无效。",
            "behavior_title": "行为",
            "change_browser_download_directory": "更改浏览器下载目录",
            "change_saveas_setting": "更改设置",
            "controls_title": "控制",
            "copy_to_clipboard": "复制信息到剪贴板",
            "download_directory_description": "视频将下载到浏览器默认下载目录。你也可以指定子目录。特定网站的下载目录可通过智能命名工具设置。",
            "download_directory_title": "下载目录",
            "download_subdirectory": "下载子目录",
            "download_title": "下载",
            "enable_history": "启用历史记录",
            "font_size_default": "默认",
            "font_size_large": "大",
            "font_size_title": "文字大小",
            "font_size_verylarge": "特大",
            "history_limit": "X 天后清除下载历史",
            "leave_review_button": "撰写评价",
            "leave_review_description": "希望你喜欢 vcatch :) 可以在扩展网站上留下好评吗？",
            "max_parallel_downloads": "最大并发下载数",
            "media_discovered_ordering_title": "媒体排序方式",
            "order_media_by_newest": "最新优先",
            "order_media_by_oldest": "最早优先",
            "order_media_smart": "智能（推荐）",
            "prefer_mkv": "尽可能下载为 MKV",
            "prefer_original_audio": "优先原始音轨",
            "prefered_quality": "首选视频画质",
            "prefered_quality_1080p": "1080p（默认推荐）",
            "prefered_quality_480p": "480p（下载更快，分辨率更低）",
            "prefered_quality_720p": "720p（下载快，低分辨率）",
            "prefered_quality_highest": "最高画质（下载较慢，分辨率高）",
            "preview_mode_image": "图片",
            "preview_mode_none": "禁用",
            "preview_mode_title": "媒体预览",
            "preview_mode_video": "短视频预览",
            "private_browsing_button": "更改隐私浏览设置",
            "private_browsing_notifications": "显示隐私下载通知",
            "private_browsing_title": "隐私浏览",
            "private_browsing_warning": "vcatch 尚未在隐私/无痕窗口中启用。需要手动开启该选项（并非必需）。",
            "reset_settings": "重置设置",
            "restart_addon": "重新加载扩展",
            "saveas_detected_warning": "检测到浏览器会在下载完成后显示“另存为”对话框，建议在浏览器设置中关闭该选项。",
            "settings_history_title": "历史记录",
            "show_in_context_menu": "从页面右键菜单访问命令",
            "show_notification": "下载完成时显示通知",
            "theme_dark": "深色",
            "theme_light": "浅色",
            "theme_system": "跟随系统",
            "theme_title": "主题",
            "throttle_youtube": "限制 YouTube 下载速度（速度较慢，但更不容易被阻止）",
            "transient_history_description": "在面板中显示已完成下载",
            "version_title": "版本",
        }
        read_settings_translations = """(settings, keys) => Object.fromEntries(keys.map(key => {
          const node = settings.shadowRoot.querySelector(`[data-sidebar-i18n="${key}"], [data-i18n="${key}"]`);
          return [key, node.textContent.trim()];
        }))"""
        settings_values = sidebar.locator("#settings").evaluate(read_settings_translations, list(settings_translations))
        assert settings_values == settings_translations, settings_values
        assert sidebar.locator("#settings").locator("#button_smartnaming").text_content().strip() == "智能命名"
        sidebar.evaluate("document.documentElement.dispatchEvent(new Event('persistent-changed'))")
        settings_values = sidebar.locator("#settings").evaluate(read_settings_translations, list(settings_translations))
        assert settings_values == settings_translations, settings_values
        settings.locator("#button_back").click()
        assert sidebar.locator("#main").is_visible()
        assert sidebar.locator("#sidebar-page-header").is_visible()
        assert float(cards.nth(0).evaluate("card => getComputedStyle(card).borderRadius.replace('px', '')")) >= 12
        discovered = cards.nth(0).locator("com-media-discovered")
        assert discovered.locator(".sidebar-quality-row").count() == 1
        assert discovered.locator(".sidebar-media-summary").count() == 0
        controls_box = cards.nth(0).locator("#sidebar-page-controls").bounding_box()
        quality_box = discovered.locator(".sidebar-quality-row").bounding_box()
        assert 14 <= quality_box["y"] - controls_box["y"] - controls_box["height"] <= 18, (controls_box, quality_box)
        selector_box = discovered.locator("#media_selector").bounding_box()
        selector_menu_box = discovered.locator("#media_selector").locator("#menu_options").bounding_box()
        assert selector_menu_box["width"] >= selector_box["width"] * 0.9
        assert selector_menu_box["height"] >= 42
        assert discovered.locator("#action_copy").is_visible()
        assert discovered.locator("#action_download").is_visible()
        assert discovered.locator("#action_ytdlp").count() == 0
        ytdlp_menu_button = discovered.locator("#action_ytdlp_menu")
        assert ytdlp_menu_button.is_visible()
        split_widths = discovered.locator("#action_download, #action_ytdlp_menu").evaluate_all(
            "buttons => buttons.map(button => parseFloat(getComputedStyle(button).width))"
        )
        assert split_widths == [88, 38], split_widths
        split_heights = discovered.locator("#action_download, #action_ytdlp_menu").evaluate_all(
            "buttons => buttons.map(button => parseFloat(getComputedStyle(button).height))"
        )
        assert split_heights == [42, 42], split_heights
        buttons = discovered.locator("#box_combo > button").evaluate_all(
            "buttons => buttons.map(button => { const r = button.getBoundingClientRect(); return {center: r.y + r.height / 2, left: r.left, right: r.right}; })"
        )
        assert max(b["center"] for b in buttons) - min(b["center"] for b in buttons) < 1, buttons
        assert abs(buttons[-2]["right"] - buttons[-1]["left"]) <= 1, buttons
        ytdlp_menu_button.click()
        ytdlp_menu = discovered.locator(".sidebar-ytdlp-menu")
        assert ytdlp_menu.is_visible()
        assert ytdlp_menu.locator("button").all_text_contents() == ["通过 yt-dlp 下载"]
        assert ytdlp_menu.evaluate("menu => getComputedStyle(menu).borderRadius") == "14px"
        menu_text_style = ytdlp_menu.locator("button").evaluate(
            "button => ({color: getComputedStyle(button).color, fontSize: getComputedStyle(button).fontSize, fontWeight: getComputedStyle(button).fontWeight})"
        )
        assert menu_text_style == {"color": "rgb(23, 24, 27)", "fontSize": "16px", "fontWeight": "600"}, menu_text_style
        if screenshot_dir := os.environ.get("VCATCH_UI_SCREENSHOT_DIR"):
            output = Path(screenshot_dir)
            output.mkdir(parents=True, exist_ok=True)
            for width in (420, 455):
                sidebar.set_viewport_size({"width": width, "height": 900})
                cards.nth(0).screenshot(path=str(output / f"sidebar-menu-{width}.png"))
                ytdlp_menu.evaluate("menu => menu.hidden = false")
                menu_box = ytdlp_menu.bounding_box()
                buttons_box = discovered.locator("#box_combo").bounding_box()
                sidebar.screenshot(path=str(output / f"download-actions-{width}.png"), clip={
                    "x": menu_box["x"] - 6, "y": menu_box["y"] - 6,
                    "width": menu_box["width"] + 12,
                    "height": buttons_box["y"] + buttons_box["height"] - menu_box["y"] + 12,
                })
                ytdlp_menu.evaluate("menu => menu.hidden = true")
                cards.nth(0).screenshot(path=str(output / f"sidebar-closed-{width}.png"))
                ytdlp_menu.evaluate("menu => menu.hidden = false")
        cards.nth(0).dispatch_event("mouseleave")
        assert not ytdlp_menu.is_visible()
        frame_state = worker.evaluate("""async () => {
          const [tab] = await chrome.tabs.query({url: 'http://vcatch.test/*'});
          const frames = await chrome.webNavigation.getAllFrames({tabId: tab.id});
          const frame = frames.find(item => item.url.endsWith('/frame'));
          return chrome.tabs.sendMessage(tab.id, {channel: 'vcatch-page-media', action: 'state'}, {frameId: frame.frameId});
        }""")
        assert frame_state["count"] == 1, (frame_state, errors)
        assert cards.nth(0).locator("com-media-preview").locator(".sidebar-stream-video").count() == 1
        assert cards.nth(0).locator("com-media-preview").locator(".sidebar-page-frame").count() == 0
        assert discovered.locator("#box_combo > button").evaluate_all(
            "buttons => buttons.map(button => button.id)"
        ) == ["action_copy", "action_download", "action_ytdlp_menu"]
        assert discovered.locator("#action_download_audio").count() == 0
        action_menu = discovered.locator("#sidebar-action-menu")
        assert action_menu.count() == 1
        assert not action_menu.is_visible()
        assert discovered.locator("#action_download").evaluate("button => Boolean(button.oncontextmenu)")
        menu_values = action_menu.locator("select option").evaluate_all("options => options.map(option => option.value)")
        assert "menu_do_details" in menu_values
        assert "sidebar_download_as" in menu_values
        assert "sidebar_download_audio" in menu_values
        action_icon_widths = discovered.locator("#action_ytdlp_menu > svg").evaluate_all(
            "icons => icons.map(icon => icon.getBoundingClientRect().width)"
        )
        assert action_icon_widths and min(action_icon_widths) >= 12, action_icon_widths
        cards.nth(0).locator("#sidebar-loop").evaluate("button => button.click()")
        sidebar.wait_for_timeout(100)
        assert not page.frame_locator('iframe[src="/frame"]').locator("video").evaluate("video => video.loop")
        cards.nth(0).locator("#sidebar-loop").evaluate("button => button.click()")
        sidebar.wait_for_timeout(100)
        assert page.frame_locator('iframe[src="/frame"]').locator("video").evaluate("video => video.loop")
        cards.nth(1).locator(".sidebar-card-header").click()
        assert cards.nth(0).evaluate("card => card.classList.contains('sidebar-collapsed')")
        assert not cards.nth(1).evaluate("card => card.classList.contains('sidebar-collapsed')")
        assert not cards.nth(0).locator(".sidebar-card-select").is_checked()
        assert cards.nth(1).locator(".sidebar-card-select").is_checked()
        cards.nth(1).locator(".sidebar-card-header").click()
        assert cards.nth(1).evaluate("card => card.classList.contains('sidebar-collapsed')")
        assert not cards.nth(1).locator(".sidebar-card-select").is_checked()
        cards.evaluate_all("cards => cards.forEach(card => card.shadowRoot.querySelector('com-dismiss-button').onclick = () => card.remove())")
        sidebar.locator("#sidebar-page-clear").click()
        assert cards.count() == 1
        assert cards.nth(0).evaluate("card => card.meta.tab_id") == web_tab_id + 1
        sidebar.evaluate("""tabId => {
          const media = document.querySelector('#main').shadowRoot.querySelector('#media');
          const card = document.createElement('com-media');
          card.meta = {tab_id: tabId};
          const menu = card.shadowRoot.querySelector('com-media-discovered').shadowRoot.querySelector('#menu_options');
          menu.invalidateState([{id: 'menu_do_details', text: '详情', enabled: true, onclick: () => {}}]);
          media.append(card);
        }""", arg=web_tab_id)
        sidebar.wait_for_function("""tabId => {
          const card = [...document.querySelector('#main').shadowRoot.querySelector('#media').querySelectorAll('com-media')]
            .find(item => item.meta?.tab_id === tabId);
          return card?.dataset.sidebarEnhanced;
        }""", arg=web_tab_id)
        projection_card = cards.last
        if projection_card.evaluate("card => card.classList.contains('sidebar-collapsed')"):
            projection_card.locator(".sidebar-card-header").click()
        sidebar.wait_for_function("""tabId => {
          const card = [...document.querySelector('#main').shadowRoot.querySelector('#media').querySelectorAll('com-media')]
            .find(item => item.meta?.tab_id === tabId);
          return card?.sidebarStateReady;
        }""", arg=web_tab_id)
        frame = page.frame_locator('iframe[src="/frame"]')
        frame.locator("body").evaluate("""body => {
          const video = body.querySelector('video');
          video.pause();
          const button = document.createElement('button');
          button.id = 'projection-play';
          button.onclick = () => video.play();
          body.append(button);
        }""")
        page.bring_to_front()
        frame.locator("#projection-play").click()
        for _ in range(20):
            session = worker.evaluate("async () => (await chrome.storage.session.get('vcatchPlaybackSession')).vcatchPlaybackSession")
            if session and session.get("tabId") == web_tab_id:
                break
            page.wait_for_timeout(100)
        else:
            raise AssertionError("source page did not claim playback")
        page_b = context.new_page()
        page_b.goto("about:blank")
        page_b.bring_to_front()
        sidebar.wait_for_function("""tabId => {
          const card = [...document.querySelector('#main').shadowRoot.querySelector('#media').querySelectorAll('com-media')]
            .find(item => item.meta?.tab_id === tabId);
          return card.sidebarStreamVideo.videoWidth > 0;
        }""", arg=web_tab_id)
        sidebar.evaluate("""() => {
          const sendMessage = chrome.tabs.sendMessage;
          Object.defineProperty(chrome.tabs, 'sendMessage', {
            configurable: true,
            value: (...args) => args[1]?.action === 'projection-stop'
              ? setTimeout(() => sendMessage(...args), 300)
              : sendMessage(...args),
          });
        }""")
        page.bring_to_front()
        page.wait_for_timeout(50)
        page_b.bring_to_front()
        page_b.wait_for_timeout(800)
        assert projection_card.evaluate("card => card.sidebarStreamVideo.videoWidth") > 0
        assert errors == [], errors
        print("PASS sidebar UI")
    finally:
        context.close()
        frame_temp.cleanup()
