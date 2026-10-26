import queue
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import app_paths
from audio_engine import AudioSession

class ConsolidationTests(unittest.TestCase):
    def test_relative_folder_follows_app_location(self):
        with patch.object(app_paths, 'app_root', return_value=Path('C:/Apps/Recorder')):
            self.assertEqual(app_paths.resolve_recording_folder('Recordings'), Path('C:/Apps/Recorder/Recordings'))
            self.assertEqual(app_paths.stored_recording_folder('C:/Apps/Recorder/Recordings'), 'Recordings')

    def test_external_folder_remains_absolute(self):
        with patch.object(app_paths, 'app_root', return_value=Path('C:/Apps/Recorder')):
            self.assertEqual(app_paths.resolve_recording_folder('D:/Recordings'), Path('D:/Recordings'))

    def test_low_disk_refuses_capture_before_workers_start(self):
        with tempfile.TemporaryDirectory() as folder:
            session=AudioSession(queue.Queue())
            with patch('audio_engine.find_ffmpeg', return_value='ffmpeg.exe'), patch('audio_engine.shutil.disk_usage', return_value=Mock(free=100)):
                with self.assertRaisesRegex(RuntimeError, '256 MB'):
                    session.start(0,1,Path(folder),'MP3')
            self.assertEqual(session.state,'idle')
            self.assertFalse(list(Path(folder).iterdir()))

    def test_low_disk_during_call_signals_save_without_deleting_tracks(self):
        with tempfile.TemporaryDirectory() as folder:
            session=AudioSession(queue.Queue());session.state='recording';session._temporary=Path(folder)
            track=Path(folder)/'speaker.wav';track.write_bytes(b'preserve')
            with patch('audio_engine.shutil.disk_usage',return_value=Mock(free=100)),patch('audio_engine.time.monotonic',return_value=10):
                self.assertIn('128 MB',session.error_if_any())
            self.assertEqual(track.read_bytes(),b'preserve')
