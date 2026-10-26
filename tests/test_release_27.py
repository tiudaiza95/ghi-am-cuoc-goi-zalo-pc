import unittest, tempfile, csv
from pathlib import Path
from recording_library import filter_date_range, export_recordings_csv, list_recordings, atomic_json
class Release27Tests(unittest.TestCase):
 def test_inclusive_date_range_and_validation(self):
  rows=[{'timestamp':'2026-10-26T23:59:00'},{'timestamp':'2026-10-27T00:00:00'},{'timestamp':'2026-10-28T00:00:00'}]
  self.assertEqual(filter_date_range(rows,'27/10/2026','27/10/2026'),[rows[1]])
  self.assertEqual(filter_date_range(rows,'','27/10/2026'),rows[:2])
  self.assertEqual(filter_date_range(rows,'27/10/2026',''),rows[1:])
  for a,b in [('31/02/2026',''),('28/10/2026','27/10/2026')]:
   with self.assertRaises(ValueError):filter_date_range(rows,a,b)
 def test_csv_unicode_newline_formula_and_no_private_path(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'out.csv'
   export_recordings_csv([{'name':'=Vợ yêu.mp3','path':'private/path','date':'27/10/2026','size':99,'metadata':{'note':' @SUM(1,2)\nGhi chú','favorite':True}}],path)
   self.assertTrue(path.read_bytes().startswith(b'\xef\xbb\xbf'))
   with path.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.reader(f))
   self.assertEqual(rows[1][0],"'=Vợ yêu.mp3")
   self.assertEqual(rows[1][6],"' @SUM(1,2)\nGhi chú")
   self.assertNotIn('private/path',path.read_text(encoding='utf-8-sig'))
   self.assertEqual(len(list(Path(folder).iterdir())),1)
 def test_malformed_duration_does_not_break_library(self):
  with tempfile.TemporaryDirectory() as folder:
   for n,value in enumerate(['oops',float('inf'),-1,{'bad':1}]):
    p=Path(folder)/f'{n}.mp3';p.write_bytes(b'dummy')
    atomic_json(p.with_suffix('.mp3.json'),{'duration':value})
   rows=list_recordings(folder)
   self.assertEqual(len(rows),4)
   self.assertTrue(all(r['duration'] is None for r in rows))
