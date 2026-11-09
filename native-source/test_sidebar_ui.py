import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SidebarUiTests(unittest.TestCase):
    def test_product_name_is_visible_across_extension(self):
        product = "FreeVDH-yt-dlp"
        manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        sidebar_ui = (ROOT / "content" / "sidebar-ui.js").read_text(encoding="utf-8")
        english = json.loads((ROOT / "_locales" / "en" / "messages.json").read_text(encoding="utf-8"))
        japanese = json.loads((ROOT / "_locales" / "ja" / "messages.json").read_text(encoding="utf-8"))
        app = (ROOT / "native-source" / "app.py").read_text(encoding="utf-8")
        ytdlp = (ROOT / "content" / "ytdlp-sidebar.js").read_text(encoding="utf-8")
        translations = (ROOT / "content" / "translate.js").read_text(encoding="utf-8")

        self.assertEqual(manifest["name"], product)
        self.assertEqual(manifest["version_name"], "1.0.0")
        self.assertEqual(manifest["action"]["default_title"], product)
        self.assertEqual(manifest["side_panel"]["default_title"], product)
        self.assertIn(f'button_show_translate: "协助翻译 {product}"', sidebar_ui)
        self.assertIn(f'private_browsing_warning: "{product} 尚未在隐私/无痕窗口中启用。', sidebar_ui)
        self.assertIn(product, english["private_browsing_warning"]["message"])
        self.assertIn(product, japanese["private_browsing_warning"]["message"])
        self.assertIn(f"We hope you're enjoying {product}", translations)
        self.assertIn(f"{product} is not enabled in a Private/Incognito windows", translations)
        self.assertIn(f"'{product} 安装'", app)
        self.assertIn(f"未检测到 {product} 桥接组件", ytdlp)
        for page in ("popup.html", "sidebar.html", "history.html"):
            html = (ROOT / "content" / page).read_text(encoding="utf-8")
            self.assertIn(f"<p>{product}: <span id=\"span_version\"></span></p>", html)

    def test_sidebar_loads_redesign_without_touching_popup(self):
        sidebar = (ROOT / "content" / "sidebar.html").read_text(encoding="utf-8")
        popup = (ROOT / "content" / "popup.html").read_text(encoding="utf-8")

        self.assertIn('src="sidebar-ui.js"', sidebar)
        self.assertNotIn('src="sidebar-ui.js"', popup)

    def test_page_media_control_is_registered_for_web_pages(self):
        manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        entry = next(
            item
            for item in manifest["content_scripts"]
            if "content/page-media-control.js" in item["js"]
        )

        self.assertEqual(entry["matches"], ["http://*/*", "https://*/*"])
        self.assertTrue(entry["all_frames"])

    def test_sidebar_reuses_freevdh_actions_and_has_requested_layout(self):
        script = (ROOT / "content" / "sidebar-ui.js").read_text(encoding="utf-8")

        for expected in (
            "sidebar-current-count",
            "sidebar-current-host",
            "sidebar-page-controls",
            "sidebar-card-header",
            "sidebar-card-select",
            "sidebar-quality-row",
            "sidebar-download-main",
            "sidebar-download-side",
            "sidebarStopDownload",
            "sidebarSetDownloadProgress",
            "sidebarSetDownloadError",
            "正在连接…",
            "sidebarSetDownloadComplete",
            "#action_copy",
            "#action_download",
            "#media_selector",
            "freeVDHYtdlpDownload",
            "通过 yt-dlp 下载",
        ):
            self.assertIn(expected, script)

        self.assertNotIn("jQuery", script)
        self.assertNotIn("cat-catch", script.lower())
        self.assertNotIn("sidebar-media-summary", script)
        self.assertNotIn("#downloaded { display: none !important; }", script)

    def test_page_control_protocol_covers_mockup_controls(self):
        script = (ROOT / "content" / "page-media-control.js").read_text(encoding="utf-8")

        self.assertIn('channel !== "freevdh-page-media"', script)
        for action in (
            '"state"',
            '"play"',
            '"pause"',
            '"speed"',
            '"pip"',
            '"fullscreen"',
            '"screenshot"',
            '"loop"',
            '"muted"',
            '"volume"',
            '"seek"',
        ):
            self.assertIn(action, script)

        self.assertNotIn("jQuery", script)
        self.assertNotIn("cat-catch", script.lower())

    def test_sidebar_uses_volume_without_a_separate_mute_option(self):
        script = (ROOT / "content" / "sidebar-ui.js").read_text(encoding="utf-8")

        self.assertIn('id="sidebar-volume"', script)
        self.assertNotIn('id="sidebar-muted"', script)
        self.assertNotIn('querySelector("#sidebar-muted")', script)

    def test_sidebar_matches_reference_control_structure(self):
        script = (ROOT / "content" / "sidebar-ui.js").read_text(encoding="utf-8")

        for expected in (
            'class="sidebar-timeline-row"',
            'class="sidebar-timeline-stack"',
            'class="sidebar-control-grid"',
            'class="sidebar-speed-row"',
            'class="sidebar-action-grid"',
            '<button id="sidebar-speed">倍速播放</button>',
            'id="sidebar-speed-value"',
            '<button id="sidebar-loop"',
            '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>',
            '<button id="sidebar-play" title="播放" aria-label="播放">',
            'class="sidebar-play-glyph"',
            'class="sidebar-pause-glyph"',
            'id="sidebar-pip"',
            'id="sidebar-fullscreen"',
            'id="sidebar-screenshot"',
            'id="sidebar-volume-zero"',
            'let lastVolume = 1',
            '? lastVolume : 0, updateControls)',
            'sidebar-download-main',
            'sidebar-download-side',
            '通过 yt-dlp 下载',
        ):
            self.assertIn(expected, script)

        speed_row = script.split('class="sidebar-speed-row"', 1)[1].split("</div>", 1)[0]
        self.assertLess(speed_row.index('id="sidebar-speed-value"'), speed_row.index('id="sidebar-speed"'))

        self.assertNotIn('id="sidebar-app-header"', script)
        self.assertNotIn('id="sidebar-loop" type="checkbox"', script)
        self.assertNotIn('id="action_preview"', script)

    def test_function_buttons_use_centered_blue_active_style(self):
        sidebar = (ROOT / "content" / "sidebar-ui.js").read_text(encoding="utf-8")
        page = (ROOT / "content" / "page-media-control.js").read_text(encoding="utf-8")

        self.assertIn("#sidebar-page-controls button {\n      display: grid; place-items: center;", sidebar)
        self.assertIn("border: 1px solid #0786ff; border-radius: 20px; color: #0786ff; background: #fff;", sidebar)
        self.assertIn(
            "#sidebar-page-controls button.active, #sidebar-page-controls button.playing, #sidebar-page-controls button:active { color: #fff; background: #0786ff; border-color: #49a4ff; }",
            sidebar,
        )
        self.assertIn("#box_combo > button.active, #box_combo > button:active { color: #fff; background: #0786ff; border-color: #49a4ff; }", sidebar)
        self.assertIn('controls.querySelector("#sidebar-pip").classList.toggle("active", state.pip);', sidebar)
        self.assertIn('controls.querySelector("#sidebar-fullscreen").classList.toggle("active", state.fullscreen);', sidebar)
        self.assertIn("fullscreen: document.fullscreenElement === media", page)

    def test_download_colors_and_light_diffuse_background(self):
        sidebar = (ROOT / "content" / "sidebar-ui.js").read_text(encoding="utf-8")

        self.assertIn("radial-gradient(circle at 8% 8%, #acd1ff 0, transparent 34%)", sidebar)
        self.assertIn("radial-gradient(circle at 42% 92%, #d9c7ff 0, transparent 42%)", sidebar)
        self.assertIn("#box_combo > #action_download, #box_combo > #action_ytdlp_menu { color: #fff; background: #0786ff; border-color: #49a4ff; }", sidebar)
        self.assertIn("#box_combo > #action_download.active, #box_combo > #action_download:active, #box_combo > #action_ytdlp_menu.active, #box_combo > #action_ytdlp_menu:active { color: #0786ff; background: #fff; border-color: #0786ff; }", sidebar)

    def test_sidebar_only_mode(self):
        sidebar = (ROOT / "content" / "sidebar-ui.js").read_text(encoding="utf-8")
        service = (ROOT / "service" / "freevdh-main.js").read_text(encoding="utf-8")

        self.assertIn("chrome.sidePanel.setOptions({ enabled: true });", service)
        self.assertIn("chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });", service)
        self.assertIn('chrome.action.setPopup({ popup: "" });', service)
        self.assertNotIn('menuSection("显示方式"', sidebar)
        self.assertNotIn('button_popup: "在弹出窗口显示"', sidebar)
        self.assertIn('input[name="settings_popup_size"], input[name="settings_dock"]', sidebar)

    def test_sidebar_menu_matches_glass_style(self):
        sidebar = (ROOT / "content" / "sidebar-ui.js").read_text(encoding="utf-8")

        self.assertIn("border-radius: 24px; background: #ffffff73;", sidebar)
        self.assertIn(".sidebar-menu-section { width: 100%; padding: 12px; border: 1px solid #fff9; border-radius: 18px;", sidebar)
        self.assertIn("background: #ffffff66; box-shadow: inset 0 1px #fff, 0 8px 20px #53606f14;", sidebar)
        self.assertIn("background: #fff; border: 1px solid #0786ff; border-radius: 12px;", sidebar)
        self.assertIn("border: 1px solid #fff9; border-radius: 18px; background: #ffffff66;", sidebar)

    def test_settings_page_matches_sidebar_glass_style(self):
        sidebar = (ROOT / "content" / "sidebar-ui.js").read_text(encoding="utf-8")

        self.assertIn("#sidebar-page-header, #main, #settings { position: relative; z-index: 1; }", sidebar)
        self.assertIn("body:has(#settings:not([hidden])) #sidebar-page-header { display: none; }", sidebar)
        self.assertIn("#settings { min-height: 0; margin: 14px; overflow: hidden;", sidebar)
        self.assertIn("#settings-toolbar { min-height: 60px; padding: 10px 14px;", sidebar)
        self.assertIn("#box_main > vbox { margin: 12px 0 0; padding: 14px 16px;", sidebar)
        self.assertIn("border: 1px solid #fff9; border-radius: 22px; background: #ffffff66;", sidebar)

    def test_page_projection_uses_a_local_media_stream(self):
        page = (ROOT / "content" / "page-media-control.js").read_text(encoding="utf-8")
        sidebar = (ROOT / "content" / "sidebar-ui.js").read_text(encoding="utf-8")

        for expected in (
            "captureStream()",
            "RTCPeerConnection",
            '"projection-offer"',
            '"projection-answer"',
            '"projection-stop"',
        ):
            self.assertIn(expected, page)

        for expected in (
            "srcObject",
            "RTCPeerConnection",
            "sidebar-stream-video",
            "使用画中画",
        ):
            self.assertIn(expected, sidebar)

        self.assertNotIn("freevdh-page-media-frame", page)
        self.assertNotIn("requestVideoFrameCallback", page)
        self.assertNotIn("freevdh-page-media-frame", sidebar)

    def test_ytdlp_download_can_be_stopped(self):
        script = (ROOT / "content" / "ytdlp-sidebar.js").read_text(encoding="utf-8")

        self.assertIn("{ action: 'stop' }", script)
        self.assertIn("message.state === 'stopped'", script)
        self.assertIn("sidebarSetDownloadProgress(undefined", script)

    def test_ytdlp_completed_history_is_persistent(self):
        sidebar = (ROOT / "content" / "sidebar-ui.js").read_text(encoding="utf-8")
        ytdlp = (ROOT / "content" / "ytdlp-sidebar.js").read_text(encoding="utf-8")

        self.assertIn("chrome.storage.local", sidebar)
        self.assertIn("sidebarYtdlpHistory", sidebar)
        self.assertIn("freeVDHYtdlpHistory", sidebar)
        self.assertIn("freeVDHYtdlpHistory.add", ytdlp)

    def test_playing_cards_use_session_retention(self):
        sidebar = (ROOT / "content" / "sidebar-ui.js").read_text(encoding="utf-8")

        self.assertIn("chrome.storage.session", sidebar)
        self.assertIn("freeVDHPlayingCards.add", sidebar)
        self.assertIn("freeVDHPlayingCards.remove", sidebar)
        self.assertIn("freeVDHPlayingCards.removeTab", sidebar)

    def test_panel_merges_retained_playing_cards(self):
        panel = (ROOT / "content" / "panel.js").read_text(encoding="utf-8")

        self.assertIn("freeVDHPlayingCards?.ready", panel)
        self.assertIn("freeVDHPlayingCards?.has", panel)
        self.assertIn("freeVDHPlayingCards?.has(x.meta.tab_id, D)", panel)


if __name__ == "__main__":
    unittest.main()
