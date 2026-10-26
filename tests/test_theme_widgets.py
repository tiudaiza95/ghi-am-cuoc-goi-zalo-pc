import tempfile
import unittest
from unittest.mock import Mock, patch
import customtkinter as ctk
from pathlib import Path
import ui_layout
from library_window import LibraryWindow
from ui_effects import cancel_root_callbacks


class ThemeWidgetTests(unittest.TestCase):
    def test_real_widgets_build_and_switch_both_themes(self):
        # Isolated withdrawn widget tree: no device capture or live Zalo access.
        root = ctk.CTk()
        root.withdraw()
        try:
            with tempfile.TemporaryDirectory() as folder:
                for name in ('hide_to_tray', 'open_library', 'manual_confirm', 'stop_recording',
                             'toggle_auto_record', 'update_auto_hint', 'reload_devices', 'persist',
                             'change_format', 'choose_folder', 'open_folder', 'toggle_new_windows',
                             'toggle_autostart', 'open_zalo', 'diagnostics', 'on_close', 'export_logs', 'log', 'change_theme', 'toggle_motion', 'test_audio'):
                    setattr(root, name, Mock())
                root.auto_record = True
                root.appearance = 'Dark'
                root.folder = folder
                root.chosen_format = 'MP3'
                root.detector = Mock(allow_new_windows=True)
                root.recorder = Mock(state='idle')
                ctk.set_appearance_mode('Dark')
                with patch.object(ui_layout, 'autostart_enabled', return_value=False):
                    ui_layout.build_ui(root)
                library = LibraryWindow(root, Path(folder), Mock())
                library.withdraw()
                for mode in ('Dark', 'Light', 'Dark'):
                    ctk.set_appearance_mode(mode)
                    root.update_idletasks()
                    expected = '#1C1C1E' if mode == 'Dark' else '#FFFFFF'
                    from tkinter import ttk
                    self.assertEqual(ttk.Style(library).lookup('Recordings.Treeview', 'background'), expected)
                library.destroy()
        finally:
            cancel_root_callbacks(root)
            root.destroy()
            ctk.set_appearance_mode('Light')
