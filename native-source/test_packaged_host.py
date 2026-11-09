import json
import queue
import struct
import subprocess
import threading
import unittest
from pathlib import Path


ROOT = Path(__file__).parent
EXECUTABLE = ROOT / 'package-dist' / 'freevdh-setup.exe'


class PackagedHostTest(unittest.TestCase):
    def test_ping(self):
        request = json.dumps({'action': 'ping'}).encode('utf-8')
        process = subprocess.Popen(
            [EXECUTABLE, '--host'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        output, _ = process.communicate(struct.pack('<I', len(request)) + request, timeout=30)
        size = struct.unpack('<I', output[:4])[0]
        self.assertEqual(json.loads(output[4:4 + size]), {'state': 'ready'})

    def test_bilibili_download_reports_progress(self):
        request = json.dumps({
            'action': 'download',
            'url': 'https://www.bilibili.com/video/BV1UB4v67Exr',
        }).encode('utf-8')
        process = subprocess.Popen(
            [EXECUTABLE, '--host'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        messages = queue.Queue()
        def read_messages():
            while raw := process.stdout.read(4):
                size = struct.unpack('<I', raw)[0]
                messages.put(json.loads(process.stdout.read(size)))
        threading.Thread(target=read_messages, daemon=True).start()
        process.stdin.write(struct.pack('<I', len(request)) + request)
        process.stdin.flush()
        received = []
        try:
            while not any(message.get('state') == 'downloading' for message in received):
                received.append(messages.get(timeout=15))
        except queue.Empty:
            pass
        finally:
            if process.poll() is None:
                stop = json.dumps({'action': 'stop'}).encode('utf-8')
                process.stdin.write(struct.pack('<I', len(stop)) + stop)
                process.stdin.flush()
            process.wait(timeout=30)
            process.stdin.close()
            process.stdout.close()
        for message in received:
            if message.get('state') == 'done':
                Path(message['path']).unlink()
        self.assertTrue(any(message.get('state') == 'downloading' for message in received), received)


if __name__ == '__main__':
    unittest.main()
