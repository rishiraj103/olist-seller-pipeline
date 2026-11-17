-- Items and revenue per batch straight from the curated lake (partition column batch_id).
SELECT batch_id, count(*) AS items, sum(price) AS revenue
FROM olist_lake.order_items
GROUP BY batch_id
ORDER BY batch_id
