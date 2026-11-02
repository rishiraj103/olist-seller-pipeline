# Changelog

## v0.1-setup — 2026-11-02
- Repo structure, `.gitignore`, `.env.example`, requirements (PySpark 3.5 to match Glue 5.0).
- GitHub Actions runs `unittest` on every push.
- Local PostgreSQL 16 in Docker; AWS CLI configured.
- AWS region is `ap-southeast-2`: the AWS Free plan locks the account to one region.
- GenAI will use a local Ollama model instead of Bedrock: Bedrock quotas are 0 and not adjustable on the Free plan.
