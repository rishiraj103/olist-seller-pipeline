# Olist Seller Performance Pipeline

A small, end-to-end data pipeline on AWS that turns Olist's raw marketplace order files into a data lake, a PostgreSQL star-schema warehouse, a dashboard, and a grounded AI explanation of why sellers' ratings change.

## Problem

Olist is a Brazilian marketplace where many small sellers sell products. Late deliveries cause bad reviews, but managers cannot easily see which sellers and states cause delays, and nobody reads the thousands of written complaints. The data sits in 9 separate CSV files designed for running the shop, not for analysis.

**Users**
- Operations manager: on-time delivery by state and month.
- Seller-success team: seller scorecards and the reasons behind bad ratings.

**Data:** [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) (~100k anonymised orders, 2016–2018). The CSVs are not included in this repo; download them into `data/source/`.

## Results so far

| What | Measured |
| --- | --- |
| Seller scorecard query with composite index `(seller_key, purchase_date_key)` | 11.3 ms → 1.6 ms (vs. a full scan) |
| Athena: items and revenue per batch on the curated lake | 51 KB scanned |
| Repeat customers (Q5) | 3.12% ordered more than once |
| Late orders with a 1–2 star review (Q4, top category) | 62.7% (bed_bath_table) |

Details: [docs/analytics.md](docs/analytics.md).
