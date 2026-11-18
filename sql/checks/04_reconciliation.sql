-- Latest reconciliation per batch with a non-zero difference between staging and warehouse. Expected: no rows.
SELECT batch_id, check_name, staging_value, warehouse_value, difference
FROM (SELECT *, rank() OVER (PARTITION BY batch_id ORDER BY checked_at DESC) AS rnk FROM audit.reconciliation) r
WHERE rnk = 1 AND difference <> 0
