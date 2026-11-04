# Changelog

## v0.2-profiling — 2026-11-04
- `tools/profile_data.py` profiles all 9 source files and checks each known data problem.
- `docs/data_profile.md`: row counts, nulls, duplicates and a pipeline rule for every confirmed problem.
- `docs/source_er.md`: source ER diagram.
- Finding: repeated `review_id`s are one review shared by several orders, not duplicate rows; rule is the latest review per order.
- Development moved to WSL (Ubuntu 24.04): Windows Smart App Control blocks pandas native libraries.

## v0.1-setup — 2026-11-02
- Repo structure, `.gitignore`, `.env.example`, requirements (PySpark 3.5 to match Glue 5.0).
- GitHub Actions runs `unittest` on every push.
- Local PostgreSQL 16 in Docker; AWS CLI configured.
- AWS region is `ap-southeast-2`: the AWS Free plan locks the account to one region.
- GenAI will use a local Ollama model instead of Bedrock: Bedrock quotas are 0 and not adjustable on the Free plan.
