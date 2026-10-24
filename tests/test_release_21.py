import json
import os
from pathlib import Path
import queue
import sys
import tempfile
import time
import unittest
import uuid
import wave
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import audio_engine as audio
import main
from recording_library import atomic_json, list_recordings, recovery_candidates, rename_recording, read_json
from desktop_support import SingleInstance, setup_logger
from zalo_detector import ZaloCallDetector, WindowInfo


def wav_file(path):
    with wave.open(str(path), 'wb') as wav:
        wav.setparams((1, 2, 48000, 0, 'NONE', 'none'))
        wav.writeframes(b'\x00\x08' * 48000)


class ReleaseTests(unittest.TestCase):
    def make_app(self):
        app = Mock()
        app.recorder.state = 'saving'
        app.recorder.error_if_any.return_value = None
        app.events = queue.Queue()
        app.pending_signals = {}
        app.current_call_key = None
        app.pending_popup = None
        app.detector = ZaloCallDetector()
        app.auto_record = False
        app._handle_signal = lambda signal: main.Companion._handle_signal(app, signal)
        return app

    def poll(self, app, windows):
        with patch.object(main, 'zalo_processes', return_value={123: 'Zalo.exe'}), \
             patch.object(main, 'windows_for_pids', return_value=windows):
            main.Companion._poll(app)

    def test_new_call_waits_for_save_then_prompts_once(self):
        app = self.make_app()
        baseline = WindowInfo(1, 123, 'Zalo', '', 500, 500)
        call = WindowInfo(2, 123, 'Incoming call', '', 500, 500)
        self.poll(app, [baseline])
        self.poll(app, [baseline, call])
        self.poll(app, [baseline, call])
        app._show_decision.assert_not_called()
        app.recorder.state = 'idle'
        self.poll(app, [baseline, call])
        self.poll(app, [baseline, call])
        app._show_decision.assert_called_once()
        self.assertEqual(app._show_decision.call_args.args[0], 2)

    def test_ended_waiting_call_does_not_prompt(self):
        app = self.make_app()
        baseline = WindowInfo(1, 123, 'Zalo', '', 500, 500)
        call = WindowInfo(2, 123, 'Incoming call', '', 500, 500)
        self.poll(app, [baseline])
        self.poll(app, [baseline, call])
        self.poll(app, [baseline, call])
        app.recorder.state = 'idle'
        self.poll(app, [baseline])
        app._show_decision.assert_not_called()

    def test_manual_can_bind_to_call(self):
        app = Mock()
        app.recorder.state = 'idle'
        app.active_call_keys = {5}
        with patch.object(main.messagebox, 'askyesno', return_value=True):
            main.Companion.manual_confirm(app)
        self.assertEqual(app._show_decision.call_args.args[0], 5)
        with patch.object(main.messagebox, 'askyesno', return_value=False):
            main.Companion.manual_confirm(app)
        self.assertIsNone(app._show_decision.call_args.args[0])

    def test_ready_only_after_two_sources(self):
        with tempfile.TemporaryDirectory() as folder:
            session = audio.AudioSession(queue.Queue())
            session._temporary = Path(folder)
            session.state = 'starting'
            session._launch_time = time.monotonic()
            session._workers = [Mock(name='unused'), Mock(name='unused')]
            for worker, role in zip(session._workers, ['microphone', 'speaker']):
                worker.name, worker.exitcode = role, None
            atomic_json(Path(folder) / 'microphone.json', {'started': time.perf_counter(), 'faults': [], 'level': 0.5, 'updated': time.monotonic()})
            session.refresh()
            self.assertEqual(session.state, 'starting')
            self.assertEqual(session.levels['microphone'], 0.5)
            atomic_json(Path(folder) / 'speaker.json', {'started': time.perf_counter(), 'faults': []})
            session.refresh()
            self.assertEqual(session.state, 'recording')
            self.assertEqual(session.events.get_nowait()[0], 'ready')
            session.refresh()
            self.assertTrue(session.events.empty())

    def test_save_timer_does_not_include_encoding(self):
        app = Mock()
        app.recorder.state = 'saving'
        app.recorder.elapsed = 62
        app.audio_meters = {}
        main.Companion._clock(app)
        app.timer_label.configure.assert_called_once_with(text='00:01:02')

    @unittest.skipUnless(audio.find_ffmpeg(), 'Needs FFmpeg')
    def test_single_source_is_saved_and_original_kept(self):
        with tempfile.TemporaryDirectory() as folder:
            temp = Path(folder) / 'zcc_temp_test'
            temp.mkdir()
            wav_file(temp / 'microphone.wav')
            session = audio.AudioSession(queue.Queue())
            session._temporary = temp
            session.recording_file = Path(folder) / 'QA.mp3'
            session._started = {'microphone': 1.0}
            session._faults = ['speaker: unplugged']
            session.state = 'saving'
            session._complete()
            self.assertEqual(session.state, 'idle')
            self.assertIn('Chỉ micro', session.recording_file.name)
            self.assertGreater(session.recording_file.stat().st_size, 100)
            self.assertTrue((temp / 'microphone.wav').exists())
            self.assertEqual(recovery_candidates(folder), [])
            self.assertEqual(list_recordings(folder)[0]['status'], 'Chỉ micro')

    @unittest.skipUnless(audio.find_ffmpeg(), 'Needs FFmpeg')
    def test_recovery_preserves_raw_and_is_not_offered_again(self):
        with tempfile.TemporaryDirectory() as folder:
            temp = Path(folder) / 'zcc_temp_test'
            temp.mkdir()
            wav_file(temp / 'microphone.wav')
            atomic_json(temp / 'session.json', {'active': False, 'destination': str(Path(folder) / 'Test.mp3')})
            self.assertEqual(recovery_candidates(folder), [temp])
            session = audio.AudioSession(queue.Queue())
            session.recover(temp)
            deadline = time.monotonic() + 10
            while session.state != 'idle' and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertEqual(session.state, 'idle')
            self.assertTrue(session.recording_file.exists())
            self.assertTrue((temp / 'microphone.wav').exists())
            self.assertEqual(recovery_candidates(folder), [])

    def test_active_session_not_recoverable(self):
        import psutil
        with tempfile.TemporaryDirectory() as folder:
            temp = Path(folder) / 'zcc_temp_test'
            temp.mkdir()
            wav_file(temp / 'microphone.wav')
            atomic_json(temp / 'session.json', {'active': True, 'pid': os.getpid(), 'process_created': psutil.Process().create_time()})
            self.assertEqual(recovery_candidates(folder), [])
            with self.assertRaises(RuntimeError):
                audio.AudioSession(queue.Queue()).recover(temp)

    def test_rename_moves_metadata_and_blocks_path_escape(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'Test.wav'
            wav_file(source)
            atomic_json(source.with_suffix('.wav.json'), {'duration': 1, 'status': 'Đủ hai nguồn'})
            with self.assertRaises(ValueError):
                rename_recording(source, '../escape')
            result = rename_recording(source, 'Vợ yêu')
            self.assertTrue(result.exists())
            self.assertEqual(read_json(result.with_suffix('.wav.json'))['duration'], 1)
            self.assertFalse(source.exists())

    def test_atomic_encode_failure_does_not_create_final_file(self):
        import subprocess
        with tempfile.TemporaryDirectory() as folder:
            microphone = Path(folder) / 'microphone.wav'
            wav_file(microphone)
            dest = Path(folder) / 'output.mp3'
            def failed_run(cmd, **kwargs):
                Path(cmd[-1]).write_bytes(b'partial data')
                raise subprocess.TimeoutExpired(cmd, 600)
            with patch.object(audio, 'find_ffmpeg', return_value='ffmpeg'), patch.object(audio.subprocess, 'run', side_effect=failed_run):
                with self.assertRaises(RuntimeError):
                    audio.encode_audio(Path(folder) / 'absent.wav', microphone, {'microphone': 1.0}, dest, 'MP3')
            self.assertFalse(dest.exists())
            self.assertTrue(microphone.exists())
            self.assertEqual(list_recordings(folder)[0]['path'], microphone)
            self.assertEqual(len(list_recordings(folder)), 1)

    @unittest.skipUnless(sys.platform == 'win32', 'Windows only')
    def test_single_instance_signals_primary(self):
        name = 'ZccTest' + uuid.uuid4().hex
        first = SingleInstance(name)
        second = SingleInstance(name)
        try:
            self.assertTrue(first.primary)
            self.assertFalse(second.primary)
            self.assertTrue(first.requested_show())
            self.assertFalse(first.requested_show())
        finally:
            second.close()
            first.close()


if __name__ == '__main__':
    unittest.main()
