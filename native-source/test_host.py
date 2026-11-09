import unittest
import host
from host import download_args, parse_path, parse_progress, stop_process_tree_args
import json
import tempfile
from pathlib import Path

class HostTest(unittest.TestCase):
    def test_native_host_can_open_completed_file(self):
        source = (Path(__file__).parent / 'app.py').read_text(encoding='utf-8')
        self.assertIn("('open', 'show', 'delete')", source)
        self.assertIn('os.startfile(path)', source)

    def test_request(self):
        args = download_args('yt-dlp.exe', 'ffmpeg', 'C:/Downloads', 'C:/Temp/task', 'https://example.com/watch?v=1')
        self.assertEqual(args[-1], 'https://example.com/watch?v=1')
        self.assertIn('--no-playlist', args)
        self.assertNotIn('--cookies-from-browser', args)
        self.assertEqual(args[args.index('-f') + 1], 'bv*+ba/b')
        self.assertEqual(args[args.index('--remux-video') + 1], 'mp4')
        self.assertIn('--plugin-dirs', args)
        self.assertEqual(args[args.index('--plugin-dirs') + 1], str(Path('ffmpeg') / 'yt-dlp-plugins'))
        paths = [args[index + 1] for index, value in enumerate(args) if value == '-P']
        self.assertEqual(paths, ['home:C:/Downloads', 'temp:C:/Temp/task'])
        self.assertEqual(args[args.index('-o') + 1], '%(title).150B [%(id)s].%(ext)s')

    def test_stop_process_tree(self):
        self.assertEqual(stop_process_tree_args(42), ['taskkill', '/PID', '42', '/T', '/F'])

    def test_extension_discovery(self):
        with tempfile.TemporaryDirectory() as directory:
            extension = Path(directory) / 'FreeVDH extension'
            extension.mkdir()
            (extension / 'manifest.json').write_text(json.dumps({'name': 'FreeVDH'}))
            prefs = Path(directory) / 'Default' / 'Preferences'
            prefs.parent.mkdir()
            extension_ids = ['a' * 32]
            prefs.write_text(json.dumps({'extensions': {'settings': {extension_ids[0]: {'path': str(extension)}}}}))
            find_extension_ids = getattr(host, 'find_extension_ids', lambda _: [])
            self.assertEqual(find_extension_ids(Path(directory)), extension_ids)

    def test_progress(self):
        self.assertEqual(parse_progress(' 45.0%'), 45.0)
        self.assertIsNone(parse_progress('other'))

    def test_final_path(self):
        args = download_args('yt-dlp.exe', 'ffmpeg', 'C:/Downloads', 'C:/Temp/task', 'https://example.com/watch?v=1')
        self.assertIn('after_move:file:%(filepath)s', args)
        self.assertEqual(parse_path('file:C:/Downloads/video.mp4'), 'C:/Downloads/video.mp4')
        self.assertIsNone(parse_path(' 45.0%'))

    def test_bilibili_media_connection_error_is_clear(self):
        formatter = getattr(host, 'format_download_error', None)
        self.assertIsNotNone(formatter)
        self.assertEqual(
            formatter('https://www.bilibili.com/video/example', 'ERROR: unable to download video data: timed out'),
            '媒体 CDN 连接失败',
        )
        self.assertEqual(formatter('https://example.com/watch', 'original error'), 'original error')

if __name__ == '__main__':
    unittest.main()
