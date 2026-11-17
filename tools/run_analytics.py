"""Run the six analytics queries (results -> docs/results/*.csv) and the validation checks (must return no rows).

Usage: python -m tools.run_analytics [--target local|rds]
"""
import argparse
import csv
import time
from pathlib import Path

from dotenv import load_dotenv

from loader.curated_to_warehouse import connect


def run(cur, path: Path):
    start = time.perf_counter()
    cur.execute(path.read_text())
    rows = cur.fetchall()
    return [c.name for c in cur.description], rows, (time.perf_counter() - start) * 1000


def main() -> None:
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", choices=["local", "rds"], default="local")
    args = ap.parse_args()
    out = Path("docs/results")
    out.mkdir(parents=True, exist_ok=True)

    conn = connect(args.target)
    failed = 0
    try:
        with conn.cursor() as cur:
            for path in sorted(Path("sql/analytics").glob("q*.sql")):
                cols, rows, ms = run(cur, path)
                with open(out / f"{path.stem}.csv", "w", newline="") as f:
                    csv.writer(f).writerows([cols, *rows])
                print(f"{path.stem}: {len(rows)} rows, {ms:.0f} ms")
            for path in sorted(Path("sql/checks").glob("*.sql")):
                cols, rows, _ = run(cur, path)
                failed += bool(rows)
                print(f"check {path.stem}: {'OK' if not rows else f'{len(rows)} PROBLEM ROWS {rows[:3]}'}")
    finally:
        conn.close()
    if failed:
        raise SystemExit(f"{failed} check(s) failed")


if __name__ == "__main__":
    main()
