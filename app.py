#!/usr/bin/env python3
"""
CiteLens — a research agent that brings its sources.

Pipeline:
  1. Retrieve  : Tavily web search (runtime API call) — or a bundled offline
                 corpus when no API key is configured (demo mode).
  2. Generate  : NVIDIA Nemotron on Nebius Token Factory (OpenAI-compatible
                 chat completions) — or a deterministic extractive composer
                 in demo mode.
  3. Verify    : a citation checker walks every sentence of the answer and
                 flags any factual sentence that carries no [n] citation, so
                 unsupported claims are visible instead of silent.

Zero third-party dependencies: Python 3.10+ standard library only.
Run:  python3 app.py            (http://127.0.0.1:8000)
Env:  NEBIUS_API_KEY, NEBIUS_BASE_URL, NEBIUS_MODEL, TAVILY_API_KEY, PORT
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

class Config:
    def __init__(self, env: dict | None = None):
        env = os.environ if env is None else env
        self.nebius_api_key = env.get("NEBIUS_API_KEY", "").strip()
        self.nebius_base_url = env.get(
            "NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1/"
        ).rstrip("/")
        # Any NVIDIA Nemotron model served by Token Factory works; the model
        # id is configurable because the console catalogue is the source of
        # truth. Nemotron 3 Nano is the fast default; use a Super/Ultra id
        # for heavier reasoning.
        self.model = env.get("NEBIUS_MODEL", "nvidia/nemotron-3-nano-30b-a3b")
        self.tavily_api_key = env.get("TAVILY_API_KEY", "").strip()
        self.port = int(env.get("PORT", "8000"))

    @property
    def live(self) -> bool:
        """Live mode needs both retrieval and generation keys."""
        return bool(self.nebius_api_key and self.tavily_api_key)


# --------------------------------------------------------------------------
# Retrieval
# --------------------------------------------------------------------------

def http_post_json(url: str, payload: dict, headers: dict, timeout: int = 60):
    """POST JSON and return parsed JSON. Raises on HTTP errors."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    for k, v in headers.items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def tavily_search(query: str, api_key: str, max_results: int = 6,
                  transport=http_post_json) -> list[dict]:
    """Call the Tavily search API and normalise the result list."""
    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": "advanced",
        "max_results": max_results,
        "include_answer": False,
        "include_raw_content": False,
    }
    raw = transport("https://api.tavily.com/search", payload, {})
    sources = []
    for i, r in enumerate(raw.get("results", []), start=1):
        sources.append({
            "id": i,
            "title": r.get("title", "Untitled"),
            "url": r.get("url", ""),
            "content": (r.get("content") or "").strip(),
            "score": r.get("score"),
            "published_date": r.get("published_date"),
        })
    return [s for s in sources if s["content"]]


_WORD_RE = re.compile(r"[a-z0-9]+")
_STOP = set("the a an of to in is are was were what how why when who which "
            "does do did can could should would and or for with on at by".split())


def _terms(text: str) -> set[str]:
    return {w for w in _WORD_RE.findall(text.lower()) if w not in _STOP and len(w) > 2}


def offline_search(query: str, corpus: list[dict], max_results: int = 6) -> list[dict]:
    """Keyword-overlap search over the bundled demo corpus."""
    q = _terms(query)
    scored = []
    for doc in corpus:
        hay = _terms(doc["title"] + " " + doc["content"])
        overlap = len(q & hay)
        scored.append((overlap, doc))
    scored.sort(key=lambda t: -t[0])
    picked = [d for ov, d in scored if ov > 0][:max_results]
    if not picked:  # fall back to the first entries so the demo never dead-ends
        picked = corpus[:3]
    return [{"id": i, "title": d["title"], "url": d["url"],
             "content": d["content"], "score": None,
             "published_date": d.get("published_date")}
            for i, d in enumerate(picked, start=1)]


# --------------------------------------------------------------------------
# Generation
# --------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are CiteLens, a research assistant. Answer the user's question "
    "using ONLY the numbered sources provided. Every sentence that states a "
    "fact must end with the citation marker(s) of the source(s) it came "
    "from, like [1] or [2][3]. Do not invent facts, numbers, or sources. "
    "If the sources do not answer the question, say so plainly. Write "
    "150-250 words in plain paragraphs, no markdown tables or bullet lists."
)


def build_user_prompt(question: str, sources: list[dict]) -> str:
    blocks = []
    for s in sources:
        blocks.append(f"[{s['id']}] {s['title']}\nURL: {s['url']}\n{s['content']}")
    return ("Question: " + question + "\n\nSources:\n\n" + "\n\n".join(blocks))


def llm_answer(question: str, sources: list[dict], cfg: Config,
               transport=http_post_json) -> str:
    """One runtime call to Nebius Token Factory chat completions."""
    payload = {
        "model": cfg.model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(question, sources)},
        ],
        "temperature": 0.2,
        "max_tokens": 700,
    }
    headers = {"Authorization": f"Bearer {cfg.nebius_api_key}"}
    raw = transport(f"{cfg.nebius_base_url}/chat/completions", payload, headers)
    return raw["choices"][0]["message"]["content"].strip()


