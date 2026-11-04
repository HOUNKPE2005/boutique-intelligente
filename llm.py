"""Appel au LLM (API compatible OpenAI) + compteurs d'appels et de tokens."""
import os, sys
from dotenv import load_dotenv
from openai import OpenAI

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()
MODEL = os.getenv("RODIUM_MODEL")
STATS = {"appels": 0, "tokens": 0}
_client = None

def _get_client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.getenv("RODIUM_API_KEY"),
                         base_url=os.getenv("RODIUM_BASE_URL") or None)
    return _client

def chat(messages, tools=None):
    kw = {"model": MODEL, "messages": messages}
    if tools:
        kw["tools"] = tools
    r = _get_client().chat.completions.create(**kw)
    STATS["appels"] += 1
    if getattr(r, "usage", None):
        STATS["tokens"] += r.usage.total_tokens or 0
    return r.choices[0].message
