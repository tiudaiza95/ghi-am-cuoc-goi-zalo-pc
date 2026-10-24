import unittest
from datetime import datetime
from recording_names import caller_from_title, recording_stem


class NameTests(unittest.TestCase):
    def test_call_titles(self):
        for title in ('Cuộc gọi đến - Vợ yêu - Zalo', 'Vợ yêu - Gọi video',
                      'Video call with Vợ yêu', 'Zalo - Cuộc gọi từ Vợ yêu'):
            self.assertEqual(caller_from_title(title), 'Vợ yêu')

    def test_generic_titles_are_not_names(self):
        for title in ('Zalo', '', 'Incoming call', 'Cuộc gọi đến - Zalo', 'Tin nhắn của Vợ yêu'):
            self.assertEqual(caller_from_title(title), '')

    def test_time_and_unicode(self):
        self.assertEqual(recording_stem('Vợ yêu', datetime(2026, 10, 22, 14, 30, 5)),
                         'Vợ yêu - 14h30m05s - 22-10-2026')

    def test_unsafe_names(self):
        when = datetime(2026, 10, 22)
        self.assertTrue(recording_stem('..\\A:/B*?"<>|', when).startswith('A B - '))
        self.assertTrue(recording_stem('CON', when).startswith('_CON - '))
        self.assertTrue(recording_stem('... ', when).startswith('Zalo - '))
        self.assertLess(len(recording_stem('a' * 500, when)), 120)
