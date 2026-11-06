-- Calendar 2016-01-01 .. 2020-12-31 covers every source date (max shipping limit is 2020-04-09).
INSERT INTO dw.dim_date (date_key, full_date, year, quarter, month, month_name, day, day_of_week, is_weekend)
SELECT to_char(d, 'YYYYMMDD')::int, d, extract(year FROM d), extract(quarter FROM d), extract(month FROM d),
       to_char(d, 'FMMonth'), extract(day FROM d), extract(isodow FROM d), extract(isodow FROM d) IN (6, 7)
FROM generate_series(DATE '2016-01-01', DATE '2020-12-31', INTERVAL '1 day') AS g(d)
ON CONFLICT DO NOTHING;

INSERT INTO dw.dim_date VALUES (-1, DATE '1900-01-01', 1900, 1, 1, 'Unknown', 1, 1, false)
ON CONFLICT DO NOTHING;
