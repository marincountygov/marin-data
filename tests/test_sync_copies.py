#!/usr/bin/env python3
"""Tests for scripts/sync_copies.py, run against a small made-up marin-data and consumer."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("sync_copies", HERE / "scripts" / "sync_copies.py")
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


class SyncCopiesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.data, self.app = root / "marin-data", root / "marin-app"
        (self.data / "organizations").mkdir(parents=True)
        (self.data / "brand" / "alpha" / "assets").mkdir(parents=True)
        self.app.mkdir()
        (self.data / "organizations" / "list.json").write_text('{"a": 1}\n')
        (self.data / "brand" / "alpha" / "brand.json").write_text("alpha\n")
        (self.data / "brand" / "alpha" / "assets" / "logo.svg").write_text("<svg/>")
        (self.data / "consumers.json").write_text(json.dumps({"consumers": [{
            "repo": "marin-app", "sync": ["python3 ../marin-data/scripts/sync_copies.py ."], "build": ["node build.js"],
            "copies": [{"from": "organizations/list.json", "to": "data/list.json"},
                       {"from": "brand", "to": "brands", "dir": True, "ignore": ["*/index.html"]}]}]}))

    def tearDown(self):
        self.tmp.cleanup()

    def sync(self, check=False):
        return sync.run(self.data, self.app, check)[0]

    def test_a_file_is_copied_and_a_second_run_changes_nothing(self):
        done = self.sync()
        self.assertIn("copied data/list.json", done)
        self.assertEqual((self.app / "data" / "list.json").read_text(), '{"a": 1}\n')
        self.assertEqual(self.sync(), [])
        self.assertEqual(self.sync(check=True), [])

    def test_a_folder_is_copied_with_its_files_and_the_consumers_own_files_stay(self):
        self.sync()
        self.assertTrue((self.app / "brands" / "alpha" / "assets" / "logo.svg").is_file())
        (self.app / "brands" / "alpha" / "index.html").write_text("ours")
        (self.app / "brands" / "alpha" / ".DS_Store").write_text("junk")
        self.assertEqual(self.sync(check=True), [], "an ignored file and a .DS_Store are not problems")
        self.sync()
        self.assertTrue((self.app / "brands" / "alpha" / "index.html").is_file())

    def test_check_reports_a_missing_a_changed_and_a_left_over_file(self):
        self.sync()
        (self.app / "data" / "list.json").write_text("changed")
        (self.app / "brands" / "alpha" / "brand.json").unlink()
        (self.app / "brands" / "alpha" / "old.txt").write_text("old")
        problems = self.sync(check=True)
        self.assertIn("data/list.json: differs from marin-data", problems)
        self.assertIn("brands/alpha/brand.json: missing", problems)
        self.assertIn("brands/alpha/old.txt: not in marin-data any more", problems)

    def test_sync_removes_what_marin_data_no_longer_has(self):
        self.sync()
        (self.data / "brand" / "alpha" / "assets" / "logo.svg").unlink()
        (self.app / "brands" / "beta").mkdir()
        (self.app / "brands" / "beta" / "brand.json").write_text("gone")
        done = self.sync()
        self.assertIn("removed brands/beta/ (not in marin-data any more)", done)
        self.assertIn("removed brands/alpha/assets/logo.svg", done)
        self.assertFalse((self.app / "brands" / "alpha" / "assets").exists(), "an empty folder is removed")
        self.assertFalse((self.app / "brands" / "beta").exists())

    def test_an_app_marin_data_does_not_list_stops_with_a_plain_message(self):
        other = self.app.parent / "marin-other"
        other.mkdir()
        with self.assertRaises(SystemExit) as caught:
            sync.run(self.data, other, True)
        self.assertIn("marin-other is not listed", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
