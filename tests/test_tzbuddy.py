import io
import unittest
from contextlib import redirect_stdout
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from tzbuddy.core import meeting_slots, offset_str, parse_when, resolve, best_compromise
from tzbuddy.cli import main

TOKYO, NY, LON = ZoneInfo("Asia/Tokyo"), ZoneInfo("America/New_York"), ZoneInfo("Europe/London")


class ResolveTests(unittest.TestCase):
    def test_names(self):
        self.assertEqual(resolve("Asia/Tokyo")[1], TOKYO)
        self.assertEqual(resolve("tokyo")[1], TOKYO)
        self.assertEqual(resolve("New York")[1], NY)
        self.assertEqual(resolve("nyc")[1], NY)
        self.assertEqual(resolve("beijing")[1], ZoneInfo("Asia/Shanghai"))
        self.assertEqual(resolve("europe/london")[1], LON)

    def test_offsets(self):
        lbl, tz = resolve("+05:30")
        self.assertEqual(lbl, "UTC+05:30")
        self.assertEqual(tz.utcoffset(None), timedelta(hours=5, minutes=30))
        self.assertEqual(resolve("UTC-8")[1].utcoffset(None), timedelta(hours=-8))

    def test_unknown_suggests(self):
        with self.assertRaises(ValueError) as cm:
            resolve("tokio")
        self.assertIn("tokyo", str(cm.exception))


class ParseTests(unittest.TestCase):
    def test_formats(self):
        d = date(2026, 3, 1)
        self.assertEqual(parse_when("3pm", TOKYO, d).hour, 15)
        self.assertEqual(parse_when("12am", TOKYO, d).hour, 0)
        self.assertEqual(parse_when("09:45", TOKYO, d).minute, 45)
        self.assertEqual(parse_when("tomorrow 9am", TOKYO, d), datetime(2026, 3, 2, 9, tzinfo=TOKYO))
        self.assertEqual(parse_when("2026-07-04 18:00", NY).date(), date(2026, 7, 4))
        for bad in ("25:00", "13pm", "lunch"):
            with self.assertRaises(ValueError):
                parse_when(bad, TOKYO, d)

    def test_dst_offsets(self):
        self.assertEqual(offset_str(datetime(2026, 1, 15, 12, tzinfo=NY)), "UTC-05:00")
        self.assertEqual(offset_str(datetime(2026, 7, 15, 12, tzinfo=NY)), "UTC-04:00")


class MeetTests(unittest.TestCase):
    def test_london_newyork_overlap(self):
        slots = meeting_slots([LON, NY], date(2026, 1, 14))
        # London 14:00-17:00 starts = NY 09:00-12:00 (London 9–18, NY 9–18, 60 min)
        self.assertEqual([s.strftime("%H:%M") for s in slots][:1], ["14:00"])
        self.assertEqual(slots[-1].strftime("%H:%M"), "17:00")

    def test_no_overlap_and_compromise(self):
        zs = [TOKYO, NY, LON]
        self.assertEqual(meeting_slots(zs, date(2026, 1, 14)), [])
        t, pain = best_compromise(zs, date(2026, 1, 14))
        self.assertGreater(pain, 0)

    def test_cli(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(main(["at", "2026-01-14 09:00", "tokyo", "london", "--json"]), 0)
        self.assertIn("00:00", buf.getvalue())
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(["meet", "tokyo", "nyc", "london", "--date", "2026-01-14"]), 1)
            self.assertEqual(main(["UTC", "seoul"]), 0)
        self.assertEqual(main(["now", "atlantis"]), 2)


if __name__ == "__main__":
    unittest.main()
