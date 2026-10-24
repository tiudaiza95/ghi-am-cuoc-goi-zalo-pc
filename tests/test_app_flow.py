import queue
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main


class AppFlowTests(unittest.TestCase):
    def test_missing_call_stops_after_handover_grace(self):
        app = self.app('recording')
        app.current_call_key = 2
        app.lost_call_since = None
        with patch.object(main.time, 'monotonic', return_value=10):
            self.poll(app)
        app.stop_recording.assert_not_called()
        with patch.object(main.time, 'monotonic', return_value=15):
            self.poll(app)
        app.stop_recording.assert_called_once()

    def app(self, state='idle'):
        app = Mock()
        app.events = queue.Queue()
        app.recorder.state = state
        app.recorder.error_if_any.return_value = None
        app.detector.update.return_value = ([], set())
        app.close_requested = False
        app.pending_popup = None
        app.last_windows = []
        app.current_call_key = None
        app.pending_signals = {}
        app.library = None
        return app

    def poll(self, app):
        with patch.object(main, 'zalo_processes', return_value={}), \
             patch.object(main.messagebox, 'showerror'):
            main.Companion._poll(app)

    def test_other_window_cannot_take_over_recording(self):
        app = self.app('recording')
        app.current_call_key = 2
        app.lost_call_since = 1.0
        app.detector.update.return_value = ([], {3})
        with patch.object(main.time, 'monotonic', return_value=10.0):
            self.poll(app)
        self.assertEqual(app.current_call_key, 2)
        app.stop_recording.assert_called_once()

    def test_save_failure_cancels_requested_close(self):
        app = self.app()
        app.close_requested = True
        app.events.put(('error', 'encoding failed'))
        self.poll(app)
        self.assertFalse(app.close_requested)
        app.destroy.assert_not_called()
        app._restore_controls.assert_called_once()

    def test_success_closes_only_after_saved_event(self):
        app = self.app()
        app.close_requested = True
        app.events.put(('saved', 'result.wav'))
        self.poll(app)
        app.destroy.assert_called_once()
        app.detector.update.assert_not_called()

    def test_blocked_workers_disable_recording_and_cancel_close(self):
        app = self.app('blocked')
        app.close_requested = True
        app.events.put(('blocked', 'waiting'))
        self.poll(app)
        self.assertFalse(app.close_requested)
        app.record_btn.configure.assert_called_with(state='disabled')
        app._restore_controls.assert_not_called()
        app.destroy.assert_not_called()

    def test_stale_popup_cannot_start_recording(self):
        app = self.app()
        app.active_call_keys = set()
        with patch.object(main, 'ConfirmPopup') as popup:
            main.Companion._show_decision(app, 2, 'Incoming call')
            accept = popup.call_args.args[2]
            accept()
        app._start_recording.assert_not_called()

    def test_settings_array_falls_back_to_defaults(self):
        with patch.object(main, 'CONFIG') as config:
            config.read_text.return_value = '[]'
            self.assertEqual(main.load_settings(), {})


if __name__ == '__main__':
    unittest.main()
