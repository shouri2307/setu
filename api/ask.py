"""
api/ask.py — Vercel serverless function: proxies AI questions to Groq.

Same logic as serve.py's ask_groq (used for local dev). On Vercel, this file is
auto-exposed at POST /api/ask. The Groq key is read from the GROQ_API_KEY
environment variable set in the Vercel project's dashboard — never sent to the
browser. If it's missing or Groq is unreachable, the app still works fully;
only the live "Ask AI" box is disabled, since every ward's ranking and
plain-language explanation is precomputed and offline.
"""

import os
import json
from http.server import BaseHTTPRequestHandler
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

GROQ_KEY = os.environ.get("GROQ_API_KEY", "").strip()
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# Primary model, then fallbacks tried in order if one fails (404 / model
# decommissioned / rate-limited / temporary outage). Keeps the demo alive
# even if Groq deprecates or throttles one model mid-demo.
GROQ_MODELS = [
    "openai/gpt-oss-120b",
    "qwen/qwen3.6-27b",
    "openai/gpt-oss-20b",
]

SYSTEM = (
    "You are SETHU's flood-planning advisor, explaining to a judge or a city "
    "official with no engineering background. Answer ONLY from the ward data "
    "provided in the user's message — do not invent numbers. Be concrete and "
    "brief (3-5 sentences). Explain flood-control ideas in plain language. If "
    "asked why an intervention was chosen or rejected, use the 'why' and "
    "'excluded' reasons in the data. Never claim precision the data doesn't have."
)

BASE_RULES = (
    "Answer ONLY from the REPORT DATA in the user's message. Never invent numbers, prices, "
    "legal status or facts that are not in the data; if something is not in the data, say so. "
    "Name the factors you rely on. Point-level indicators (lake distance, terrain pocket, facilities) "
    "are indicative, not validated; the ward flood ranking is validated (held-out floods). A lake distance "
    "from open maps is NOT the legal lake boundary (FTL/buffer) - say it must be verified with the "
    "authorities. This is not legal, valuation or insurance advice. Be concrete, 4-6 short sentences, "
    "plain language, no markdown tables."
)
LENS_SYSTEM = {
    "buyer": "You are SETHU, explaining a property location report to a family thinking of buying here. " + BASE_RULES,
    "agent": "You are SETHU, helping a real-estate professional. Give evidence they can cite when pricing or negotiating (facts from the report), and honest selling points. Do not invent a discount or a price. " + BASE_RULES,
    "insurer": "You are SETHU, assisting an insurance underwriter or claims analyst. Explain tiers using the factor weights, treat loadings as illustrative, and for claims describe what evidence supports or does not support the claim - triage, never an accusation. " + BASE_RULES,
}


def call_groq_model(model, question, context, system=None, label="WARD DATA"):
    """Try a single model. Returns (answer_text, None) on success,
    or (None, (kind, detail)) on failure so the caller can decide whether
    to retry the next model or give up."""
    body = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system or SYSTEM},
            {"role": "user", "content": f"WARD DATA:\n{context}\n\nQUESTION: {question}"},
        ],
        "temperature": 0.3, "max_tokens": 700,
    }).encode()

    req = Request(GROQ_URL, data=body, headers={
        "Authorization": f"Bearer {GROQ_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SETU-Server/1.0",
        "Accept": "application/json",
    })

    try:
        with urlopen(req, timeout=25) as r:
            data = json.loads(r.read())
        return data["choices"][0]["message"]["content"].strip(), None

    except HTTPError as e:
        try:
            detail = e.read().decode()
        except Exception:
            detail = "(no body)"
        print(f"[groq] model={model} HTTP {e.code}: {detail}")
        return None, ("http", e.code)

    except URLError as e:
        print(f"[groq] model={model} URLError: {e}")
        return None, ("net", str(e))

    except Exception as e:
        print(f"[groq] model={model} other error: {e}")
        return None, ("other", str(e))


def ask_groq(question, context, lens=None):
    if not GROQ_KEY:
        return {"error": "no_key", "answer": "Live AI is off (no GROQ_API_KEY set in the Vercel project). The precomputed explanation above still applies."}

    last_err = None
    for model in GROQ_MODELS:
        answer, err = call_groq_model(model, question, context, LENS_SYSTEM.get(lens), "REPORT DATA" if lens in LENS_SYSTEM else "WARD DATA")
        if answer is not None:
            return {"answer": answer, "model_used": model}
        last_err = err

    kind, detail = last_err if last_err else ("other", "unknown")
    return {
        "error": kind,
        "answer": f"Couldn't reach the AI service (tried {len(GROQ_MODELS)} models, last error: {detail}). The precomputed explanation above still applies.",
    }


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(n)) if n else {}
            result = ask_groq(payload.get("question", ""), payload.get("context", ""), payload.get("lens"))
        except Exception as e:
            result = {"error": "bad_request", "answer": f"Request error: {e}"}
        out = json.dumps(result).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def do_GET(self):
        self.send_response(405)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"error":"method_not_allowed","answer":"POST only"}')
