import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import tempfile
import json
import wave

from audio_engine import encode_audio
from recording_library import trim_audio, transcribe_with_gemini
from desktop_support import play_audio_cue


class Release29Tests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_wav(self, name, duration_sec=3.0):
        p = self.dir / name
        with wave.open(str(p), 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(48000)
            wf.writeframes(b'\x00\x00' * int(48000 * duration_sec))
        return p

    def test_trim_audio_success_and_validation(self):
        src = self._create_wav('sample.wav', duration_sec=4.0)
        out = trim_audio(src, 1.0, 3.0)
        self.assertTrue(out.is_file())
        with wave.open(str(out), 'rb') as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            dur = frames / float(rate)
            self.assertAlmostEqual(dur, 2.0, delta=0.2)

        # Validation error when end <= start
        with self.assertRaises(ValueError):
            trim_audio(src, 3.0, 1.0)

    def test_denoise_filter_in_encoding(self):
        mic = self._create_wav('mic.wav', 1.0)
        spk = self._create_wav('spk.wav', 1.0)
        dest = self.dir / 'denoised_test.wav'
        encode_audio(spk, mic, {'speaker': 0, 'microphone': 0}, dest, 'WAV', denoise=True)
        self.assertTrue(dest.is_file())

    def test_gemini_31_flash_lite_and_summary_task(self):
        src = self._create_wav('call.wav', 1.0)
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps({
                'candidates': [{
                    'content': {
                        'parts': [{'text': '📌 Tóm tắt cuộc gọi: Hẹn họp 15h'}]
                    }
                }]
            }).encode('utf-8')
            mock_urlopen.return_value.__enter__.return_value = mock_resp

            result = transcribe_with_gemini('dummy_key', src, model='gemini-3.1-flash-lite', task='summary')
            self.assertIn('📌 Tóm tắt cuộc gọi', result)

            # Check that request URL used gemini-3.1-flash-lite
            call_args = mock_urlopen.call_args
            req = call_args[0][0]
            self.assertIn('gemini-3.1-flash-lite', req.full_url)
            self.assertIn('ACTION ITEMS', req.data.decode('utf-8'))

    def test_play_audio_cue_non_blocking(self):
        # Should not raise exception
        play_audio_cue('start')
        play_audio_cue('stop')
        play_audio_cue('mark')

    def test_waveform_canvas_logic(self):
        import tkinter as tk
        from library_window import WaveformCanvas
        root = tk.Tk()
        root.withdraw()
        try:
            canvas = WaveformCanvas(root)
            canvas.set_audio(10.0, marks=[0.2, 0.5])
            self.assertEqual(len(canvas.peaks), 72)
            canvas.set_progress(0.4)
            self.assertEqual(canvas.progress, 0.4)
        finally:
            root.destroy()

    def test_library_sync_close_on_hide_to_tray(self):
        from unittest.mock import Mock
        from main import Companion
        app = Mock()
        mock_lib = Mock()
        mock_lib.winfo_exists.return_value = True
        app.library = mock_lib
        app.tray = None
        app.events = Mock()
        app.auto_record = True
        Companion.hide_to_tray(app)
        mock_lib.destroy.assert_called_once()
        self.assertIsNone(app.library)


if __name__ == '__main__':
    unittest.main()
