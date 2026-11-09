import json, os, pathlib, sys, tempfile, types, unittest
from unittest.mock import patch
import app

class InstallTest(unittest.TestCase):
    def test_installer_registers_host_for_extension(self):
        extension_ids = ['a' * 32, 'b' * 32]
        class Root:
            def withdraw(self): pass
            def destroy(self): pass
        class Key:
            def __enter__(self): return self
            def __exit__(self, *args): pass
        tkinter = types.ModuleType('tkinter')
        tkinter.Tk = Root
        tkinter.simpledialog = types.SimpleNamespace(askstring=lambda *args: self.fail('installer asked for an extension ID'))
        tkinter.messagebox = types.SimpleNamespace(askyesno=lambda *args: True, showinfo=lambda *args: None, showerror=lambda *args: self.fail(str(args)))
        values = []
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'LOCALAPPDATA':tmp}), patch.object(sys, 'executable', str(pathlib.Path(tmp)/'setup.exe')), patch.dict(sys.modules, {'tkinter':tkinter}), patch.object(app, 'find_extension_ids', return_value=extension_ids), patch.object(app.shutil, 'copy2'), patch.object(app.winreg, 'CreateKey', return_value=Key()), patch.object(app.winreg, 'SetValueEx', side_effect=lambda *args: values.append(args)):
            app.install()
            manifest = json.loads((pathlib.Path(tmp)/'FreeVDH-ytdlp'/'host.json').read_text())
            self.assertEqual(manifest['allowed_origins'], ['chrome-extension://'+extension_id+'/' for extension_id in extension_ids])
            self.assertTrue((pathlib.Path(tmp)/'FreeVDH-ytdlp'/'host.bat').exists())
            self.assertEqual(values[0][-1], str(pathlib.Path(tmp)/'FreeVDH-ytdlp'/'host.json'))

if __name__ == '__main__': unittest.main()
