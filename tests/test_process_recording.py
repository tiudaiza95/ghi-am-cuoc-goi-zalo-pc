"""Exercise real child processes without accessing a microphone or speaker."""
import os
import queue
import sys
import tempfile
import time
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import audio_engine as audio


def synthetic_capture(role, device, target, stop):
    with wave.open(str(target), 'wb') as wav:
        wav.setparams((1, 2, 48000, 0, 'NONE', 'not compressed'))
        wav.writeframes(b'\0\0' * 48000)
    audio.write_status(target.with_suffix('.json'), {'started': time.perf_counter(), 'faults': []})
    stop.wait(15)


def fail_process():
    os._exit(37)


def stuck_capture(role, device, target, stop):
    with wave.open(str(target), 'wb') as wav:
        wav.setparams((1, 2, 48000, 0, 'NONE', 'not compressed'))
        wav.writeframes(b'\0\0' * 48000)
    audio.write_status(target.with_suffix('.json'), {'started': time.perf_counter(), 'faults': []})
    time.sleep(30)


class ProcessTests(unittest.TestCase):
    def test_real_child_exit_is_reported_without_parent_exit(self):
        session = audio.AudioSession(queue.Queue())
        worker = session._context.Process(name='microphone', target=fail_process)
        session._workers = [worker]
        worker.start()
        worker.join(10)
        try:
            self.assertFalse(worker.is_alive())
            self.assertIn('0x00000025', session.error_if_any())
            self.assertTrue(session._stop.is_set())
        finally:
            if worker.is_alive():
                worker.terminate()
                worker.join(5)
            worker.close()

    @unittest.skipUnless(audio.find_ffmpeg(), 'FFmpeg is required for integration test')
    def test_two_real_processes_mix_synthetic_audio_to_mp3(self):
        with tempfile.TemporaryDirectory() as folder:
            session = audio.AudioSession(queue.Queue())
            try:
                with patch.object(audio, 'capture_process', getattr(self, 'capture_target', synthetic_capture)):
                    self.assertTrue(session.start(1, 2, Path(folder), 'MP3'))
                deadline = time.monotonic() + 15
                while time.monotonic() < deadline:
                    self.assertIsNone(session.error_if_any())
                    if len(session._started) == 2:
                        break
                    time.sleep(0.05)
                self.assertEqual(len(session._started), 2)
                self.assertTrue(session.stop())
                deadline = time.monotonic() + 15
                while session.state != 'idle' and time.monotonic() < deadline:
                    time.sleep(0.05)
                self.assertEqual(session.state, 'idle')
                messages = []
                while not session.events.empty():
                    messages.append(session.events.get_nowait())
                self.assertIn(('saved', str(session.recording_file)), messages)
                self.assertGreater(session.recording_file.stat().st_size, 100)
            finally:
                session._stop.set()
                for worker in session._workers:
                    worker.join(5)
                    if worker.is_alive():
                        worker.terminate()
                        worker.join(5)
                    worker.close()

    @unittest.skipUnless(audio.find_ffmpeg(), 'FFmpeg required')
    def test_stuck_real_processes_are_terminated_and_saved(self):
        self.capture_target = stuck_capture
        with patch.object(audio, 'STOP_TIMEOUT', 0.1):
            self.test_two_real_processes_mix_synthetic_audio_to_mp3()


if __name__ == '__main__':
    unittest.main()
