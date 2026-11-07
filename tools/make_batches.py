"""Split the Olist source CSVs into monthly batches that behave like live data.

Batches: 2017-12 (everything up to end of 2017), 2018-01 .. 2018-08 (2018-08 also takes Sep/Oct 2018).
Batch 2018-03 moves ~10 sellers to a new city/state (kept in later batches); batch 2018-02 gets injected bad items.

Usage: python -m tools.make_batches [--source data/source] [--out data/batches]
"""
import argparse
import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

log = logging.getLogger("make_batches")

SOURCE_FILES = {
    "orders": "olist_orders_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "order_reviews": "olist_order_reviews_dataset.csv",
    "customers": "olist_customers_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "products": "olist_products_dataset.csv",
    "category_translation": "product_category_name_translation.csv",
}
INITIAL, LAST = "2017-12", "2018-08"
CHANGE_BATCH, BAD_ROWS_BATCH, N_MOVES, SEED = "2018-03", "2018-02", 10, 42


def batch_of(purchase_ts: pd.Series) -> pd.Series:
    month = pd.to_datetime(purchase_ts).dt.strftime("%Y-%m")
    return month.where(month > INITIAL, INITIAL).where(month < LAST, LAST)


def period(batch_id: str) -> tuple[str, str]:
    start = pd.Timestamp("2016-01-01") if batch_id == INITIAL else pd.Timestamp(f"{batch_id}-01")
    end = pd.Timestamp("2018-12-31") if batch_id == LAST else pd.Timestamp(f"{batch_id}-01") + pd.offsets.MonthEnd(0)
    return start.date().isoformat(), end.date().isoformat()


def simulate_moves(sellers: pd.DataFrame, items_by_batch: dict) -> pd.DataFrame:
    """Pick sellers active before and in CHANGE_BATCH; give each a city/state from another state."""
    before = set().union(*(items_by_batch[b].seller_id for b in items_by_batch if b < CHANGE_BATCH))
    active = sorted(before & set(items_by_batch[CHANGE_BATCH].seller_id))
    chosen = sellers[sellers.seller_id.isin(active)].sample(N_MOVES, random_state=SEED)
    targets = sellers.drop_duplicates(["seller_city", "seller_state"])
    moves = []
    for i, row in enumerate(chosen.itertuples()):
        new = targets[targets.seller_state != row.seller_state].sample(1, random_state=SEED + i).iloc[0]
        moves.append({"seller_id": row.seller_id, "old_city": row.seller_city, "old_state": row.seller_state,
                      "new_zip": new.seller_zip_code_prefix, "new_city": new.seller_city,
                      "new_state": new.seller_state, "effective_batch": CHANGE_BATCH})
    return pd.DataFrame(moves)


def apply_moves(sellers: pd.DataFrame, moves: pd.DataFrame) -> pd.DataFrame:
    s = sellers.set_index("seller_id")
    m = moves.set_index("seller_id").reindex(s.index).dropna()
    s.loc[m.index, ["seller_zip_code_prefix", "seller_city", "seller_state"]] = \
        m[["new_zip", "new_city", "new_state"]].to_numpy()
    return s.reset_index()


def inject_bad_items(items: pd.DataFrame) -> pd.DataFrame:
    """3 exact duplicates, 2 null order_id, 2 negative prices (on new item numbers)."""
    sample = items.sample(7, random_state=SEED).reset_index(drop=True)
    dup = sample.iloc[0:3].assign(injected_reason="duplicate_key")
    null_key = sample.iloc[3:5].assign(order_id=None, injected_reason="null_key")
    neg = sample.iloc[5:7].assign(order_item_id="99", price=lambda d: "-" + d.price,
                                  injected_reason="non_positive_price")
    return pd.concat([dup, null_key, neg], ignore_index=True)


def write_batch(out: Path, batch_id: str, tables: dict) -> int:
    folder = out / f"batch_id={batch_id}"
    folder.mkdir(parents=True, exist_ok=True)
    files = []
    for name, df in tables.items():
        path = folder / f"{name}.csv"
        df.to_csv(path, index=False)
        files.append({"name": path.name, "rows": len(df), "md5": hashlib.md5(path.read_bytes()).hexdigest()})
    start, end = period(batch_id)
    manifest = {"batch_id": batch_id, "period_start": start, "period_end": end,
                "created_at": datetime.now().isoformat(timespec="seconds"), "files": files}
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2))
    log.info("batch %s: %s", batch_id, {f["name"]: f["rows"] for f in files})
    return tables["orders"].order_id.nunique()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="data/source", type=Path)
    ap.add_argument("--out", default="data/batches", type=Path)
    ap.add_argument("--docs", default="docs", type=Path)
    args = ap.parse_args()

    src = {k: pd.read_csv(args.source / f, dtype=str, encoding="utf-8-sig") for k, f in SOURCE_FILES.items()}
    orders = src["orders"].assign(_batch=lambda d: batch_of(d.order_purchase_timestamp))
    batches = sorted(orders._batch.unique())
    order_ids = {b: orders.loc[orders._batch == b, "order_id"] for b in batches}
    items_by_batch = {b: src["order_items"][src["order_items"].order_id.isin(order_ids[b])] for b in batches}

    moves = simulate_moves(src["sellers"], items_by_batch)
    moved_sellers = apply_moves(src["sellers"], moves)
    bad = inject_bad_items(items_by_batch[BAD_ROWS_BATCH])
    moves.to_csv(args.docs / "simulated_changes.csv", index=False)
    bad.to_csv(args.docs / "injected_rows.csv", index=False)

    total = 0
    for b in batches:
        o = orders[orders._batch == b].drop(columns="_batch")
        items = items_by_batch[b]
        if b == BAD_ROWS_BATCH:
            items = pd.concat([items, bad.drop(columns="injected_reason")], ignore_index=True)
        sellers = moved_sellers if b >= CHANGE_BATCH else src["sellers"]
        total += write_batch(args.out, b, {
            "orders": o,
            "order_items": items,
            "order_reviews": src["order_reviews"][src["order_reviews"].order_id.isin(o.order_id)],
            "customers": src["customers"][src["customers"].customer_id.isin(o.customer_id)],
            "sellers": sellers[sellers.seller_id.isin(items.seller_id)],
            "products": src["products"][src["products"].product_id.isin(items.product_id)],
            "category_translation": src["category_translation"],
        })

    source_total = src["orders"].order_id.nunique()
    log.info("unique orders in batches: %s | source: %s | match: %s", total, source_total, total == source_total)
    if total != source_total:
        raise SystemExit("order totals do not match the source")


if __name__ == "__main__":
    main()
