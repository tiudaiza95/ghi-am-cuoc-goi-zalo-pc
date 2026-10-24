import sys
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main
from zalo_detector import CallSignal, WindowInfo


class BackgroundTests(unittest.TestCase):
    def app(self):
        app = Mock()
        app.auto_record = True
        app.recorder.state = 'idle'
        app.active_call_keys = {5}
        app.last_windows = [WindowInfo(5, 123, 'Cuộc gọi đến - Vợ yêu', '', 550, 600, 'ZaloCall.exe')]
        return app

    def test_auto_records_without_opening_window_or_confirmation(self):
        app = self.app()
        main.Companion._handle_signal(app, CallSignal(5, 'call', 'Detected'))
        self.assertEqual(app.current_call_key, 5)
        self.assertEqual(app.current_caller_name, 'Vợ yêu')
        app._start_recording.assert_called_once_with(automatic=True)
        app.show_window.assert_not_called()
        app._show_decision.assert_not_called()

    def test_ended_call_not_recorded_from_queue(self):
        app = self.app()
        app.active_call_keys = set()
        main.Companion._handle_signal(app, CallSignal(5, 'call', 'Detected'))
        app._start_recording.assert_not_called()

    def test_confirmation_mode_is_preserved(self):
        app = self.app()
        app.auto_record = False
        main.Companion._handle_signal(app, CallSignal(5, 'call', 'Detected'))
        app._show_decision.assert_called_once_with(5, 'Detected')
        app._start_recording.assert_not_called()

    def test_reindexed_device_resolves_by_name(self):
        self.assertEqual(main.resolve_device([{'name': 'USB Microphone', 'index': 22}], 'USB Microphone  [#15]'), 22)

    def test_unplugged_or_ambiguous_device_never_falls_back(self):
        with self.assertRaises(RuntimeError):
            main.resolve_device([{'name': 'Laptop Microphone', 'index': 15}], 'USB Microphone  [#15]')
        with self.assertRaises(RuntimeError):
            main.resolve_device([{'name': 'USB', 'index': 15}, {'name': 'USB', 'index': 16}], 'USB  [#15]')

    def test_background_start_failure_does_not_block_on_dialog(self):
        app = self.app()
        app.mic_combo.get.return_value = 'Missing USB [#15]'
        with patch.object(main, 'scan_devices', return_value=([], [], 0, 0)), patch.object(main.messagebox, 'showerror') as dialog:
            main.Companion._start_recording(app, automatic=True)
        dialog.assert_not_called()
        app._notify.assert_called_once()
        app.recorder.start.assert_not_called()


if __name__ == '__main__':
    unittest.main()
