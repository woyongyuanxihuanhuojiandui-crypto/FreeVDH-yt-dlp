import json
import subprocess
import sys
import types
import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SELECTOR = ROOT / 'injected' / 'bilibili-cdn.js'
EXTRACTOR = ROOT / 'injected' / 'bilibili.js'
PLUGIN = ROOT / 'native-source' / 'yt-dlp-plugins' / 'freevdh' / 'yt_dlp_plugins' / 'extractor' / 'bilibili_cdn.py'


class BilibiliCdnTest(unittest.TestCase):
    def select(self, media):
        self.assertTrue(SELECTOR.exists(), 'Bilibili CDN selector is missing')
        source = SELECTOR.read_text(encoding='utf-8')
        script = source + f"\nprocess.stdout.write(JSON.stringify(freeVDHBilibiliMediaUrl({json.dumps(media)})));"
        result = subprocess.run(['node', '-e', script], check=True, capture_output=True, text=True)
        return json.loads(result.stdout)

    def test_standard_https_backup_wins_over_special_port(self):
        selected = self.select({
            'base_url': 'https://upos-sz-mcdn.bilivideo.com:8082/video.m4s',
            'backup_url': [
                'http://cache.example/video.m4s',
                'https://upos-sz-mirroraliov.bilivideo.com/video.m4s',
            ],
        })
        self.assertEqual(selected, 'https://upos-sz-mirroraliov.bilivideo.com/video.m4s')

    def test_primary_url_remains_the_fallback(self):
        selected = self.select({'baseUrl': 'https://upos-sz-mirrorcos.bilivideo.com/video.m4s'})
        self.assertEqual(selected, 'https://upos-sz-mirrorcos.bilivideo.com/video.m4s')

    def test_playurl_request_includes_browser_fingerprint(self):
        source = SELECTOR.read_text(encoding='utf-8')
        script = source + '\nprocess.stdout.write(JSON.stringify(freeVDHBilibiliFingerprint()));'
        result = subprocess.run(['node', '-e', script], check=True, capture_output=True, text=True)
        fingerprint = json.loads(result.stdout)

        self.assertEqual(set(fingerprint), {'dm_img_list', 'dm_img_str', 'dm_cover_img_str', 'dm_img_inter'})
        self.assertEqual(json.loads(fingerprint['dm_img_inter'])['ds'], [])
        self.assertIn('...globalThis.freeVDHBilibiliFingerprint()', EXTRACTOR.read_text(encoding='utf-8'))

    def test_bilibili_extractor_plugin_rewrites_format_urls(self):
        self.assertTrue(PLUGIN.exists(), 'Bilibili yt-dlp plugin is missing')

        class BiliBiliIE:
            _VALID_URL = 'bilibili'

            def __init_subclass__(cls, **kwargs):
                cls.plugin_name = kwargs['plugin_name']

            def extract_formats(self, play_info):
                return [{'url': play_info['dash']['video'][0]['baseUrl']}]

            def _real_extract(self, url):
                return {'formats': self.extract_formats({'dash': {'audio': [], 'video': [{
                    'baseUrl': 'https://upos-sz-mcdn.bilivideo.com:8082/video.m4s?token=1',
                    'backupUrl': ['https://upos-sz-mirrorcoso1.bilivideo.com/video.m4s?token=2'],
                }]}})}

        yt_dlp = types.ModuleType('yt_dlp')
        extractors = types.ModuleType('yt_dlp.extractor')
        bilibili = types.ModuleType('yt_dlp.extractor.bilibili')
        bilibili.BiliBiliIE = BiliBiliIE
        modules = {'yt_dlp': yt_dlp, 'yt_dlp.extractor': extractors, 'yt_dlp.extractor.bilibili': bilibili}
        previous = {name: sys.modules.get(name) for name in modules}
        sys.modules.update(modules)
        try:
            spec = spec_from_file_location('freevdh_bilibili_cdn', PLUGIN)
            plugin = module_from_spec(spec)
            spec.loader.exec_module(plugin)
            info = plugin._FreeVDHBilibiliIE()._real_extract('https://www.bilibili.com/video/example')
        finally:
            for name, module in previous.items():
                if module is None:
                    del sys.modules[name]
                else:
                    sys.modules[name] = module

        self.assertEqual(
            info['formats'][0]['url'],
            'https://upos-sz-mirrorcoso1.bilivideo.com/video.m4s?token=2',
        )
        self.assertEqual(plugin._FreeVDHBilibiliIE.plugin_name, 'freevdh')


if __name__ == '__main__':
    unittest.main()
