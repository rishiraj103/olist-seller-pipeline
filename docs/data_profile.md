# Data Profile — Olist source files

Produced by `python -m tools.profile_data` on the 9 Kaggle CSVs. Orders span 2016-09-04 to 2018-10-17.

## Files

| File | Rows | Key | Duplicate keys | Worst null column |
| --- | --- | --- | --- | --- |
| orders | 99,441 | order_id | 0 | order_delivered_customer_date 2.98% |
| order_items | 112,650 | (order_id, order_item_id) | 0 | none |
| order_reviews | 99,224 | review_id | 814 (see below) | review_comment_title 88.34% |
| customers | 99,441 | customer_id | 0 | none |
| sellers | 3,095 | seller_id | 0 | none |
| products | 32,951 | product_id | 0 | product_category_name 1.85% |
| category_translation | 71 | product_category_name | 0 | none |
| order_payments | 103,886 | (order_id, payment_sequential) | 0 | none — not used in core version |
| geolocation | 1,000,163 | none | — | none — not used in core version |

Code columns:
- `order_status`: delivered 96,478 · shipped 1,107 · canceled 625 · unavailable 609 · invoiced 314 · processing 301 · created 5 · approved 2
- `review_score`: 5 = 57,328 · 4 = 19,142 · 3 = 8,179 · 2 = 3,151 · 1 = 11,424
- `payment_type`: credit_card 76,795 · boleto 19,784 · voucher 5,775 · debit_card 1,529 · not_defined 3
- States: 27 distinct customer states, 23 distinct seller states, all valid two-letter codes.

## Problems and rules

| Problem | Evidence | Rule in the pipeline |
| --- | --- | --- |
| `customer_id` is per order | 99,441 customer_ids but 96,096 `customer_unique_id`s | `dim_customer` keyed on `customer_unique_id`; facts look up through `customer_id → customer_unique_id` |
| Misspelled product columns | `product_name_lenght`, `product_description_lenght` | rename to `product_name_length`, `product_description_length` |
| Products with no category | 610 products | category = `unknown` |
| Categories missing a translation | `pc_gamer`, `portateis_cozinha_e_preparadores_de_alimentos` | map in `transform/category_fixes.csv`, else `unknown` |
| Non-delivered orders have empty delivery dates | 2,957 of 2,963 non-delivered orders | allowed: delivery date stays null, `delay_days` and `is_late` null |
| Delivered orders with no delivery date | 8 orders | keep; `delay_days` and `is_late` null |
| Delivered before handed to carrier | 23 orders | reject, reason `delivered_before_shipped` |
| Handed to carrier before purchase | 166 orders | keep (likely clock or entry error); documented limitation |
| Approved before purchase | 0 orders | rule kept as a guard: reject, reason `approved_before_purchase` |
| Same `review_id` on several orders | 814 repeated `review_id`s, 0 repeated `(review_id, order_id)` | `review_text` key is `(review_id, order_id)` |
| Several reviews for one order | 551 orders | keep the latest review per `order_id` (by `review_answer_timestamp`) |
| Empty review comments | message empty 58.7%, title empty 88.3% | keep the score; GenAI uses only non-empty messages |
| Free shipping | 383 items with freight = 0 | valid: rule is freight ≥ 0 |
| `not_defined` payment type | 3 rows | out of scope (payments not loaded) |
| Shipping limit far in the future | 4 items after 2018 (max 2020-04-09) | keep; column not used in measures |
| Orders with no items | 775 orders | kept in `fact_order_fulfilment`, no item rows |
| Orders with no review | 768 orders | `review_score` null |

Checked and clean: no null or orphan keys in `order_items`, no price ≤ 0 (min 0.85, max 6,735), all zip prefixes are 5 digits. The negative-price, null-key and duplicate-item rules are still built and are tested with the bad rows injected in batch 2018-02.
