"""Grounded seller insight: "Why did seller X's rating change in this period?"

Fixed, parameterised SQL only (the LLM never writes SQL); no customer identifiers are sent to the model;
every number in the answer must be traceable to the metrics, otherwise the metrics are returned with a warning.

Usage: python -m genai.insights <seller_id> 2018-01-01 2018-08-31
"""
import json
import logging
import os
import re
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from genai import llm_client
from loader.curated_to_warehouse import connect

MIN_REVIEWS = 10
MAX_REVIEWS = 30
PROMPT = Path(__file__).parent / "prompts" / "seller_insight.txt"

# Seller per purchase month vs. its main category (by revenue) over the whole period:
# orders, late %, delay vs. estimate, rating.
METRICS_SQL = """
WITH seller_items AS (
    SELECT i.order_id, i.price, p.category_name_english AS category
    FROM dw.fact_order_item i
    JOIN dw.dim_seller s  ON s.seller_key = i.seller_key
    JOIN dw.dim_product p ON p.product_key = i.product_key
    WHERE s.seller_id = %(seller_id)s
), main_category AS (
    SELECT category FROM seller_items GROUP BY category ORDER BY sum(price) DESC LIMIT 1
), scoped AS (
    SELECT DISTINCT 'seller' AS scope, order_id FROM seller_items
    UNION ALL
    SELECT DISTINCT 'category', i.order_id
    FROM dw.fact_order_item i JOIN dw.dim_product p ON p.product_key = i.product_key
    WHERE p.category_name_english = (SELECT category FROM main_category)
)
SELECT o.scope, (SELECT category FROM main_category) AS category,
       CASE WHEN o.scope = 'seller' THEN to_char(d.full_date, 'YYYY-MM') ELSE 'whole period' END AS month,
       count(*)                                AS orders,
       round(100.0 * avg(f.is_late::int), 1)   AS late_pct,
       round(avg(f.delay_days), 1)             AS avg_delay_vs_estimate_days,
       round(avg(f.review_score), 2)           AS avg_rating
FROM scoped o
JOIN dw.fact_order_fulfilment f ON f.order_id = o.order_id
JOIN dw.dim_date d              ON d.date_key = f.purchase_date_key
WHERE d.full_date BETWEEN %(start)s AND %(end)s
GROUP BY 1, 3
ORDER BY o.scope DESC, month
"""

# Up to 30 most recent 1-2 star review texts for the seller's orders in the period (text only, no identifiers).
REVIEWS_SQL = """
SELECT DISTINCT ON (r.review_id) r.review_id, r.review_creation_date, r.review_score,
       concat_ws(' - ', r.review_comment_title, r.review_comment_message) AS text
FROM dw.review_text r
JOIN dw.fact_order_item i ON i.order_id = r.order_id
JOIN dw.dim_seller s      ON s.seller_key = i.seller_key
WHERE s.seller_id = %(seller_id)s AND r.review_score <= 2 AND r.review_comment_message IS NOT NULL
  AND r.review_creation_date BETWEEN %(start)s AND %(end)s
ORDER BY r.review_id
"""

NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
PLACEHOLDER = re.compile(r"^\s*(Answer:\s*)?<[^>]*>\s*$")
# Small whole numbers are allowed only in these positions, never on their own:
REVIEW_COUNT = re.compile(r"\b(\d+)(?=\s+(?:low-star\s+)?reviews?\b)", re.IGNORECASE)  # "7 reviews"
STARS = re.compile(r"\b([1-5])(?:\s*-\s*([1-5]))?(?=[\s-]*stars?\b)", re.IGNORECASE)    # "1-2 star", "5 stars"
LIST_MARK = re.compile(r"(?m)^\s*\d+[.)](?=\s)|(?<![\d.])\d\)")                            # "1." / "2)"


def numbers_in(text: str) -> set[float]:
    return {float(n.replace(",", ".")) for n in NUMBER.findall(text)}


def check_numbers(answer: str, metrics: list[dict], review_count: int) -> list[float]:
    """Return numbers in the answer that cannot be traced to the metrics (empty = OK).

    Allowed: any metric value or its rounding to 1/0 decimals (sign ignored: "-3.5" may be written "3.5 days early"),
    parts of the months ("2018-03" -> 2018, 3), and three positional exceptions: a count directly before "review(s)"
    that is at most review_count, star ratings 1-5 before "star(s)", and list markers. Any other number, e.g. an
    invented "25%", must match the metrics.
    """
    allowed = set()
    for value in numbers_in(json.dumps(metrics)):
        allowed |= {value, round(value, 1), float(round(value))}
    text = REVIEW_COUNT.sub(lambda m: "" if int(m.group(1)) <= review_count else m.group(0), answer)
    text = LIST_MARK.sub("", STARS.sub("", text))
    return sorted(n for n in numbers_in(text) if n not in allowed)


def explain_seller(seller_id: str, start: date, end: date, conn=None) -> dict:
    params = {"seller_id": seller_id, "start": start, "end": end}
    own = conn is None
    conn = conn or connect(os.getenv("WAREHOUSE", "local"))
    try:
        with conn.cursor() as cur:
            cur.execute(METRICS_SQL, params)
            cols = [c.name for c in cur.description]
            metrics = [{k: (float(v) if hasattr(v, "is_finite") else v) for k, v in zip(cols, row)}
                       for row in cur.fetchall()]
            cur.execute(REVIEWS_SQL, params)
            reviews = sorted(cur.fetchall(), key=lambda r: r[1], reverse=True)[:MAX_REVIEWS]
    finally:
        if own:
            conn.close()

    result = {"seller_id": seller_id, "start": str(start), "end": str(end), "metrics": metrics,
              "review_count": len(reviews), "answer": None, "warning": None}
    if len(reviews) < MIN_REVIEWS or not any(m["scope"] == "seller" for m in metrics):
        result["warning"] = f"Not enough data: {len(reviews)} low-star reviews in the period (need {MIN_REVIEWS})."
        return result

    review_texts = "\n".join(f"- [{score} stars, {created:%Y-%m}] {text}" for _, created, score, text in reviews)
    fields = ("month", "orders", "late_pct", "avg_delay_vs_estimate_days", "avg_rating")
    seller = [{k: m[k] for k in fields} for m in metrics if m["scope"] == "seller"]
    category = [{k: m[k] for k in fields[1:]} for m in metrics if m["scope"] == "category"]
    grouped = {"seller_first_month": seller[0], "seller_last_month": seller[-1], "seller_monthly": seller,
               "category": metrics[0]["category"], "category_average_whole_period": category[0] if category else None}
    prompt = PROMPT.read_text().format(start=start, end=end, metrics_json=json.dumps(grouped),
                                       review_texts=review_texts)
    answer, result["llm"] = llm_client.generate(prompt)
    answer = "\n".join(line for line in answer.splitlines() if not PLACEHOLDER.match(line)).strip()  # echoed template

    unverified = check_numbers(answer, metrics + [{"start": str(start), "end": str(end)}], len(reviews))
    if unverified:
        result["warning"] = f"The AI answer contained numbers not found in the data {unverified}; showing metrics only."
        result["rejected_answer"] = answer
    else:
        result["answer"] = answer
    return result


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    load_dotenv()
    seller_id, start, end = sys.argv[1], date.fromisoformat(sys.argv[2]), date.fromisoformat(sys.argv[3])
    print(json.dumps(explain_seller(seller_id, start, end), indent=2, default=str))


if __name__ == "__main__":
    main()
