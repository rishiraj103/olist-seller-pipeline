# Design decisions

**PostgreSQL for the warehouse, Athena for the lake.** The warehouse needs things Athena does not do well:
row-level upserts for SCD1, closing and opening versions for SCD2, primary/foreign keys and CHECK constraints,
and a stored procedure that loads a batch in one controlled run with its own error log. Athena stays useful for
ad-hoc questions on the curated Parquet (a per-batch count scans ~50 KB), so both exist: the lake is the source of
truth for cleaned files, PostgreSQL is the modelled, constrained copy the app reads.

**SCD Type 2 only on sellers.** The business question is about sellers ("revenue by the seller's city at the time of
the order"), and a seller's location affects delivery times, so its history must be kept. Customer and product
attributes are overwritten (Type 1): nobody asks for a customer's previous address, and keeping it would only grow the
table. Facts store the seller version valid on the purchase date, so history queries are a plain join.

**Customers keyed on `customer_unique_id`.** Olist creates a new `customer_id` for every order; the real person is
`customer_unique_id` (96,096 people for 99,441 orders). Keying on it makes repeat-customer analysis (Q5) possible.

**Reject, don't repair.** Rows that break a rule go to `rejected/` with a reason and are counted in
`dq_summary.json`; nothing is silently fixed. Items and reviews of a rejected order are rejected too
(`unknown_order`), so the warehouse never has items without an order. A CSV whose header does not match the schema
fails the whole job, because a renamed column would otherwise be read by position into the wrong field.

**Fixed SQL for GenAI.** The model never writes SQL. Two parameterised queries produce the only data it sees, no
customer identifiers are sent, and every number in its answer must be found in that data or the answer is replaced
by the metrics. This makes the feature safe and checkable at the cost of flexibility (no free-form questions).

**Local Ollama instead of Bedrock.** The AWS Free plan sets Bedrock quotas to 0 and they cannot be raised, and the
project has a $0 budget. `genai/llm_client.py` keeps the Bedrock Converse call behind the same interface
(`LLM_PROVIDER=bedrock`), so moving to a hosted model is a configuration change. `qwen2.5:7b` was chosen over
`qwen2.5:3b` after the 5-seller check: the 3B model invented numbers and misread percentages (`genai_eval.md`).

**Warehouse load from the laptop.** Loading RDS from inside AWS needs Glue or Lambda inside the VPC with a JDBC
connection, VPC endpoints for S3 and security-group rules (and a NAT gateway or endpoints cost money). The pipeline
therefore automates everything up to "batch ready to load" and emails; one command loads it. Future work: a Glue
Python shell job in the VPC started by Step Functions after the DQ gate.

**Retries only for transient errors.** The Step Functions retries cover throttling and service errors. A job that
fails because of the data (wrong header) is not retried: it would fail the same way, cost another Glue run and
delay the failure email.

**Local-first development.** Every component runs locally first (PySpark, PostgreSQL in Docker, the same loader
and SQL), and the identical code then runs on AWS: the Glue job is the local script, RDS gets the same DDL. Glue runs
only code that already works, which keeps the AWS bill to cents, and results can be compared one-to-one
(the 2018-01 DQ summary from Glue is identical to the local one).

**Region `ap-southeast-2`, WSL for development.** The Free plan locks the account to one region. Windows Smart App
Control blocks pandas' native libraries, so development runs in WSL Ubuntu 24.04.

**One composite index for seller lookups.** `(seller_key, purchase_date_key)` makes the per-seller query 7× faster
than a scan and, because its leading column is `seller_key`, replaces the single-column seller index
(`docs/analytics.md`).
