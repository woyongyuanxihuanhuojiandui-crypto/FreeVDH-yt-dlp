import json
import re
from pathlib import Path
from urllib.parse import urlsplit

PROGRESS = re.compile(r'^\s*(\d+(?:\.\d+)?)%')
PATH = re.compile(r'^file:(.+)$')

def parse_progress(line):
    match = PROGRESS.match(line.strip())
    return float(match.group(1)) if match else None

def parse_path(line):
    match = PATH.match(line.strip())
    return match.group(1) if match else None

def format_download_error(url, message):
    hostname = urlsplit(url).hostname
    bilibili = hostname == 'bilibili.com' or hostname.endswith(('.bilibili.com', '.bilibili.tv'))
    network_error = any(text in message.lower() for text in (
        'unable to download video data', 'connection reset', 'timed out', 'remote end closed', 'fragment'))
    return '媒体 CDN 连接失败' if bilibili and network_error else message

def download_args(executable, ffmpeg_dir, output_dir, temp_dir, url):
    return [executable, '--no-playlist', '--newline', '--no-colors', '--no-quiet',
            '--plugin-dirs', str(Path(ffmpeg_dir) / 'yt-dlp-plugins'),
            '--progress-template', 'download:%(progress._percent_str)s',
            '--print', 'after_move:file:%(filepath)s',
            '--ffmpeg-location', ffmpeg_dir, '-f', 'bv*+ba/b',
            '--remux-video', 'mp4',
            '-P', f'home:{output_dir}', '-P', f'temp:{temp_dir}',
            '-o', '%(title).150B [%(id)s].%(ext)s', url]

def stop_process_tree_args(pid):
    return ['taskkill', '/PID', str(pid), '/T', '/F']


def find_extension_ids(user_data):
    ids = set()
    for pattern in ('*/Preferences', '*/Secure Preferences'):
        for prefs in Path(user_data).glob(pattern):
            try:
                settings = json.loads(prefs.read_text(encoding='utf-8')).get('extensions', {}).get('settings', {})
                for extension_id, info in settings.items():
                    manifest = info.get('manifest')
                    if manifest is None and info.get('path'):
                        manifest = json.loads((Path(info['path']) / 'manifest.json').read_text(encoding='utf-8'))
                    if re.fullmatch('[a-p]{32}', extension_id) and manifest and manifest.get('name') in ('FreeVDH-yt-dlp', 'FreeVDH'):
                        ids.add(extension_id)
            except (OSError, ValueError, AttributeError):
                continue
    return sorted(ids)
