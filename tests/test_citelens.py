"""Unit tests for the CiteLens pipeline (no network, transports mocked)."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import app as citelens  # noqa: E402


CORPUS = json.loads((Path(__file__).resolve().parent.parent
                     / "data" / "sample_corpus.json").read_text(encoding="utf-8"))


class TestOfflineSearch(unittest.TestCase):
    def test_relevant_doc_ranks_first(self):
        hits = citelens.offline_search("why do citations matter in AI answers", CORPUS)
        self.assertTrue(hits)
        self.assertIn("citations matter", hits[0]["title"])

    def test_ids_are_sequential(self):
        hits = citelens.offline_search("Nemotron open models", CORPUS)
        self.assertEqual([h["id"] for h in hits], list(range(1, len(hits) + 1)))


class TestTavilyMapping(unittest.TestCase):
    def test_results_normalised(self):
        def fake_transport(url, payload, headers):
            assert url == "https://api.tavily.com/search"
            assert payload["api_key"] == "tvly-test"
            return {"results": [
                {"title": "T", "url": "https://x.example", "content": "body",
                 "score": 0.9, "published_date": "2026-01-01"},
                {"title": "Empty", "url": "https://y.example", "content": "  "},
            ]}
        out = citelens.tavily_search("q", "tvly-test", transport=fake_transport)
        self.assertEqual(len(out), 1)  # empty-content result dropped
        self.assertEqual(out[0]["id"], 1)
        self.assertEqual(out[0]["title"], "T")


class TestVerifier(unittest.TestCase):
    def test_all_cited(self):
        stats = citelens.verify_citations("Water is wet [1]. The sky is blue [2].", 2)
        self.assertEqual(stats["coverage"], 1.0)
        self.assertEqual(stats["cited"], 2)

    def test_uncited_flagged(self):
        stats = citelens.verify_citations("Water is wet [1]. Sales doubled last year.", 1)
        self.assertEqual(stats["coverage"], 0.5)
        self.assertFalse(stats["segments"][1]["cited"])

    def test_out_of_range_ref_ignored(self):
        stats = citelens.verify_citations("A claim with a bogus ref [9].", 2)
        self.assertEqual(stats["segments"][0]["refs"], [])
        self.assertFalse(stats["segments"][0]["cited"])


class TestExtractiveComposer(unittest.TestCase):
    def test_every_sentence_cited(self):
        sources = citelens.offline_search("why citations matter", CORPUS)
        answer = citelens.extractive_answer("why citations matter", sources)
        stats = citelens.verify_citations(answer, len(sources))
        self.assertEqual(stats["coverage"], 1.0, answer)

    def test_empty_sources(self):
        self.assertIn("could not find", citelens.extractive_answer("x", []))


class TestLLMPath(unittest.TestCase):
    def test_llm_answer_parses_response(self):
        def fake_transport(url, payload, headers):
            assert url.endswith("/chat/completions")
            assert headers["Authorization"] == "Bearer neb-test"
            assert payload["model"].startswith("nvidia/")
            return {"choices": [{"message": {"content": "Answer [1]."}}]}
        cfg = citelens.Config({"NEBIUS_API_KEY": "neb-test", "TAVILY_API_KEY": "t"})
        src = [{"id": 1, "title": "T", "url": "https://x", "content": "body"}]
        self.assertEqual(citelens.llm_answer("q?", src, cfg, transport=fake_transport),
                         "Answer [1].")

    def test_config_live_requires_both_keys(self):
        self.assertFalse(citelens.Config({"NEBIUS_API_KEY": "x"}).live)
        self.assertTrue(citelens.Config(
            {"NEBIUS_API_KEY": "x", "TAVILY_API_KEY": "y"}).live)


if __name__ == "__main__":
    unittest.main(verbosity=2)
