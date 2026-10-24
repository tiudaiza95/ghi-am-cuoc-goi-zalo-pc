import queue
import subprocess
import sys
import tempfile
import unittest
import threading
import wave
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import audio_engine as audio


class AudioTests(unittest.TestCase):
    def test_silent_loopback_never_enters_blocking_read(self):
        with tempfile.TemporaryDirectory() as folder:
            backend = Mock()
            engine = backend.PyAudio.return_value
            engine.get_device_info_by_index.return_value = {'maxInputChannels': 2, 'defaultSampleRate': 48000}
            stream = engine.open.return_value
            stream.get_read_available.return_value = 0
            stop = Mock()
            stop.is_set.side_effect = [False, False, True]
            faults = []
            target = Path(folder) / 'speaker.wav'
            with patch.object(audio, 'pyaudio', backend), patch.object(audio.time, 'perf_counter', side_effect=[0, 1, 1]):
                audio.capture_track('speaker', 1, target, stop, {}, faults, threading.Lock())
            self.assertFalse(faults)
            stream.read.assert_not_called()
            stream.close.assert_called_once()
            with wave.open(str(target)) as wav:
                self.assertGreater(wav.getnframes(), 0)

    def test_stuck_worker_blocks_new_recordings(self):
        session = audio.AudioSession(queue.Queue())
        worker = Mock()
        worker.is_alive.return_value = True
        session._workers = [worker]
        session.state = 'saving'
        session._complete()
        self.assertEqual(session.state, 'blocked')
        self.assertEqual(session.events.get_nowait()[0], 'info')
        self.assertEqual(session.events.get_nowait()[0], 'blocked')
        worker.terminate.assert_called_once()
        self.assertFalse(session.start(1, 2, Path('.'), 'WAV'))
        with patch.object(audio.threading, 'Thread') as thread:
            session.retry_completion()
            thread.assert_not_called()
            worker.is_alive.return_value = False
            session.retry_completion()
            self.assertEqual(session.state, 'saving')
            thread.return_value.start.assert_called_once()
            session.retry_completion()
            thread.assert_called_once()

    def test_encode_failure_preserves_sources_and_publishes_idle(self):
        with tempfile.TemporaryDirectory() as folder:
            session = audio.AudioSession(queue.Queue())
            session._temporary = Path(folder)
            source = Path(folder) / 'speaker.wav'
            with wave.open(str(source), 'wb') as wav:
                wav.setparams((1, 2, 48000, 0, 'NONE', 'none'))
                wav.writeframes(b'\0\0' * 100)
            original = source.read_bytes()
            session.recording_file = Path(folder) / 'result.mp3'
            session._started = {'speaker': 1.0, 'microphone': 1.1}
            session.state = 'saving'
            with patch.object(audio, 'encode_audio', side_effect=RuntimeError('failed')) as encode:
                session._complete()
                encode.assert_called_once()
            self.assertEqual(session.state, 'idle')
            self.assertEqual(session.events.get_nowait()[0], 'error')
            self.assertEqual(source.read_bytes(), original)

    def test_success_cleans_temporary_tracks(self):
        with tempfile.TemporaryDirectory() as folder:
            session = audio.AudioSession(queue.Queue())
            session._temporary = Path(folder) / 'tracks'
            session._temporary.mkdir()
            for role in ('speaker', 'microphone'):
                with wave.open(str(session._temporary / f'{role}.wav'), 'wb') as wav:
                    wav.setparams((1, 2, 48000, 0, 'NONE', 'none'))
                    wav.writeframes(b'\0\0' * 100)
            session.recording_file = Path(folder) / 'result.wav'
            session._started = {'speaker': 1.0, 'microphone': 1.1}
            session.state = 'saving'
            with patch.object(audio, 'encode_audio'):
                session._complete()
            self.assertEqual(session.state, 'idle')
            self.assertFalse(session._temporary.exists())
            self.assertEqual(session.events.get_nowait(), ('saved', str(session.recording_file)))

    def test_ffmpeg_timeout_is_bounded_and_keeps_sources(self):
        with tempfile.TemporaryDirectory() as folder:
            speaker = Path(folder) / 'speaker.wav'
            mic = Path(folder) / 'microphone.wav'
            for path in (speaker, mic):
                with wave.open(str(path), 'wb') as wav:
                    wav.setparams((1, 2, 48000, 0, 'NONE', 'none'))
                    wav.writeframes(b'\0\0' * 100)
            with patch.object(audio.shutil, 'which', return_value='ffmpeg'), \
                 patch.object(audio.subprocess, 'run', side_effect=subprocess.TimeoutExpired('ffmpeg', 600)) as run:
                with self.assertRaises(RuntimeError):
                    audio.encode_audio(speaker, mic, {'speaker': 1.0, 'microphone': 1.1},
                                       Path(folder) / 'result.mp3', 'MP3')
                self.assertEqual(run.call_args.kwargs['timeout'], audio.ENCODE_TIMEOUT)
                self.assertTrue(speaker.exists() and mic.exists())

    def test_partial_worker_start_failure_stops_launched_worker(self):
        with tempfile.TemporaryDirectory() as folder:
            session = audio.AudioSession(queue.Queue())
            first, second = Mock(), Mock()
            second.start.side_effect = RuntimeError('thread start failed')
            with patch.object(audio, 'pyaudio', object()), \
                 patch.object(audio.shutil, 'which', return_value='ffmpeg'), \
                 patch.object(session._context, 'Process', side_effect=[first, second]), \
                 patch.object(session, 'stop') as stop:
                self.assertFalse(session.start(1, 2, Path(folder), 'WAV'))
            self.assertEqual(session._workers, [first])
            stop.assert_called_once()
            self.assertIn('thread start failed', session.error_if_any())


if __name__ == '__main__':
    unittest.main()

