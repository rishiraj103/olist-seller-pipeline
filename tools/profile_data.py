"""Profile the Olist source CSVs and check known data problems.

Usage: python -m tools.profile_data [--source data/source]
"""
import argparse
from pathlib import Path

import pandas as pd

# name: (file, key columns, date columns, code columns)
TABLES = {
    "orders": ("olist_orders_dataset.csv", ["order_id"],
               ["order_purchase_timestamp", "order_approved_at", "order_delivered_carrier_date",
                "order_delivered_customer_date", "order_estimated_delivery_date"], ["order_status"]),
    "order_items": ("olist_order_items_dataset.csv", ["order_id", "order_item_id"], ["shipping_limit_date"], []),
    "order_payments": ("olist_order_payments_dataset.csv", ["order_id", "payment_sequential"], [], ["payment_type"]),
    "order_reviews": ("olist_order_reviews_dataset.csv", ["review_id"],
                      ["review_creation_date", "review_answer_timestamp"], ["review_score"]),
    "customers": ("olist_customers_dataset.csv", ["customer_id"], [], ["customer_state"]),
    "sellers": ("olist_sellers_dataset.csv", ["seller_id"], [], ["seller_state"]),
    "products": ("olist_products_dataset.csv", ["product_id"], [], []),
    "category_translation": ("product_category_name_translation.csv", ["product_category_name"], [], []),
    "geolocation": ("olist_geolocation_dataset.csv", [], [], []),
}


def load(source: Path) -> dict:
    return {name: pd.read_csv(source / spec[0], dtype=str, encoding="utf-8-sig") for name, spec in TABLES.items()}


def profile_table(name: str, df: pd.DataFrame) -> None:
    _, keys, dates, codes = TABLES[name]
    print(f"\n## {name}\nrows: {len(df):,}")
    if keys:
        print(f"duplicate keys {keys}: {df.duplicated(keys).sum():,}")
    nulls = (df.isna().mean() * 100).round(2)
    print("null % per column:", {c: v for c, v in nulls.items() if v > 0} or "none")
    for c in dates:
        d = pd.to_datetime(df[c])
        print(f"{c}: {d.min()} .. {d.max()}")
    for c in codes:
        print(f"{c} values:", df[c].value_counts(dropna=False).to_dict())


def check_problems(t: dict) -> None:
    o, c, p, tr, r, pay = (t[k] for k in
                           ["orders", "customers", "products", "category_translation", "order_reviews", "order_payments"])
    print("\n## Known problems")
    print(f"customer_id distinct: {c.customer_id.nunique():,} | customer_unique_id distinct: "
          f"{c.customer_unique_id.nunique():,}")
    print("misspelled product columns:", [col for col in p.columns if "lenght" in col])
    print(f"products with no category: {p.product_category_name.isna().sum():,}")
    missing = sorted(set(p.product_category_name.dropna()) - set(tr.product_category_name))
    print(f"categories missing translation: {missing}")

    ts = {col: pd.to_datetime(o[col]) for col in TABLES["orders"][2]}
    not_delivered = o.order_status != "delivered"
    print(f"non-delivered orders with null delivery date: "
          f"{ts['order_delivered_customer_date'][not_delivered].isna().sum():,} of {not_delivered.sum():,}")
    print(f"delivered orders with null delivery date: "
          f"{ts['order_delivered_customer_date'][~not_delivered].isna().sum():,}")
    print(f"approved < purchased: {(ts['order_approved_at'] < ts['order_purchase_timestamp']).sum():,}")
    print(f"carrier < purchased: {(ts['order_delivered_carrier_date'] < ts['order_purchase_timestamp']).sum():,}")
    print(f"delivered < carrier: {(ts['order_delivered_customer_date'] < ts['order_delivered_carrier_date']).sum():,}")

    print(f"duplicate review_id rows: {r.review_id.duplicated().sum():,} | "
          f"duplicate (review_id, order_id): {r.duplicated(['review_id', 'order_id']).sum():,} | "
          f"orders with >1 review: {r.order_id.duplicated().sum():,}")
    print(f"empty review message: {r.review_comment_message.isna().mean():.1%} | "
          f"empty title: {r.review_comment_title.isna().mean():.1%}")
    print(f"payment_type not_defined rows: {(pay.payment_type == 'not_defined').sum():,}")

    items, s = t["order_items"], t["sellers"]
    price, freight = items.price.astype(float), items.freight_value.astype(float)
    print(f"price <= 0: {(price <= 0).sum():,} | freight < 0: {(freight < 0).sum():,} | "
          f"freight = 0: {(freight == 0).sum():,} | price range: {price.min()} .. {price.max()}")
    print(f"shipping_limit_date after 2018: {(pd.to_datetime(items.shipping_limit_date).dt.year > 2018).sum():,}")
    for name, col in [("customers", c.customer_zip_code_prefix), ("sellers", s.seller_zip_code_prefix)]:
        bad_zip = (~col.str.fullmatch(r"\d{5}")).sum()
        print(f"{name} zip prefix not 5 digits: {bad_zip:,}")
    print(f"items with unknown order_id: {(~items.order_id.isin(o.order_id)).sum():,} | "
          f"unknown seller_id: {(~items.seller_id.isin(s.seller_id)).sum():,} | "
          f"unknown product_id: {(~items.product_id.isin(p.product_id)).sum():,}")
    print(f"orders without items: {(~o.order_id.isin(items.order_id)).sum():,} | "
          f"orders without review: {(~o.order_id.isin(r.order_id)).sum():,}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="data/source", type=Path)
    tables = load(ap.parse_args().source)
    for name, df in tables.items():
        profile_table(name, df)
    check_problems(tables)


if __name__ == "__main__":
    main()
