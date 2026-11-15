"""Raw CSV batch -> curated Parquet + rejected rows + dq_summary.json. Runs locally and on AWS Glue.

Local: python -m transform.raw_to_curated --batch_id 2018-02 --input data/batches/batch_id=2018-02 --output data/lake
Glue:  --batch_id 2018-02 --input s3://<bucket>/raw/batch_id=2018-02 --output s3://<bucket>
"""
import argparse
import json
import logging
import os
import sys
from pathlib import Path

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import DecimalType, IntegerType, StringType, StructField, StructType, TimestampType

try:
    from transform import rules as R
except ImportError:  # on Glue, rules.py is shipped flat via --extra-py-files
    import rules as R

log = logging.getLogger("raw_to_curated")


def schema(*cols: tuple[str, object]) -> StructType:
    return StructType([StructField(name, dtype(), True) for name, dtype in cols])


S, I, T = StringType, IntegerType, TimestampType
D = lambda: DecimalType(10, 2)  # noqa: E731

SCHEMAS = {
    "orders": schema(("order_id", S), ("customer_id", S), ("order_status", S), ("order_purchase_timestamp", T),
                     ("order_approved_at", T), ("order_delivered_carrier_date", T),
                     ("order_delivered_customer_date", T), ("order_estimated_delivery_date", T)),
    "order_items": schema(("order_id", S), ("order_item_id", I), ("product_id", S), ("seller_id", S),
                          ("shipping_limit_date", T), ("price", D), ("freight_value", D)),
    "order_reviews": schema(("review_id", S), ("order_id", S), ("review_score", I), ("review_comment_title", S),
                            ("review_comment_message", S), ("review_creation_date", T),
                            ("review_answer_timestamp", T)),
    "customers": schema(("customer_id", S), ("customer_unique_id", S), ("customer_zip_code_prefix", S),
                        ("customer_city", S), ("customer_state", S)),
    "sellers": schema(("seller_id", S), ("seller_zip_code_prefix", S), ("seller_city", S), ("seller_state", S)),
    "products": schema(("product_id", S), ("product_category_name", S), ("product_name_lenght", I),
                       ("product_description_lenght", I), ("product_photos_qty", I), ("product_weight_g", I),
                       ("product_length_cm", I), ("product_height_cm", I), ("product_width_cm", I)),
    "category_translation": schema(("product_category_name", S), ("product_category_name_english", S)),
}

RULES = {
    "orders": R.ORDER_RULES,
    "order_items": R.ITEM_RULES,
    "order_reviews": R.REVIEW_RULES,
    "customers": R.location_rules("customer_id", "customer"),
    "sellers": R.location_rules("seller_id", "seller"),
    "products": R.PRODUCT_RULES,
}


def read_csv(spark: SparkSession, path: str, table: str) -> DataFrame:
    # enforceSchema=False: a header that does not match the schema (renamed/missing column) fails the job
    return spark.read.csv(f"{path}/{table}.csv", schema=SCHEMAS[table], header=True, multiLine=True,
                          escape='"', timestampFormat="yyyy-MM-dd HH:mm:ss", enforceSchema=False)


def write_text(path: str, text: str) -> None:
    if path.startswith("s3://"):
        import boto3
        bucket, key = path[5:].split("/", 1)
        boto3.client("s3").put_object(Bucket=bucket, Key=key, Body=text.encode())
    else:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(text)


def run(spark: SparkSession, batch_id: str, src: str, out: str) -> dict:
    translation = read_csv(spark, src, "category_translation")
    prep = {
        "customers": lambda df: R.clean_location(df, "customer"),
        "sellers": lambda df: R.clean_location(df, "seller"),
        "products": lambda df: R.clean_products(df, translation),
    }
    summary = {"batch_id": batch_id, "tables": {}}
    good_orders = None
    for table, rules in RULES.items():  # orders first: items and reviews must belong to a passed order
        df = prep.get(table, lambda d: d)(read_csv(spark, src, table)).cache()
        if table in ("order_items", "order_reviews"):
            rules = rules + [R.exists_in(good_orders, "order_id", "unknown_order")]
        good, bad = R.apply_rules(df, rules)
        if table == "orders":
            good_orders = good.select("order_id").cache()
        good.write.mode("overwrite").parquet(f"{out}/curated/{table}/batch_id={batch_id}")
        by_rule = {r["reject_reason"]: r["count"] for r in bad.groupBy("reject_reason").count().collect()}
        if by_rule:
            bad.write.mode("overwrite").parquet(f"{out}/rejected/{table}/batch_id={batch_id}")
        read, rejected = df.count(), sum(by_rule.values())
        summary["tables"][table] = {"read": read, "passed": read - rejected, "rejected": rejected,
                                    "by_rule": by_rule}
        log.info("%s: read=%d rejected=%d %s", table, read, rejected, by_rule)
        df.unpersist()

    totals = summary["tables"].values()
    summary["rows_read"] = sum(t["read"] for t in totals)
    summary["rows_rejected"] = sum(t["rejected"] for t in totals)
    summary["reject_rate"] = round(summary["rows_rejected"] / max(summary["rows_read"], 1), 6)
    write_text(f"{out}/dq/batch_id={batch_id}/dq_summary.json", json.dumps(summary, indent=2))
    return summary


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch_id", required=True)
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    args, _ = ap.parse_known_args()  # Glue adds its own arguments
    os.environ.setdefault("PYSPARK_PYTHON", sys.executable)  # workers use the same Python as the driver
    spark = (SparkSession.builder.appName("raw_to_curated")
             .config("spark.sql.session.timeZone", "UTC").getOrCreate())
    run(spark, args.batch_id, args.input.rstrip("/"), args.output.rstrip("/"))


if __name__ == "__main__":
    main()
