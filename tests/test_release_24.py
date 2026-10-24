import ast
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import main
import audio_engine


class Release24Tests(unittest.TestCase):
    def test_theme_color_pairs_are_flat_and_valid(self):
        root = Path(__file__).resolve().parents[1]
        for filename in ('main.py', 'library_window.py', 'ui_layout.py'):
            for node in ast.walk(ast.parse((root / filename).read_text(encoding='utf-8-sig'))):
                if isinstance(node, ast.Tuple) and node.elts and isinstance(node.elts[0], ast.Constant):
                    first = node.elts[0].value
                    if isinstance(first, str) and first.startswith('#'):
                        self.assertGreaterEqual(len(node.elts), 2)
                        for item in node.elts:
                            self.assertIsInstance(item, ast.Constant, (filename, node.lineno))
                            self.assertRegex(item.value, r'^#[0-9A-Fa-f]{6}$')

    def test_change_theme_persists_without_restarting_capture(self):
        app = Mock()
        with patch.object(main.ctk, 'set_appearance_mode') as change:
            main.Companion.change_theme(app, 'Tối')
            change.assert_called_once_with('Dark')
        self.assertEqual(app.appearance, 'Dark')
        app.persist.assert_called_once()
        app.recorder.stop.assert_not_called()

    def test_bundled_ffmpeg_preferred_without_system_path(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'tools').mkdir()
            ffmpeg = root / 'tools/ffmpeg.exe'
            ffmpeg.touch()
            with patch.object(audio_engine.sys, 'executable', str(root / 'app.exe')), \
                 patch.object(audio_engine.sys, 'frozen', True, create=True), \
                 patch.object(audio_engine.shutil, 'which', return_value=None):
                self.assertEqual(audio_engine.find_ffmpeg(), str(ffmpeg))

if __name__ == '__main__':
    unittest.main()

