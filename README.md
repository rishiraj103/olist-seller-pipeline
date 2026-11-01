# Olist Seller Performance Pipeline

A small, end-to-end data pipeline on AWS that turns Olist's raw marketplace order files into a data lake, a PostgreSQL star-schema warehouse, a dashboard, and a grounded AI explanation of why sellers' ratings change.

## Problem

Olist is a Brazilian marketplace where many small sellers sell products. Late deliveries cause bad reviews, but managers cannot easily see which sellers and states cause delays, and nobody reads the thousands of written complaints. The data sits in 9 separate CSV files designed for running the shop, not for analysis.

**Users**
- Operations manager: on-time delivery by state and month.
- Seller-success team: seller scorecards and the reasons behind bad ratings.

**Data:** [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) (~100k anonymised orders, 2016–2018). The CSVs are not included in this repo; download them into `data/source/`.
