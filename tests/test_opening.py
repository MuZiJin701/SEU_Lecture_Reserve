"""Reservation-window scheduling without network traffic or wall-clock waits."""

import unittest
from datetime import datetime

from app import scan_delay
from model import SHANGHAI


class OpeningTests(unittest.TestCase):
    def test_acceleration_follows_actual_opening_time_and_includes_scan_work(self):
        for hour, minute in ((9, 0), (12, 0), (19, 0), (9, 17)):
            with self.subTest(hour=hour, minute=minute):
                start = datetime(2030, 1, 1, hour, minute, tzinfo=SHANGHAI)
                details = [dict(reason='reservation_not_started', reservation_start=start.isoformat())]
                at = start.timestamp()
                self.assertEqual(scan_delay(details, at - 35, 3, 10), (5, False))
                self.assertEqual(scan_delay(details, at - 30, 0.4, 10), (0.6, True))
                self.assertEqual(scan_delay(details, at + 2, 3, 10), (0, True))
                self.assertEqual(scan_delay(details, at + 61, 3, 10), (0, True))
                self.assertEqual(scan_delay(details, at + 600, 3, 10), (0, True))
                self.assertEqual(scan_delay(details, at + 601, 3, 10), (10, False))

    def test_acceleration_stops_at_reservation_deadline(self):
        start = datetime(2030, 1, 1, 9, tzinfo=SHANGHAI)
        details = [dict(reason='candidate', reservation_start=start.isoformat(),
                        reservation_end='2030-01-01T09:02:00+08:00')]
        self.assertEqual(scan_delay(details, start.timestamp() + 119, 3, 10), (0, True))
        self.assertEqual(scan_delay(details, start.timestamp() + 121, 3, 10), (10, False))

    def test_invalid_remembered_windows_do_not_trigger_acceleration(self):
        for details in (None, {}, [None], [dict(reason='candidate', reservation_start='PRIVATE')],
                        [dict(reason='candidate', reservation_start='2030-01-01T09:00:00')]):
            with self.subTest(details=details):
                self.assertEqual(scan_delay(details, 100, 0, 10), (10, False))

    def test_missing_or_excluded_windows_keep_normal_interval(self):
        self.assertEqual(scan_delay([], 100, 3, 10), (10, False))
        self.assertEqual(scan_delay([dict(reason='reservation_not_started', reservation_start=None)],
                                    100, 3, 10), (10, False))
        details = [dict(reason='campus_not_selected', reservation_start='2030-01-01T09:00:00+08:00')]
        at = datetime(2030, 1, 1, 9, tzinfo=SHANGHAI).timestamp()
        self.assertEqual(scan_delay(details, at, 0, 10), (10, False))


if __name__ == '__main__':
    unittest.main()
