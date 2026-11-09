import re
import unittest
from pathlib import Path


ROOT = Path(__file__).parent.parent


class ExtensionErrorNoiseTest(unittest.TestCase):
    def test_zod_probe_does_not_attempt_dynamic_execution(self):
        probe = re.compile(r'let (\w+) = Function;\s+return \(new \1\(""\), !0\);')
        offenders = [path for path in ROOT.rglob("*.js") if probe.search(path.read_text(encoding="utf-8"))]
        self.assertEqual([], offenders)

    def test_bilibili_non_video_pages_return_immediately(self):
        source = (ROOT / "injected" / "bilibili.js").read_text(encoding="utf-8")
        self.assertIn("if (!Le.test(e) && !ze.test(e)) return;", source)


if __name__ == "__main__":
    unittest.main()