_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\x22])")
_REF_RE = re.compile(r"\[(\d+)\]")


def split_sentences(text: str) -> list[str]:
    parts = _SENT_SPLIT.split(text.strip())
    return [p.strip() for p in parts if p and p.strip()]


def verify_citations(answer: str, n_sources: int) -> dict:
    """Split the answer into sentences and check each for valid citations."""
    segments = []
    for sent in split_sentences(answer):
        refs = sorted({int(m) for m in _REF_RE.findall(sent)
                       if 1 <= int(m) <= n_sources})
        segments.append({"text": sent, "refs": refs, "cited": bool(refs)})
    cited = sum(1 for s in segments if s["cited"])
    return {
        "segments": segments,
        "sentences": len(segments),
        "cited": cited,
        "coverage": (cited / len(segments)) if segments else 0.0,
    }


def _rank_sentences(query_terms: set[str], content: str) -> list[str]:
    sents = split_sentences(content)
    scored = []
    for s in sents:
        st = _terms(s)
        scored.append((len(query_terms & st), s))
    scored.sort(key=lambda t: -t[0])
    return [s for sc, s in scored if sc > 0]


def extractive_answer(question: str, sources: list[dict]) -> str:
    """Demo-mode composer: stitch the most relevant source sentences
    together, each carrying its citation, so coverage is 100% by design."""
    q = _terms(question)
    pieces = []
    for s in sources:
        for sent in _rank_sentences(q, s["content"])[:2]:
            sent = sent.rstrip(".")
            pieces.append(f"{sent} [{s['id']}].")
        if len(pieces) >= 6:
            break
    if not pieces:
        return ("I could not find relevant material in the available sources "
                "to answer that question.")
    body = " ".join(pieces[:6])
    # Grammatical lead-in fused into the first sentence so the verifier
    # sees only cited factual sentences.
    return "Based on the retrieved sources, " + body[0].lower() + body[1:]


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------

def answer_question(question: str, cfg: Config, corpus: list[dict]) -> dict:
    if cfg.live:
        sources = tavily_search(question, cfg.tavily_api_key)
        text = llm_answer(question, sources, cfg)
        mode = "live"
    else:
        sources = offline_search(question, corpus)
        text = extractive_answer(question, sources)
        mode = "demo"
    check = verify_citations(text, len(sources))
    return {
        "question": question,
        "mode": mode,
        "model": cfg.model if mode == "live" else "extractive-demo",
        "answer": text,
        "segments": check["segments"],
        "stats": {k: check[k] for k in ("sentences", "cited", "coverage")},
        "sources": sources,
    }


# --------------------------------------------------------------------------
# HTTP server
# --------------------------------------------------------------------------

def make_handler(cfg: Config, corpus: list[dict]):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # keep stdout clean
            pass

        def _send(self, code: int, body: bytes, ctype: str):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, obj: dict):
            self._send(code, json.dumps(obj).encode("utf-8"),
                       "application/json; charset=utf-8")

        def do_GET(self):
            path = self.path.split("?")[0]
            if path == "/api/health":
                return self._json(200, {"ok": True, "live": cfg.live,
                                        "model": cfg.model})
            rel = "static/index.html" if path == "/" else path.lstrip("/")
            target = (ROOT / rel).resolve()
            if target.is_file() and str(target).startswith(str(ROOT)):
                ctype = {".html": "text/html; charset=utf-8",
                         ".css": "text/css", ".js": "text/javascript",
                         ".json": "application/json"}.get(
                             target.suffix, "application/octet-stream")
                return self._send(200, target.read_bytes(), ctype)
            return self._json(404, {"error": "not found"})

        def do_POST(self):
            if self.path.split("?")[0] != "/api/ask":
                return self._json(404, {"error": "not found"})
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length) or b"{}")
                question = str(body.get("question", "")).strip()
                if not question:
                    return self._json(400, {"error": "question is required"})
                return self._json(200, answer_question(question, cfg, corpus))
            except Exception as exc:  # surface, never crash the server
                return self._json(502, {"error": f"{type(exc).__name__}: {exc}"})

    return Handler


def load_corpus() -> list[dict]:
    p = ROOT / "data" / "sample_corpus.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def main():
    cfg = Config()
    corpus = load_corpus()
    mode = "LIVE" if cfg.live else "DEMO (offline corpus)"
    print(f"CiteLens on http://127.0.0.1:{cfg.port}  mode={mode}  "
          f"model={cfg.model}", file=sys.stderr)
    ThreadingHTTPServer(("127.0.0.1", cfg.port),
                        make_handler(cfg, corpus)).serve_forever()


if __name__ == "__main__":
    main()
