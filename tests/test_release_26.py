import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import Mock, patch
import customtkinter as ctk
from recording_library import filter_records, search_key, update_record_metadata, read_json, atomic_json, list_recordings
from library_window import LibraryWindow
from ui_effects import cancel_root_callbacks

class Library26Tests(unittest.TestCase):
    def test_search_accents_and_note_and_sort(self):
        rows=[{'name':'Vợ Yêu.mp3','timestamp':'2026-10-27','duration':10,'metadata':{'favorite':True,'note':'Hẹn gặp Đặng'}},
              {'name':'An.mp3','timestamp':'2026-10-26','duration':30,'metadata':{}}]
        self.assertEqual(filter_records(rows,'vo yeu'),[rows[0]])
        self.assertEqual(filter_records(rows,'dang'),[rows[0]])
        self.assertEqual(filter_records(rows,starred=True),[rows[0]])
        self.assertEqual(filter_records(rows,order='Dài nhất'),[rows[1],rows[0]])
        self.assertEqual(filter_records(rows,order='Tên A–Z'),[rows[1],rows[0]])
        self.assertEqual(filter_records(rows,order='Cũ nhất'),[rows[1],rows[0]])

    def test_notes_preserve_session_information_and_audio(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'call.mp3';p.write_bytes(b'original audio')
            atomic_json(p.with_suffix('.mp3.json'),{'devices':{'microphone':'Mic'},'duration':5})
            update_record_metadata(p,note='Gọi lại',favorite=True)
            data=read_json(p.with_suffix('.mp3.json'))
            self.assertEqual(data['devices']['microphone'],'Mic')
            self.assertEqual(data['duration'],5)
            self.assertEqual(p.read_bytes(),b'original audio')
            p.unlink()
            with self.assertRaises(FileNotFoundError):update_record_metadata(p,note='No')

    def test_reopen_remembers_position_volume_and_filter_uses_cache(self):
        root=ctk.CTk();root.withdraw();root.recorder=Mock(state='idle');root.reduce_motion=True
        try:
            with tempfile.TemporaryDirectory() as folder:
                p=Path(folder)/'silence.wav'
                with wave.open(str(p),'wb') as f:
                    f.setparams((1,2,48000,0,'NONE',''));f.writeframes(b'\0'*96000*6)
                lib=LibraryWindow(root,folder,Mock());lib.withdraw()
                lib.select_path(p);lib.play();lib.player.toggle();lib.player.seek(2500);lib._volume(0)
                lib.destroy()
                data=read_json(p.with_suffix('.wav.json'))
                self.assertAlmostEqual(data['playback_position_ms'],2500,delta=150)
                lib=LibraryWindow(root,folder,Mock());lib.withdraw()
                self.assertEqual(lib.player.volume,0)
                lib.select_path(p);lib.play()
                self.assertGreaterEqual(lib.player.status()[1],2400)
                with patch('library_window.list_recordings',side_effect=AssertionError('Must use cache')):
                    lib.search.insert(0,'silence');lib.refresh(False)
                    self.assertEqual(len(lib.records),1)
                lib.toggle_favorite()
                self.assertTrue(read_json(p.with_suffix('.wav.json'))['favorite'])
                lib.destroy()
        finally:
            cancel_root_callbacks(root);root.destroy()
