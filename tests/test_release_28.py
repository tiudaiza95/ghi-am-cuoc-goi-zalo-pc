import queue
import tempfile
import time
import unittest
import wave
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import audio_engine as audio
from audio_player import AudioPlayer
from desktop_support import GlobalHotkeyListener
from recording_library import (
    atomic_json, read_json, cleanup_old_recordings,
    add_timestamp_mark, remove_timestamp_mark
)
from ui_effects import MiniOverlay
import customtkinter as ctk


def make_dummy_wav(path, duration_sec=1):
    with wave.open(str(path), 'wb') as stream:
        stream.setparams((2, 2, 48000, 0, 'NONE', ''))
        stream.writeframes(b'\0' * 48000 * 4 * duration_sec)


class Release28Tests(unittest.TestCase):
    def test_audio_player_speed_setting(self):
        commands = []
        def mock_cmd(text):
            commands.append(text)
            if 'length' in text:
                return '10000'
            return ''
        player = AudioPlayer(command=mock_cmd)
        player.set_speed(1.5)
        self.assertEqual(player.speed, 1.5)
        # load a dummy file
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            f.write(b'123')
            f_path = Path(f.name)
        try:
            player.load(f_path)
            self.assertTrue(any('speed 1500' in c for c in commands))
            player.set_speed(0.75)
            self.assertEqual(player.speed, 0.75)
            self.assertTrue(any('speed 750' in c for c in commands))
            # clamp boundaries
            player.set_speed(5.0)
            self.assertEqual(player.speed, 2.0)
            player.set_speed(0.1)
            self.assertEqual(player.speed, 0.5)
        finally:
            f_path.unlink(missing_ok=True)

    @unittest.skipUnless(audio.find_ffmpeg(), 'Needs FFmpeg')
    def test_split_channel_and_normalize_encoding(self):
        with tempfile.TemporaryDirectory() as folder:
            f = Path(folder)
            spk = f / 'speaker.wav'
            mic = f / 'microphone.wav'
            make_dummy_wav(spk, 1)
            make_dummy_wav(mic, 1)

            # 1. Test split stereo
            dest_split = f / 'split.mp3'
            audio.encode_audio(spk, mic, {'speaker': 0.0, 'microphone': 0.0},
                               dest_split, 'MP3', channel_mode='split', normalize=True)
            self.assertTrue(dest_split.exists())
            self.assertGreater(dest_split.stat().st_size, 100)

            # 2. Test mixed normalized
            dest_mixed = f / 'mixed.mp3'
            audio.encode_audio(spk, mic, {'speaker': 0.0, 'microphone': 0.0},
                               dest_mixed, 'MP3', channel_mode='mixed', normalize=True)
            self.assertTrue(dest_mixed.exists())
            self.assertGreater(dest_mixed.stat().st_size, 100)

    def test_retention_policy_cleanup(self):
        with tempfile.TemporaryDirectory() as folder:
            f = Path(folder)
            old_day = (datetime.now() - timedelta(days=45)).isoformat()
            new_day = (datetime.now() - timedelta(days=5)).isoformat()

            # Record 1: Old and not favorite -> Should be deleted
            r1 = f / 'call1.mp3'
            r1.write_bytes(b'abc')
            atomic_json(f / 'call1.mp3.json', {'started_at': old_day, 'favorite': False})

            # Record 2: Old but FAVORITE -> Must be kept!
            r2 = f / 'call2.mp3'
            r2.write_bytes(b'def')
            atomic_json(f / 'call2.mp3.json', {'started_at': old_day, 'favorite': True})

            # Record 3: Recent and not favorite -> Must be kept!
            r3 = f / 'call3.mp3'
            r3.write_bytes(b'ghi')
            atomic_json(f / 'call3.mp3.json', {'started_at': new_day, 'favorite': False})

            deleted = cleanup_old_recordings(f, 30)
            self.assertEqual(deleted, 1)
            self.assertFalse(r1.exists())
            self.assertFalse((f / 'call1.mp3.json').exists())
            self.assertTrue(r2.exists())
            self.assertTrue(r3.exists())

    def test_timestamps_marks_add_and_remove(self):
        with tempfile.TemporaryDirectory() as folder:
            f = Path(folder)
            audio_file = f / 'meeting.mp3'
            audio_file.write_bytes(b'test')
            atomic_json(f / 'meeting.mp3.json', {'duration': 120})

            # Add marks
            add_timestamp_mark(audio_file, 45.2, 'Báo giá')
            add_timestamp_mark(audio_file, 15.0, 'Mở đầu')
            data = read_json(f / 'meeting.mp3.json')
            self.assertEqual(len(data.get('timestamps', [])), 2)
            # Should be sorted by time
            self.assertEqual(data['timestamps'][0]['label'], 'Mở đầu')
            self.assertEqual(data['timestamps'][1]['label'], 'Báo giá')

            # Remove mark
            remove_timestamp_mark(audio_file, 0)
            data2 = read_json(f / 'meeting.mp3.json')
            self.assertEqual(len(data2['timestamps']), 1)
            self.assertEqual(data2['timestamps'][0]['label'], 'Báo giá')

    def test_mini_overlay_creation_and_update(self):
        root = ctk.CTk()
        root.withdraw()
        try:
            stopped = []
            expanded = []
            overlay = MiniOverlay(root, on_stop=lambda: stopped.append(True), on_expand=lambda: expanded.append(True))
            overlay.withdraw()
            self.assertTrue(overlay.winfo_exists())
            overlay.update_time('00:05:21')
            self.assertEqual(overlay.timer.cget('text'), '00:05:21')
            overlay.destroy()
        finally:
            root.destroy()


if __name__ == '__main__':
    unittest.main()
