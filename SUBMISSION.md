# Devpost submission copy — Nebius × NVIDIA Global AI Hackathon

**Deadline: Oct 30, 2026, 10:00 am PT. Track: Best Apps and Agents.**
**Also eligible: Best Use of Tavily bonus ($3,000) — the app makes a
functional runtime call to the Tavily API on every question.**

## Project name
CiteLens

## Tagline
A research agent that brings its sources — and flags any sentence it
can't back up.

## Description (paste-ready)

**Inspiration.** AI research tools answer fluently, but an uncited answer
forces the reader to re-derive every claim before trusting it. We wanted
the verification step to be part of the product, not homework after it.

**What it does.** You ask a question. CiteLens searches the live web with
the **Tavily API**, drafts an answer with **NVIDIA Nemotron** running on
**Nebius Token Factory**, and then runs a citation audit over its own
output: every sentence is checked for a valid source marker, the UI shows
a citation-coverage meter, and any uncited sentence is highlighted in red.
Each citation chip jumps to a source card with title, URL, date, and
relevance score.

**How we built it.** A zero-dependency Python service (standard library
only) with three explicit stages — retrieve, generate, verify — behind a
small JSON API, plus a vanilla-JS single-page UI. Nemotron is called
through Token Factory's OpenAI-compatible endpoint, so the model id is a
config value: Nano for fast calls, Super/Ultra for heavier reasoning. A
deterministic offline mode (bundled corpus + extractive composer) keeps
the full pipeline testable without keys; the test suite mocks both API
transports.

**Challenges.** Getting an LLM to cite *every* factual sentence — not
just some — took prompt discipline plus enforcement: the verifier treats
citation as a contract and surfaces violations instead of hiding them.

**What's next.** Source-quality weighting in the coverage score,
multi-question research sessions with a persistent evidence board, and
deploying the service on a Nebius Serverless Endpoint.

## Testing instructions (for judges)
1. Open the demo URL. The header badge shows LIVE (Nemotron on Token
   Factory) or DEMO mode.
2. Ask: "Why do AI research tools need citations?" — watch citations and
   the coverage meter.
3. Ask something the sources only partly cover and look for a red-flagged
   uncited sentence.
4. Or run it yourself: `python3 app.py` (no dependencies), tests:
   `python3 -m unittest discover -s tests`.

## Feedback for Nebius (submission form section — draft)
- Token Factory's OpenAI-compatible endpoint made swapping Nemotron
  model ids a one-line config change; a published, stable catalogue of
  model ids inside the console (with copy buttons) would remove the one
  guesswork step we hit.
- Builder Program credits covering both Token Factory and Tavily is
  exactly the right bundle for retrieval+inference apps.
- A lightweight "deploy this repo" path from Token Factory to a
  Serverless Endpoint would close the loop for hackathon demos.

## Pre-submit checklist
- [ ] Devpost: join hackathon, create project, paste copy above
- [ ] GitHub: push this repo (public, MIT license visible)
- [ ] Nebius Builder Program: claim credits; create Token Factory API key
- [ ] Tavily: API key (Builder Program credits or tavily.com free tier)
- [ ] Deploy demo (e.g. Render free tier) with the two keys as env vars;
      confirm header badge shows LIVE
- [ ] Record ≤3:00 demo from DEMO.md, upload public to YouTube
- [ ] Submit before Oct 30, 10:00 am PT
