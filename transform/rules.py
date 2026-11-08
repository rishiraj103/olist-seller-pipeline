"""Data-quality rules as pure functions: each takes a DataFrame and returns (good_df, bad_df).

Bad rows carry a `reject_reason` column. A row is checked by the next rule only if it passed the previous one.
"""
from functools import reduce
from typing import Callable

from pyspark.sql import Column, DataFrame, Window
from pyspark.sql import functions as F

Rule = Callable[[DataFrame], tuple[DataFrame, DataFrame]]

ORDER_STATUSES = ["created", "approved", "invoiced", "processing", "shipped", "delivered", "canceled", "unavailable"]
BR_STATES = ["AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA", "PB", "PE", "PI",
             "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO"]
# Categories missing from the translation file (see docs/data_profile.md).
CATEGORY_FIXES = {"pc_gamer": "pc_gamer",
                  "portateis_cozinha_e_preparadores_de_alimentos": "portable_kitchen_food_preparers"}


def split(df: DataFrame, is_bad: Column, reason: str) -> tuple[DataFrame, DataFrame]:
    flag = F.coalesce(is_bad, F.lit(False))
    return df.filter(~flag), df.filter(flag).withColumn("reject_reason", F.lit(reason))


def null_key(*keys: str) -> Rule:
    return lambda df: split(df, reduce(lambda a, b: a | b, [F.col(k).isNull() for k in keys]), "null_key")


def duplicate_key(*keys: str, latest_by: str | None = None) -> Rule:
    """Keep one row per key (the latest by `latest_by` if given); reject the rest."""
    def rule(df: DataFrame) -> tuple[DataFrame, DataFrame]:
        df = df.withColumn("_id", F.monotonically_increasing_id())
        order = [F.col(latest_by).desc_nulls_last(), "_id"] if latest_by else ["_id"]
        ranked = df.withColumn("_rn", F.row_number().over(Window.partitionBy(*keys).orderBy(*order)))
        good, bad = split(ranked, F.col("_rn") > 1, "duplicate_key")
        return good.drop("_rn", "_id"), bad.drop("_rn", "_id")
    return rule


def check(condition_is_bad: Callable[[], Column], reason: str) -> Rule:
    return lambda df: split(df, condition_is_bad(), reason)


def not_in(col: str, allowed: list, reason: str) -> Rule:
    return check(lambda: ~F.col(col).isin(allowed), reason)


def before(later: str, earlier: str, reason: str) -> Rule:
    """Reject when `later` is before `earlier`; NULL dates pass (milestone not reached)."""
    return check(lambda: F.col(later) < F.col(earlier), reason)


def apply_rules(df: DataFrame, rules: list[Rule]) -> tuple[DataFrame, DataFrame | None]:
    bads = []
    for rule in rules:
        df, bad = rule(df)
        bads.append(bad)
    return df, reduce(DataFrame.unionByName, bads) if bads else None


# ---- per-table rule lists -------------------------------------------------------------------------------------

ORDER_RULES = [
    null_key("order_id", "customer_id"),
    duplicate_key("order_id"),
    not_in("order_status", ORDER_STATUSES, "invalid_status"),
    before("order_approved_at", "order_purchase_timestamp", "approved_before_purchase"),
    before("order_delivered_customer_date", "order_delivered_carrier_date", "delivered_before_shipped"),
]

ITEM_RULES = [
    null_key("order_id", "order_item_id", "product_id", "seller_id"),
    duplicate_key("order_id", "order_item_id"),
    check(lambda: F.col("price").isNull() | (F.col("price") <= 0), "non_positive_price"),
    check(lambda: F.col("freight_value").isNull() | (F.col("freight_value") < 0), "negative_freight"),
]


def location_rules(key: str, prefix: str) -> list[Rule]:
    return [
        null_key(key),
        duplicate_key(key),
        not_in(f"{prefix}_state", BR_STATES, "invalid_state"),
        check(lambda: ~F.col(f"{prefix}_zip_code_prefix").rlike(r"^\d{5}$"), "invalid_zip"),
    ]


REVIEW_RULES = [
    null_key("review_id", "order_id"),
    duplicate_key("review_id", "order_id", latest_by="review_answer_timestamp"),
    check(lambda: ~F.col("review_score").between(1, 5), "invalid_score"),
]

PRODUCT_RULES = [null_key("product_id"), duplicate_key("product_id")]


# ---- cleaning (no rows rejected) ------------------------------------------------------------------------------

def clean_location(df: DataFrame, prefix: str) -> DataFrame:
    return (df.withColumn(f"{prefix}_state", F.upper(F.trim(f"{prefix}_state")))
              .withColumn(f"{prefix}_city", F.lower(F.trim(f"{prefix}_city"))))


def clean_products(products: DataFrame, translation: DataFrame) -> DataFrame:
    fixes = translation.sparkSession.createDataFrame(list(CATEGORY_FIXES.items()), translation.columns)
    names = translation.unionByName(fixes).dropDuplicates(["product_category_name"])
    return (products
            .withColumnRenamed("product_name_lenght", "product_name_length")
            .withColumnRenamed("product_description_lenght", "product_description_length")
            .join(names, "product_category_name", "left")
            .withColumn("product_category_name", F.coalesce("product_category_name", F.lit("unknown")))
            .withColumn("product_category_name_english",
                        F.coalesce("product_category_name_english", F.lit("unknown"))))
