import os
import sys
import unittest
from datetime import datetime
from decimal import Decimal

from pyspark.sql import SparkSession

from transform import rules as R


def ids(df, col="id"):
    return sorted(r[col] for r in df.collect())


class TestRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
        cls.spark = (SparkSession.builder.master("local[1]").appName("test_rules")
                     .config("spark.ui.enabled", "false").getOrCreate())

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()

    def df(self, rows, cols):
        return self.spark.createDataFrame(rows, cols)

    def test_null_key(self):
        good, bad = R.null_key("a", "b")(self.df([(1, "x", "y"), (2, None, "y"), (3, "x", None)], ["id", "a", "b"]))
        self.assertEqual(ids(good), [1])
        self.assertEqual(ids(bad), [2, 3])
        self.assertEqual({r.reject_reason for r in bad.collect()}, {"null_key"})

    def test_duplicate_key_keeps_one(self):
        good, bad = R.duplicate_key("k")(self.df([(1, "a"), (2, "a"), (3, "b")], ["id", "k"]))
        self.assertEqual(good.count(), 2)
        self.assertEqual(bad.count(), 1)
        self.assertNotIn("_rn", good.columns)

    def test_duplicate_key_keeps_latest(self):
        rows = [(1, "r", datetime(2018, 1, 1)), (2, "r", datetime(2018, 2, 1))]
        good, bad = R.duplicate_key("k", latest_by="ts")(self.df(rows, ["id", "k", "ts"]))
        self.assertEqual(ids(good), [2])
        self.assertEqual(ids(bad), [1])

    def test_invalid_status(self):
        rows = [(1, "delivered"), (2, "lost")]
        good, bad = R.not_in("s", R.ORDER_STATUSES, "invalid_status")(self.df(rows, ["id", "s"]))
        self.assertEqual((ids(good), ids(bad)), ([1], [2]))

    def test_before_allows_null(self):
        rows = [(1, datetime(2018, 1, 2), datetime(2018, 1, 1)),
                (2, datetime(2018, 1, 1), datetime(2018, 1, 2)),
                (3, None, datetime(2018, 1, 1))]
        good, bad = R.before("delivered", "shipped", "delivered_before_shipped")(
            self.df(rows, "id int, delivered timestamp, shipped timestamp"))
        self.assertEqual((ids(good), ids(bad)), ([1, 3], [2]))

    def test_non_positive_price(self):
        rows = [(1, Decimal("10.00")), (2, Decimal("0.00")), (3, Decimal("-5.00")), (4, None)]
        good, bad = R.ITEM_RULES[2](self.df(rows, "id int, price decimal(10,2)"))
        self.assertEqual((ids(good), ids(bad)), ([1], [2, 3, 4]))

    def test_negative_freight(self):
        rows = [(1, Decimal("0.00")), (2, Decimal("-0.01"))]
        good, bad = R.ITEM_RULES[3](self.df(rows, "id int, freight_value decimal(10,2)"))
        self.assertEqual((ids(good), ids(bad)), ([1], [2]))

    def test_location_rules(self):
        rows = [(1, " sp ", "01001", " Sao Paulo "), (2, "XX", "01001", "a"), (3, "RJ", "123", "b")]
        df = R.clean_location(self.df(rows, ["seller_id", "seller_state", "seller_zip_code_prefix", "seller_city"]),
                              "seller")
        good, bad = R.apply_rules(df, R.location_rules("seller_id", "seller"))
        row = good.collect()[0]
        self.assertEqual((row.seller_id, row.seller_state, row.seller_city), (1, "SP", "sao paulo"))
        self.assertEqual({(r.seller_id, r.reject_reason) for r in bad.collect()},
                         {(2, "invalid_state"), (3, "invalid_zip")})

    def test_invalid_score(self):
        rows = [("r1", "o1", 5, datetime(2018, 1, 1)), ("r2", "o2", 6, datetime(2018, 1, 1))]
        good, bad = R.apply_rules(self.df(rows, ["review_id", "order_id", "review_score", "review_answer_timestamp"]),
                                  R.REVIEW_RULES)
        self.assertEqual((ids(good, "review_id"), ids(bad, "review_id")), (["r1"], ["r2"]))

    def test_exists_in(self):
        orders = self.df([("o1",)], ["order_id"])
        good, bad = R.exists_in(orders, "order_id", "unknown_order")(self.df([(1, "o1"), (2, "o2")], ["id", "order_id"]))
        self.assertEqual((ids(good), ids(bad)), ([1], [2]))
        self.assertEqual(bad.collect()[0].reject_reason, "unknown_order")

    def test_clean_products(self):
        products = self.df([("p1", "beleza_saude", 10), ("p2", None, 5), ("p3", "pc_gamer", 1)],
                           ["product_id", "product_category_name", "product_name_lenght"])
        translation = self.df([("beleza_saude", "health_beauty")],
                              ["product_category_name", "product_category_name_english"])
        out = {r.product_id: r for r in R.clean_products(products, translation).collect()}
        self.assertIn("product_name_length", out["p1"].asDict())
        self.assertEqual(out["p1"].product_category_name_english, "health_beauty")
        self.assertEqual(out["p2"].product_category_name_english, "unknown")
        self.assertEqual(out["p3"].product_category_name_english, "pc_gamer")


if __name__ == "__main__":
    unittest.main()
