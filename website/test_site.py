from pathlib import Path
import re
import unittest

ROOT = Path(__file__).parent

class SiteSourceTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue((ROOT / "index.html").is_file(), "index.html is missing")
        self.html = (ROOT / "index.html").read_text(encoding="utf-8")

    def test_semantic_markers_and_copy(self):
        for marker in ("header", "nav", "main", "h1", "section", "ul", "ol", "details", "footer", "FreeVDH-yt-dlp", "网页视频，轻轻带回本地。", "发现视频", "预览与选择画质", "保存到本地", "安装教程", "常见问题", "下载 Windows 测试版"):
            self.assertIn(marker, self.html)

        self.assertEqual(self.html.count("下载 Windows 测试版"), 1)

    def test_no_script_or_spa(self):
        self.assertNotRegex(self.html, r"(?i)<script|id=[\"']app[\"']|javascript:")

    def test_repository_and_release_url(self):
        self.assertIn("https://github.com/woyongyuanxihuanhuojiandui-crypto/freevdh-yt-dlp", self.html)
        self.assertIn("https://github.com/woyongyuanxihuanhuojiandui-crypto/freevdh-yt-dlp/releases/download/v1.0.0/FreeVDH-yt-dlp.zip", self.html)

    def test_images_exist(self):
        for src in re.findall(r'<img\b[^>]*\bsrc=[\"\']([^\"\']+)', self.html):
            self.assertTrue((ROOT / src).is_file(), src)

    def test_styles_are_responsive_and_script_free(self):
        css = (ROOT / "styles.css").read_text(encoding="utf-8")
        for marker in ("max-width: 1200px", "@media (max-width: 760px)", "@media (prefers-reduced-motion: reduce)"):
            self.assertIn(marker, css)
        self.assertNotIn("expression(", css.lower())

    def test_steps_and_features_have_glass_card_layout(self):
        css = (ROOT / "styles.css").read_text(encoding="utf-8")
        self.assertEqual(self.html.count('class="step-icon"'), 3)
        for marker in (
            ".steps-section,\n.features-section {",
            ".step-icon {",
            ".steps li,\n.feature-grid li {",
            "backdrop-filter: blur(14px);",
        ):
            self.assertIn(marker, css)

if __name__ == "__main__":
    unittest.main()
