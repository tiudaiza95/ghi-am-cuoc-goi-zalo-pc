import queue
import tempfile
import unittest
import wave
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch
import customtkinter as ctk
import main
import test_app_flow
from audio_engine import AudioSession
from audio_player import AudioPlayer
from desktop_support import TRAY_STATES, tray_state_image, update_tray_state
from recording_library import atomic_json, read_json, matches_date, session_description, list_recordings
from library_window import LibraryWindow
from ui_effects import cancel_root_callbacks
from zalo_detector import CallSignal


def wav(path):
    with wave.open(str(path), 'wb') as f:
        f.setparams((1, 2, 48000, 0, 'NONE', ''))
        f.writeframes(b'\0' * 96000)


class NewFlowTests(unittest.TestCase):
    def app(self, state='idle'):
        app = test_app_flow.AppFlowTests().app(state)
        app._test_mode = False
        app._test_deadline = None
        app.active_call_keys = set()
        return app

    def test_audio_check_refuses_during_call(self):
        app = self.app('recording')
        with patch.object(main.messagebox, 'showinfo'):
            main.Companion.test_audio(app)
        app._start_recording.assert_not_called()

    def test_audio_check_sets_purpose_and_handles_start_failure(self):
        app = self.app()
        app._start_recording.return_value = False
        main.Companion.test_audio(app)
        self.assertFalse(app._test_mode)
        self.assertIsNone(app.current_call_key)

    def test_ready_starts_eight_seconds_not_device_startup(self):
        app = self.app('recording');app._test_mode=True
        app.events.put(('ready', 'Ready'))
        with patch.object(main.time, 'monotonic', return_value=100):
            test_app_flow.AppFlowTests().poll(app)
        self.assertEqual(app._test_deadline,108)
        app.recorder.recorded_from=100;app.audio_meters={}
        with patch.object(main.time,'monotonic',return_value=107):
            main.Companion._clock(app)
        app.stop_recording.assert_not_called()
        with patch.object(main.time,'monotonic',return_value=108):
            main.Companion._clock(app)
        app.stop_recording.assert_called_once()

    def test_incoming_call_interrupts_test_and_remains_pending(self):
        app = self.app('recording');app._test_mode=True
        signal=CallSignal(12,'call','call')
        app.detector.update.return_value=([signal],{12})
        test_app_flow.AppFlowTests().poll(app)
        app.stop_recording.assert_called_once()
        self.assertEqual(app.pending_signals,{12:signal})
        app._handle_signal.assert_not_called()

    def test_test_saved_does_not_play_over_pending_call(self):
        app=self.app();app._test_mode=True
        signal=CallSignal(12,'call','call')
        app.pending_signals={12:signal}
        app.detector.update.return_value=([],{12})
        app.events.put(('saved','test.mp3'))
        with patch.object(main,'LibraryWindow') as library:
            test_app_flow.AppFlowTests().poll(app)
        library.assert_not_called()
        self.assertFalse(app._test_mode)
        app._handle_signal.assert_called_once_with(signal)

    def test_saved_audio_check_opens_internal_player(self):
        app=self.app();app._test_mode=True
        app.events.put(('saved','check.mp3'))
        with patch.object(main,'LibraryWindow') as library:
            test_app_flow.AppFlowTests().poll(app)
            library.return_value.select_path.assert_called_once_with('check.mp3',autoplay=True)
        self.assertFalse(app._test_mode)


class PlaybackAndMetadataTests(unittest.TestCase):
    def test_native_volume_and_skip_bounds(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'silent.wav';wav(path)
            player=AudioPlayer()
            try:
                player.load(path)
                player.set_volume(0)
                self.assertEqual(player.command(f'status {player.alias} volume'),'0')
                player.set_volume(200)
                self.assertEqual(player.volume,100)
                player.skip(-10)
                self.assertEqual(player.status()[1],0)
                player.skip(10)
                self.assertLessEqual(player.status()[1],player.length)
            finally:player.close()

    def test_date_filters_and_invalid_legacy_date(self):
        now=datetime(2026,10,27)
        self.assertTrue(matches_date({'timestamp':'2026-10-21T12:00:00'},'7 ngày qua',now))
        self.assertFalse(matches_date({'timestamp':'2026-10-20T12:00:00'},'7 ngày qua',now))
        self.assertTrue(matches_date({'timestamp':'2026-10-27T12:00:00'},'Hôm nay',now))
        self.assertFalse(matches_date({'timestamp':None},'Hôm nay',now))
        self.assertTrue(matches_date({'timestamp':None},'Tất cả ngày',now))

    def test_metadata_preserves_devices_times_sources_and_recovery(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);temp=root/'temp';temp.mkdir();wav(temp/'speaker.wav')
            atomic_json(temp/'session.json',{'created':'2026-10-27T10:00:00','ended_at':'2026-10-27T10:00:01',
                'session_details':{'devices':{'speaker':'Headset','microphone':'USB Mic'},'purpose':'audio_check'}})
            session=AudioSession(queue.Queue())
            with patch('audio_engine.encode_audio',side_effect=lambda a,b,c,d,e:d.write_bytes(b'encoded')):
                dest=session._save_tracks(temp,root/'result.mp3','MP3',recovering=True)
            data=read_json(dest.with_suffix('.mp3.json'))
            self.assertEqual(data['devices']['speaker'],'Headset')
            self.assertEqual(data['started_at'],'2026-10-27T10:00:00')
            self.assertEqual(data['ended_at'],'2026-10-27T10:00:01')
            self.assertEqual(data['sources'],['speaker'])
            self.assertEqual(data['source_durations']['speaker'],1)
            self.assertIn('Chỉ loa',session_description(dest))

    def test_display_date_matches_filter_even_when_saved_next_day(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'night.wav';wav(path)
            atomic_json(path.with_suffix('.wav.json'), {'started_at':'2026-10-26T23:59:00'})
            record=list_recordings(folder)[0]
            self.assertEqual(record['date'],'26/10/2026 23:59')
            self.assertTrue(matches_date(record,'Hôm nay',datetime(2026,10,26)))
            self.assertFalse(matches_date(record,'Hôm nay',datetime(2026,10,27)))

    def test_tray_states_have_distinct_shapes_and_no_redundant_updates(self):
        self.assertEqual(len({tray_state_image(s).tobytes() for s in ('idle','recording','saving','error')}),4)
        icon=Mock();update_tray_state(icon,'recording');original=icon.icon
        update_tray_state(icon,'recording');self.assertIs(icon.icon,original)
        update_tray_state(icon,'error');self.assertIn('Có lỗi',icon.title)

    def test_refresh_filter_does_not_reset_playback(self):
        root=ctk.CTk();root.withdraw();root.recorder=Mock(state='idle');root.reduce_motion=True
        try:
            with tempfile.TemporaryDirectory() as folder:
                path=Path(folder)/'record.wav';wav(path)
                atomic_json(path.with_suffix('.wav.json'),{'started_at':'2020-01-01T10:00:00'})
                library=LibraryWindow(root,folder,Mock());library.withdraw()
                library.player=Mock(path=path,length=1000,volume=80)
                library.player.status.return_value=('paused',450)
                library.select_path(path)
                library.refresh()
                self.assertEqual(library.selected(),path)
                library.player.load.assert_not_called()
                library.player.seek.assert_not_called()
                library.date_filter.set('Hôm nay');library.refresh()
                self.assertIsNone(library.selected())
                library.play()
                library.player.toggle.assert_called_once()
                library.player.load.assert_not_called()
                library.destroy()
        finally:
            cancel_root_callbacks(root)
            root.destroy()
