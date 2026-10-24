import json
import queue
import tempfile
import unittest
import wave
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch
import main
from audio_engine import AudioSession
from audio_player import AudioPlayer
from zalo_detector import WindowInfo, ZaloCallDetector
import test_app_flow


class HandoverTests(unittest.TestCase):
    def test_ring_gap_answer_keeps_one_capture_and_updates_name(self):
        app = test_app_flow.AppFlowTests().app('recording')
        app.current_call_key = 1
        app.current_caller_name = ''
        app.lost_call_since = None
        app.detector = ZaloCallDetector()
        ring = WindowInfo(1, 10, 'Zalo', 'x', 400, 600, 'ZaloCall.exe')
        answer = WindowInfo(2, 11, 'Cuộc gọi đến - Vợ Yêu', 'x', 500, 600, 'Zalo.exe')
        app.detector.update([ring], True)
        app.detector.update([ring], True)
        app.detector.update([ring], True)
        for now, windows in [(10, []), (11, []), (12, []), (13, [answer]), (14, [answer]), (15, [answer])]:
            with patch.object(main, 'zalo_processes', return_value={10: 'Zalo.exe'}), \
                 patch.object(main, 'windows_for_pids', return_value=windows), \
                 patch.object(main.time, 'monotonic', return_value=now):
                main.Companion._poll(app)
        app.stop_recording.assert_not_called()
        app._handle_signal.assert_not_called()
        self.assertEqual(app.current_call_key, 2)
        self.assertEqual(app.current_caller_name, 'Vợ Yêu')
        app.recorder.set_caller_name.assert_called_once_with('Vợ Yêu')
        self.assertFalse(app.pending_signals)

    def test_explicit_end_stops_without_grace(self):
        app = test_app_flow.AppFlowTests().app('recording')
        app.current_call_key = 1
        app.lost_call_since = None
        ended = WindowInfo(1, 10, 'Cuộc gọi kết thúc', 'x', 500, 600, 'ZaloCall.exe')
        with patch.object(main, 'zalo_processes', return_value={10: 'Zalo.exe'}), \
             patch.object(main, 'windows_for_pids', return_value=[ended]):
            main.Companion._poll(app)
        app.stop_recording.assert_called_once()

    def test_different_contact_does_not_take_over(self):
        app = test_app_flow.AppFlowTests().app('recording')
        app.current_call_key = 1
        app.current_caller_name = 'An'
        app.lost_call_since = 1
        other = WindowInfo(2, 10, 'Cuộc gọi đến - Bình', 'x', 500, 600, 'Zalo.exe')
        app.detector.update.return_value = ([], {2})
        with patch.object(main, 'zalo_processes', return_value={10: 'Zalo.exe'}), \
             patch.object(main, 'windows_for_pids', return_value=[other]), \
             patch.object(main.time, 'monotonic', return_value=10):
            main.Companion._poll(app)
        self.assertEqual(app.current_call_key, 1)
        app.stop_recording.assert_called_once()

    def test_name_update_preserves_start_time_and_manifest(self):
        with tempfile.TemporaryDirectory() as folder:
            session = AudioSession(queue.Queue())
            session.state = 'recording'
            session._temporary = Path(folder)
            session._session_date = datetime(2026, 10, 22, 17, 38, 6)
            session.recording_file = Path(folder) / 'Zalo.mp3'
            (Path(folder) / 'session.json').write_text('{"active":true}', encoding='utf-8')
            session.set_caller_name('Vợ Yêu')
            self.assertIn('17h38m06s', session.recording_file.name)
            self.assertIn('Vợ Yêu', session.recording_file.name)
            data = json.loads((Path(folder) / 'session.json').read_text(encoding='utf-8'))
            self.assertEqual(data['destination'], str(session.recording_file))


class PlayerTests(unittest.TestCase):
    def test_native_unicode_wav_and_mp3_play_pause_seek_close(self):
        import subprocess
        import time
        from audio_engine import find_ffmpeg
        with tempfile.TemporaryDirectory() as folder:
            wav = Path(folder) / 'Vợ Yêu bản thử.wav'
            with wave.open(str(wav), 'wb') as stream:
                stream.setparams((2, 2, 44100, 0, 'NONE', ''))
                stream.writeframes(b'\0' * 44100 * 4 * 2)
            mp3 = wav.with_suffix('.mp3')
            subprocess.run([str(find_ffmpeg()), '-v', 'error', '-i', str(wav), str(mp3)], check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            for path in (wav, mp3):
                player = AudioPlayer()
                try:
                    player.load(path)
                    self.assertGreater(player.length, 1800)
                    player.toggle()
                    time.sleep(.05)
                    self.assertEqual(player.status()[0], 'playing')
                    player.toggle()
                    self.assertIn(player.status()[0], ('paused', 'stopped'))
                    player.seek(1000)
                    self.assertAlmostEqual(player.status()[1], 1000, delta=100)
                    player.toggle()
                    self.assertEqual(player.status()[0], 'playing')
                finally:
                    player.close()
                self.assertIsNone(player.path)

if __name__ == '__main__':
    unittest.main()
