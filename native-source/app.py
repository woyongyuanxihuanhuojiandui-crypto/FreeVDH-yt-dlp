import ctypes
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import uuid
import winreg
from pathlib import Path
from urllib.parse import urlsplit

from host import download_args, parse_path, parse_progress, find_extension_ids, format_download_error, stop_process_tree_args

NAME = 'com.vcatch.ytdlp'
ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).parent))

def send(data):
    data = json.dumps(data, ensure_ascii=False).encode('utf-8')
    sys.stdout.buffer.write(struct.pack('<I', len(data)) + data)
    sys.stdout.buffer.flush()

def receive():
    raw = sys.stdin.buffer.read(4)
    if len(raw) != 4: return
    return json.loads(sys.stdin.buffer.read(struct.unpack('<I', raw)[0]))

def downloads_dir():
    folder_id = uuid.UUID('{374DE290-123F-4565-9164-39C4925E467B}')
    out = ctypes.c_wchar_p()
    result = ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.create_string_buffer(folder_id.bytes_le), 0, None, ctypes.byref(out))
    if result: raise OSError('Cannot find Downloads folder')
    path = out.value
    ctypes.windll.ole32.CoTaskMemFree(out)
    return path

def run_host():
    request = receive()
    if request is None: return
    if request.get('action') == 'ping':
        send({'state': 'ready'})
        return
    if request.get('action') in ('open', 'show', 'delete'):
        try:
            path = Path(request['path'])
            if request['action'] == 'open':
                os.startfile(path)
            elif request['action'] == 'show':
                subprocess.Popen(['explorer.exe', '/select,', str(path)])
            else:
                path.unlink()
            send({'state': 'done'})
        except Exception as exc:
            send({'state': 'error', 'message': str(exc)})
        return
    url = request.get('url', '')
    if request.get('action') != 'download' or urlsplit(url).scheme not in ('http', 'https'):
        send({'state': 'error', 'message': '无效网页地址'})
        return
    try:
        with tempfile.TemporaryDirectory(prefix='vcatch-ytdlp-') as temp_dir:
            args = download_args(str(ROOT / 'yt-dlp.exe'), str(ROOT), downloads_dir(), temp_dir, url)
            proc = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    encoding='mbcs', errors='replace', creationflags=subprocess.CREATE_NO_WINDOW)
            stopped = threading.Event()
            def listen_for_stop():
                command = receive()
                if command and command.get('action') == 'stop':
                    stopped.set()
                    subprocess.run(stop_process_tree_args(proc.pid), stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
            threading.Thread(target=listen_for_stop, daemon=True).start()
            last = ''
            output_path = ''
            for line in proc.stdout:
                path = parse_path(line)
                progress = parse_progress(line)
                if path is not None:
                    output_path = path
                elif progress is not None:
                    send({'state': 'downloading', 'percent': progress})
                elif line.strip():
                    last = line.strip()
            code = proc.wait()
            if stopped.is_set():
                send({'state': 'stopped'})
            else:
                send({'state': 'done', 'path': output_path} if code == 0 else {
                    'state': 'error', 'message': format_download_error(url, last)})
    except Exception as exc:
        send({'state': 'error', 'message': str(exc)})

def install():
    import tkinter as tk
    from tkinter import messagebox
    root = tk.Tk(); root.withdraw()
    match = re.search(r'([a-p]{32})', Path(sys.executable).stem)
    extension_ids = [match.group(1)] if match else find_extension_ids(Path(os.environ['LOCALAPPDATA']) / 'Google/Chrome/User Data')
    if not extension_ids:
        messagebox.showerror('vcatch 安装', '未检测到 vcatch。请先在 Chrome 中加载扩展，再重新运行安装程序。')
        root.destroy(); return
    if not messagebox.askyesno('vcatch 安装', '是否安装 vcatch 桥接组件？'):
        return
    try:
        target = Path(os.environ['LOCALAPPDATA']) / 'vcatch-ytdlp'
        target.mkdir(parents=True, exist_ok=True)
        binary = target / 'vcatch-ytdlp.exe'
        shutil.copy2(sys.executable, binary)
        launcher = target / 'host.bat'
        launcher.write_text('@echo off\r\n"%~dp0vcatch-ytdlp.exe" --host\r\n', encoding='utf-8')
        manifest = target / 'host.json'
        manifest.write_text(json.dumps({'name': NAME, 'description': 'vcatch host', 'path': str(launcher), 'type': 'stdio', 'allowed_origins': ['chrome-extension://' + extension_id + '/' for extension_id in extension_ids]}), encoding='utf-8')
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r'Software\Google\Chrome\NativeMessagingHosts' + chr(92) + NAME) as key:
            winreg.SetValueEx(key, '', 0, winreg.REG_SZ, str(manifest))
        messagebox.showinfo('vcatch 安装', '安装完成。请回到 vcatch 侧栏并点击重新检测。')
    except Exception as exc:
        messagebox.showerror('vcatch 安装失败', str(exc))
    root.destroy()

if __name__ == '__main__':
    if '--host' in sys.argv:
        run_host()
    else:
        install()

