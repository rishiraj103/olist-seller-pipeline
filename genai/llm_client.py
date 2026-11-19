"""LLM client: local Ollama by default; Bedrock (Converse API) is a drop-in swap with LLM_PROVIDER=bedrock.

Both return (text, meta) with token counts and response time, so callers never depend on the provider.
Ollama is the default because Bedrock quotas are 0 on the AWS Free plan (see docs/decisions.md).
"""
import json
import logging
import os
import time
import urllib.request

log = logging.getLogger("llm")
MAX_TOKENS = 400
TEMPERATURE = 0.1


def _ollama(prompt: str) -> tuple[str, dict]:
    body = {"model": os.getenv("OLLAMA_MODEL", "qwen2.5:7b"), "stream": False,
            "messages": [{"role": "user", "content": prompt}],
            "options": {"temperature": TEMPERATURE, "num_predict": MAX_TOKENS}}
    req = urllib.request.Request(f"{os.getenv('OLLAMA_HOST', 'http://localhost:11434')}/api/chat",
                                 data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        out = json.load(resp)
    return out["message"]["content"], {"model": body["model"], "input_tokens": out.get("prompt_eval_count"),
                                       "output_tokens": out.get("eval_count")}


def _bedrock(prompt: str) -> tuple[str, dict]:
    import boto3
    model = os.environ["BEDROCK_MODEL_ID"]
    out = boto3.client("bedrock-runtime").converse(
        modelId=model, messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": MAX_TOKENS, "temperature": TEMPERATURE})
    return out["output"]["message"]["content"][0]["text"], {"model": model, "input_tokens": out["usage"]["inputTokens"],
                                                            "output_tokens": out["usage"]["outputTokens"]}


def generate(prompt: str) -> tuple[str, dict]:
    start = time.perf_counter()
    text, meta = (_bedrock if os.getenv("LLM_PROVIDER", "ollama") == "bedrock" else _ollama)(prompt)
    meta["seconds"] = round(time.perf_counter() - start, 1)
    log.info("llm %s", meta)
    return text, meta
