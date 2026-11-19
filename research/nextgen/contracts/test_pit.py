import unittest
from datetime import datetime,timedelta,timezone
from pit import PointInTimeRecord,assert_point_in_time,purged_training_rows
def t(day,h=0):return datetime(2025,1,day,h,tzinfo=timezone.utc)

class PointInTimeTests(unittest.TestCase):
    def test_valid(self):
        r=PointInTimeRecord("issuer:001","v1",t(1),t(2),t(3))
        assert_point_in_time([r],t(4),timedelta(hours=1))
    def test_same_time_future(self):
        r=PointInTimeRecord("issuer:001","v1",t(1),t(2),t(3))
        with self.assertRaises(ValueError):assert_point_in_time([r],t(3))
        with self.assertRaises(ValueError):assert_point_in_time([r],t(3,1),timedelta(hours=1))
    def test_missing_timezone(self):
        with self.assertRaises(ValueError):
            PointInTimeRecord("i","v",datetime(2025,1,1),t(2),t(3))
    def test_bad_order(self):
        with self.assertRaises(ValueError):
            PointInTimeRecord("i","v",t(4),t(2),t(3))
    def test_duplicate(self):
        r=PointInTimeRecord("i","v",t(1),t(2),t(3))
        with self.assertRaises(ValueError):assert_point_in_time([r,r],t(4))
    def test_purge_by_target_end_not_start(self):
        decisions=[t(1),t(2),t(3)]; ends=[t(2),t(5),t(8)]
        self.assertEqual(purged_training_rows(decisions,ends,t(6)),[True,True,False])
        self.assertEqual(purged_training_rows(decisions,ends,t(6),timedelta(days=2)),[True,False,False])
if __name__=="__main__":unittest.main()
