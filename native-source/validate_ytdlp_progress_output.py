import subprocess
import tempfile
from pathlib import Path

from host import download_args, parse_progress


ROOT = Path(__file__).resolve().parents[3] / 'freevdh-ytdlp-work'
URL = 'https://www.bilibili.com/video/BV1UB4v67Exr'


with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
    directory = Path(directory)
    args = download_args(str(ROOT / 'yt-dlp.exe'), str(ROOT), str(directory), str(directory / 'temp'), URL)
    args[args.index('--plugin-dirs') + 1] = str(Path(__file__).parent / 'yt-dlp-plugins')
    args.insert(1, '--test')
    result = subprocess.run(args, capture_output=True, encoding='mbcs', errors='replace', timeout=60)
    progress = [value for line in result.stdout.splitlines() if (value := parse_progress(line)) is not None]
    print({'exitCode': result.returncode, 'progress': progress})
    assert result.returncode == 0
    assert progress
