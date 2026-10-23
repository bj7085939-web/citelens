# CiteLens — answers that bring their sources

CiteLens is a research agent that refuses to answer from thin air. Ask it a
question and it (1) searches the live web, (2) drafts an answer grounded in
what it found, and then (3) **audits its own answer** — every factual
sentence must carry a citation, and any sentence that doesn't is flagged in
the UI instead of being silently trusted.

Built for the **Nebius × NVIDIA Global AI Hackathon** — *Best Apps and
Agents* track, and designed to also qualify for the *Best Use of Tavily*
bonus.

## How the sponsor stack is used

| Piece | Technology | Where |
|---|---|---|
| Inference | **NVIDIA Nemotron** (open-weight) served by **Nebius Token Factory** via its OpenAI-compatible chat-completions API — one runtime call per question | `app.py → llm_answer()` |
| Retrieval | **Tavily** search API — one runtime call per question; results normalised into numbered sources | `app.py → tavily_search()` |
| Verification | CiteLens' own citation checker: sentence segmentation, citation extraction, coverage scoring, uncited-claim flagging | `app.py → verify_citations()` |

The model is deliberately interchangeable (`NEBIUS_MODEL`): Nemotron 3 Nano
for fast everyday calls, a Nemotron Super/Ultra model id from the Token
Factory catalogue when a question needs heavier reasoning.

## Quickstart

Zero third-party dependencies — Python 3.10+ standard library only.

```bash
# Demo mode (no keys): bundled sample corpus + deterministic extractive answers
python3 app.py
# open http://127.0.0.1:8000

# Live mode: copy .env.example, fill in your keys, then
NEBIUS_API_KEY=... TAVILY_API_KEY=... python3 app.py
```

Hackathon participants can get Token Factory and Tavily credits through
the **Nebius Builder Program** (linked from the hackathon rules).

## Tests

```bash
python3 -m unittest discover -s tests   # 10 tests, transports mocked, no network
```

## Why it matters

Teams adopting AI research tools consistently rank *verifiability* as a top
requirement, because an uncited answer forces a human to re-derive every
number before it can be used. CiteLens moves verification from
re-derivation to spot-checking: claims arrive with their evidence attached,
and the coverage meter (e.g. "7/8 sentences cited") plus red-flagged
uncited sentences make the remaining risk visible at a glance.

## Layout

```
app.py                  server + retrieve/generate/verify pipeline
static/                 single-page UI (vanilla HTML/CSS/JS)
data/sample_corpus.json offline demo corpus
tests/                  unit tests (mocked transports)
DEMO.md                 3-minute demo-video shot list
SUBMISSION.md           Devpost submission copy + testing instructions
```

## License

MIT — see `LICENSE`.
