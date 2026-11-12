"""Integration test: reloading a batch must not change any warehouse row count.

Needs local PostgreSQL with all batches loaded and data/lake present; skipped otherwise (e.g. in CI).
"""
import subprocess
import sys
import unittest
from pathlib import Path

from dotenv import load_dotenv

from loader.curated_to_warehouse import connect

BATCH = "2018-03"
TABLES = ["dw.fact_order_item", "dw.fact_order_fulfilment", "dw.review_text",
          "dw.dim_seller", "dw.dim_customer", "dw.dim_product"]


def counts() -> dict:
    conn = connect()
    try:
        with conn.cursor() as cur:
            result = {}
            for table in TABLES:
                cur.execute(f"SELECT count(*) FROM {table}")
                result[table] = cur.fetchone()[0]
            return result
    finally:
        conn.close()


def available() -> bool:
    load_dotenv()
    try:
        return Path(f"data/lake/curated/orders/batch_id={BATCH}").exists() and counts()["dw.fact_order_item"] > 0
    except Exception:
        return False


@unittest.skipUnless(available(), "needs local PostgreSQL with loaded batches and data/lake")
class TestWarehouseRerun(unittest.TestCase):
    def test_rerun_batch_changes_nothing(self):
        before = counts()
        result = subprocess.run([sys.executable, "-m", "loader.curated_to_warehouse", "--batch", BATCH],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        self.assertEqual(counts(), before)


if __name__ == "__main__":
    unittest.main()
