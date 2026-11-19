import unittest
from datetime import datetime,timedelta,timezone
from research.nextgen.contracts.pit import PointInTimeRecord,assert_point_in_time,purged_training_rows
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

    def test_timezone_normalisation(self):
        from datetime import timezone
        eastern=timezone(timedelta(hours=-5))
        r=PointInTimeRecord("issuer","v1",t(1),t(2),datetime(2025,1,2,20,tzinfo=eastern))
        assert_point_in_time([r],t(4))
    def test_negative_latency_and_embargo(self):
        r=PointInTimeRecord("issuer","v1",t(1),t(2),t(3))
        with self.assertRaises(ValueError):assert_point_in_time([r],t(4),timedelta(days=-1))
        with self.assertRaises(ValueError):purged_training_rows([t(1)],[t(2)],t(4),timedelta(days=-1))
    def test_target_overlap_purged_even_if_features_past(self):
        self.assertEqual(purged_training_rows([t(1),t(2)],[t(4),t(6)],t(4)),[False,False])

    def test_rejects_empty_ids_wrong_records_and_impossible_target_end(self):
        with self.assertRaises(ValueError):
            PointInTimeRecord("", "v", t(1), t(2), t(3))
        with self.assertRaises(TypeError): assert_point_in_time(["ticker:NOW"], t(4))
        with self.assertRaises(ValueError): purged_training_rows([t(4)], [t(3)], t(6))
if __name__=="__main__":unittest.main()
