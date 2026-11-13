import unittest

from ingest.on_batch_arrival import check_manifest

MANIFEST = {"batch_id": "2018-01", "files": [{"name": "orders.csv", "md5": "aaa"}, {"name": "sellers.csv", "md5": "bbb"}]}
STORED = {"orders.csv": "aaa", "sellers.csv": "bbb"}


class TestManifest(unittest.TestCase):
    def test_ok(self):
        self.assertEqual(check_manifest(MANIFEST, STORED.get), [])

    def test_missing_file(self):
        self.assertEqual(check_manifest(MANIFEST, {"orders.csv": "aaa"}.get), ["missing file: sellers.csv"])

    def test_md5_mismatch(self):
        self.assertEqual(check_manifest(MANIFEST, {**STORED, "orders.csv": "zzz"}.get), ["md5 mismatch: orders.csv"])

    def test_bad_batch_id_and_no_files(self):
        self.assertEqual(len(check_manifest({"batch_id": "../x"}, STORED.get)), 2)


if __name__ == "__main__":
    unittest.main()
