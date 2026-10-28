import csv
import os
import tempfile
import unittest

from arknights_mower.utils.csv_utils import EmptyDataError, read_csv_rows, read_dicts


class TestCsvEncodingFallback(unittest.TestCase):
    """验证 CSV 读取兼容 UTF-8、UTF-8 BOM 与 GBK。"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _make_csv(self, encoding: str, name: str = "report.csv") -> str:
        path = os.path.join(self.temp_dir, name)
        with open(path, "w", encoding=encoding, newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["", "col1", "col2"])
            writer.writerow(["2026-01-01", "数据1", 1])
            writer.writerow(["2026-01-02", "数据2", 2])
        return path

    def test_read_utf8_csv(self):
        path = self._make_csv("utf-8")
        rows = read_dicts(path, encoding="gbk")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["Unnamed: 0"], "2026-01-01")
        self.assertEqual(rows[0]["col1"], "数据1")

    def test_read_gbk_csv(self):
        path = self._make_csv("gbk")
        rows = read_dicts(path, encoding="gbk")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["col1"], "数据1")

    def test_read_utf8_bom_csv(self):
        path = self._make_csv("utf-8-sig", "report_bom.csv")
        rows = read_dicts(path, encoding="gbk")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["Unnamed: 0"], "2026-01-01")
        self.assertNotIn("\ufeff", rows[0])

    def test_read_csv_rows_without_header(self):
        path = self._make_csv("gbk")
        rows = read_csv_rows(path, header=False, encoding="gbk")
        self.assertEqual(rows[0], ["", "col1", "col2"])
        self.assertEqual(rows[1][0], "2026-01-01")

    def test_empty_csv_raises(self):
        path = os.path.join(self.temp_dir, "empty.csv")
        open(path, "w", encoding="utf-8").close()
        with self.assertRaises(EmptyDataError):
            read_dicts(path)


if __name__ == "__main__":
    unittest.main()
