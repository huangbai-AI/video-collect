import csv
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import store


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = store.connect(os.path.join(self.tmp.name, "t.db"))

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def item(self, vid, **kw):
        return {"vid": vid, "url": f"https://x/{vid}", **kw}

    def test_validate_rejects_bad_payloads(self):
        for bad in (None, [], {"platform": "yt", "list": "a", "items": []},
                    {"platform": "xhs", "list": "", "items": []},
                    {"platform": "xhs", "list": "fav", "items": "no"}):
            with self.assertRaises(ValueError):
                store.validate(bad)

    def test_validate_drops_items_without_id_or_url(self):
        _, _, items = store.validate({"platform": "xhs", "list": "fav",
                                      "items": [self.item("a"), {"vid": "b"}, {"url": "u"}, "junk"]})
        self.assertEqual([i["vid"] for i in items], ["a"])

    def test_ingest_counts_new_and_dedupes(self):
        _, _, items = store.validate({"platform": "douyin", "list": "like", "items": [self.item("1"), self.item("2")]})
        self.assertEqual(store.ingest(self.conn, "douyin", "like", items), 2)
        self.assertEqual(store.ingest(self.conn, "douyin", "like", items), 0)

    def test_same_video_in_second_list_merges_lists(self):
        _, _, items = store.validate({"platform": "xhs", "list": "fav", "items": [self.item("n1", title="t")]})
        store.ingest(self.conn, "xhs", "fav", items)
        _, _, again = store.validate({"platform": "xhs", "list": "liked", "items": [self.item("n1")]})
        self.assertEqual(store.ingest(self.conn, "xhs", "liked", again), 1)
        row = self.conn.execute("SELECT lists, title FROM videos WHERE vid='n1'").fetchone()
        self.assertEqual(row["lists"], "fav,liked")
        self.assertEqual(row["title"], "t")  # not overwritten by missing value

    def test_same_vid_on_different_platforms_is_distinct(self):
        _, _, items = store.validate({"platform": "xhs", "list": "fav", "items": [self.item("same")]})
        store.ingest(self.conn, "xhs", "fav", items)
        self.assertEqual(store.ingest(self.conn, "douyin", "like", items), 1)

    def test_x_likes_can_be_ingested_and_deduplicated(self):
        payload = {"platform": "x", "list": "liked", "items": [
            {"vid": "123456789", "url": "https://x.com/example/status/123456789",
             "title": "视频", "author": "example", "likes": 12}]}
        platform, list_name, items = store.validate(payload)
        self.assertEqual(store.ingest(self.conn, platform, list_name, items), 1)
        self.assertEqual(store.ingest(self.conn, platform, list_name, items), 0)
        row = self.conn.execute("SELECT platform, lists, title FROM videos WHERE vid=?",
                                ("123456789",)).fetchone()
        self.assertEqual(tuple(row), ("x", "liked", "视频"))

    def test_export_csv(self):
        _, _, items = store.validate({"platform": "xhs", "list": "fav", "items": [self.item("a", title="标题")]})
        store.ingest(self.conn, "xhs", "fav", items)
        out, n = store.export_csv(self.conn, os.path.join(self.tmp.name, "o.csv"))
        with open(out, encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual((n, rows[0]["title"]), (1, "标题"))


    def test_export_new_records_batches_without_repeating_videos(self):
        _, _, first = store.validate({"platform": "xhs", "list": "fav",
                                      "items": [self.item("a"), self.item("b")]})
        store.ingest(self.conn, "xhs", "fav", first)
        path1 = os.path.join(self.tmp.name, "batch1.csv")
        self.assertEqual(store.export_new_csv(self.conn, path1)[1], 2)
        self.assertEqual(store.export_new_csv(self.conn, os.path.join(self.tmp.name, "empty.csv")),
                         (None, 0))
        _, _, second = store.validate({"platform": "xhs", "list": "liked",
                                       "items": [self.item("a"), self.item("c")]})
        store.ingest(self.conn, "xhs", "liked", second)
        path2 = os.path.join(self.tmp.name, "batch2.csv")
        self.assertEqual(store.export_new_csv(self.conn, path2)[1], 1)
        with open(path2, encoding="utf-8-sig", newline="") as f:
            self.assertEqual([r["vid"] for r in csv.DictReader(f)], ["c"])
        status = store.export_status(self.conn)
        self.assertEqual((status["exported"], status["pending"], len(status["batches"])),
                         (3, 0, 2))

    def test_existing_csv_can_seed_export_history(self):
        _, _, first = store.validate({"platform": "instagram", "list": "saved",
                                      "items": [self.item("a"), self.item("b")]})
        store.ingest(self.conn, "instagram", "saved", first)
        old_csv = os.path.join(self.tmp.name, "old.csv")
        store.export_csv(self.conn, old_csv)
        self.assertEqual(store.mark_exported_from_csv(self.conn, old_csv)["marked"], 2)
        self.assertEqual(store.mark_exported_from_csv(self.conn, old_csv)["marked"], 0)
        self.assertEqual(store.export_new_csv(self.conn, os.path.join(self.tmp.name, "none.csv")),
                         (None, 0))
        _, _, latest = store.validate({"platform": "instagram", "list": "saved",
                                       "items": [self.item("c")]})
        store.ingest(self.conn, "instagram", "saved", latest)
        new_csv = os.path.join(self.tmp.name, "new.csv")
        self.assertEqual(store.export_new_csv(self.conn, new_csv)[1], 1)
        with open(new_csv, encoding="utf-8-sig", newline="") as f:
            self.assertEqual([r["vid"] for r in csv.DictReader(f)], ["c"])


if __name__ == "__main__":
    unittest.main()
