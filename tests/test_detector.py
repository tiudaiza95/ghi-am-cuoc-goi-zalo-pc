import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from zalo_detector import WindowInfo, ZaloCallDetector, looks_like_call_title, is_zalo_process


def w(hwnd, title='Zalo', width=550, height=600, process_name='Zalo.exe'):
    return WindowInfo(hwnd, 123, title, 'Chrome_WidgetWin_1', width, height, process_name)


class DetectionTests(unittest.TestCase):
    def test_generic_call_ended_window_is_no_longer_active(self):
        mon = ZaloCallDetector()
        mon.update([w(1)], True)
        for _ in range(3):
            mon.update([w(1), w(2)], True)
        for title in ('Cuộc gọi kết thúc', 'Call ended', 'Không trả lời'):
            signals, active = mon.update([w(1), w(2, title)], True)
            self.assertNotIn(2, active)
            self.assertFalse(signals)

    def test_process_before_main_window_does_not_prompt(self):
        mon = ZaloCallDetector()
        for _ in range(3):
            self.assertEqual(mon.update([], True), ([], set()))
        for _ in range(5):
            self.assertEqual(mon.update([w(1)], True), ([], set()))

    def test_named_call_does_not_fall_back_to_generic(self):
        mon = ZaloCallDetector()
        mon.update([w(1)], True)
        for _ in range(2):
            mon.update([w(1), w(2, 'Incoming call')], True)
        for _ in range(12):
            signals, active = mon.update([w(1), w(2)], True)
            self.assertFalse(signals)
            self.assertNotIn(2, active)
        self.assertNotIn(2, mon.active_keys)
        mon.update([w(1), w(2, 'Incoming call')], True)
        self.assertEqual(len(mon.update([w(1), w(2, 'Incoming call')], True)[0]), 1)

    def test_named_observations_must_be_consecutive(self):
        mon = ZaloCallDetector()
        mon.allow_new_windows = False
        mon.update([w(1)], True)
        mon.update([w(1, 'Incoming call')], True)
        mon.update([w(1)], True)
        self.assertFalse(mon.update([w(1, 'Incoming call')], True)[0])
        self.assertEqual(len(mon.update([w(1, 'Incoming call')], True)[0]), 1)

    def test_generic_observations_must_be_consecutive(self):
        mon = ZaloCallDetector()
        mon.update([w(1)], True)
        mon.update([w(1), w(2, process_name='ZaloCall.exe')], True)
        mon.update([w(1), w(2, 'Settings', process_name='ZaloCall.exe')], True)
        for _ in range(2):
            self.assertFalse(mon.update([w(1), w(2, process_name='ZaloCall.exe')], True)[0])
        self.assertEqual(len(mon.update([w(1), w(2, process_name='ZaloCall.exe')], True)[0]), 1)

    def test_named_call_inbound(self):
        mon = ZaloCallDetector()
        mon.update([w(1)], True)
        signals, _ = mon.update([w(1), w(2, 'Cuộc gọi đến - Zalo')], True)
        self.assertEqual(signals, [])
        signals, active = mon.update([w(1), w(2, 'Cuộc gọi đến - Zalo')], True)
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0].key, 2)
        self.assertIn(2, active)

    def test_outbound_call(self):
        mon = ZaloCallDetector()
        mon.update([w(1)], True)
        mon.update([w(1), w(3, 'Video Call with A')], True)
        signals, _ = mon.update([w(1), w(3, 'Video Call with A')], True)
        self.assertEqual(len(signals), 1)

    def test_call_process_window_needs_three_polls(self):
        mon = ZaloCallDetector()
        mon.update([w(1)], True)
        self.assertFalse(mon.update([w(1), w(4, '', process_name='ZaloCall.exe')], True)[0])
        self.assertFalse(mon.update([w(1), w(4, '', process_name='ZaloCall.exe')], True)[0])
        self.assertEqual(len(mon.update([w(1), w(4, '', process_name='ZaloCall.exe')], True)[0]), 1)

    def test_profile_photo_and_generic_chat_never_signal(self):
        for process in ('Zalo.exe', 'ZaloCall.exe'):
            for title in ('Thông tin tài khoản', 'Thông tin cá nhân', 'Profile', 'Trình xem ảnh', 'Cuộc gọi kết thúc'):
                mon = ZaloCallDetector()
                mon.update([w(1)], True)
                for _ in range(10):
                    signals, active = mon.update([w(1), w(2, title, process_name=process)], True)
                    self.assertFalse(signals, (process, title))
                    self.assertNotIn(2, active)
        for title in ('', 'Zalo', 'Bạn A', 'Đang kết nối'):
            mon = ZaloCallDetector()
            mon.update([w(1)], True)
            for _ in range(10):
                self.assertFalse(mon.update([w(1), w(2, title)], True)[0])

    def test_short_lived_call_process_toast_does_not_signal(self):
        mon = ZaloCallDetector()
        mon.update([w(1)], True)
        for _ in range(2):
            self.assertFalse(mon.update([w(1), w(2, '', process_name='ZaloCall.exe')], True)[0])
        self.assertEqual(mon.update([w(1)], True), ([], set()))

    def test_existing_call_process_at_start_is_detected(self):
        mon = ZaloCallDetector()
        window = w(2, '', process_name='ZaloCall.exe')
        mon.update([window], True)
        mon.update([window], True)
        self.assertEqual(len(mon.update([window], True)[0]), 1)

    def test_decline_no_reprompt(self):
        mon = ZaloCallDetector()
        mon.update([w(1)], True)
        mon.update([w(1), w(5, 'Gọi thoại - Zalo')], True)
        sig, _ = mon.update([w(1), w(5, 'Gọi thoại - Zalo')], True)
        self.assertEqual(len(sig), 1)
        mon.dismiss(5)
        for _ in range(10):
            self.assertFalse(mon.update([w(1), w(5, 'Gọi thoại - Zalo')], True)[0])

    def test_settings_ignored(self):
        mon = ZaloCallDetector()
        mon.update([w(1)], True)
        for _ in range(4):
            sig, _ = mon.update([w(1), w(5, 'Cài đặt Zalo')], True)
            self.assertFalse(sig)

    def test_process_match_excludes_self(self):
        self.assertTrue(is_zalo_process('Zalo.exe'))
        self.assertTrue(is_zalo_process('ZaloCall.exe'))
        self.assertFalse(is_zalo_process('ZaloCallCompanion.exe'))

    def test_titles_not_chat_history(self):
        self.assertTrue(looks_like_call_title('Đang gọi video - Zalo'))
        self.assertFalse(looks_like_call_title('Lịch sử cuộc gọi'))
        self.assertFalse(looks_like_call_title('Zalo'))


if __name__ == '__main__':
    unittest.main()
