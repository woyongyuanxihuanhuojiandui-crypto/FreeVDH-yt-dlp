import unittest
from pathlib import Path


class SidebarRedockTest(unittest.TestCase):
    def test_toolbar_mount_reaches_sidebar_binding(self):
        source = (Path(__file__).parents[1] / 'content' / 'panel.js').read_text(encoding='utf-8')
        self.assertNotIn('(this.button_show_translate.onclick', source)
        self.assertIn('this.button_sidebar.onclick = () => o("sidebar")', source)


if __name__ == '__main__':
    unittest.main()
