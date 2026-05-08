#!/usr/bin/env python3
"""
Unit tests for taskforge — все тесты офлайн, без живых вызовов claude.

Запуск:
    python3 -m unittest tests.test_taskforge -v
или:
    python3 tests/test_taskforge.py
"""
import json
import os
import sys
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path

# Загружаем модуль taskforge (бинарник без .py-расширения).
ROOT = Path(__file__).resolve().parent.parent
TF = SourceFileLoader("tf", str(ROOT / "bin" / "taskforge")).load_module()


# ─── Утилиты ──────────────────────────────────────────────────────────────────

class TestParseDuration(unittest.TestCase):
    def test_hours(self):
        self.assertEqual(TF.parse_duration("5h"), 18000)
        self.assertEqual(TF.parse_duration("1h"), 3600)

    def test_minutes(self):
        self.assertEqual(TF.parse_duration("30m"), 1800)
        self.assertEqual(TF.parse_duration("90m"), 5400)

    def test_seconds(self):
        self.assertEqual(TF.parse_duration("90s"), 90)
        self.assertEqual(TF.parse_duration("90"), 90)

    def test_invalid(self):
        with self.assertRaises(ValueError):
            TF.parse_duration("abc")
        with self.assertRaises(ValueError):
            TF.parse_duration("5x")


class TestFormatDuration(unittest.TestCase):
    def test_with_hours(self):
        self.assertEqual(TF.format_duration(3722), "1h 2m")
        self.assertEqual(TF.format_duration(7200), "2h 0m")

    def test_with_minutes(self):
        self.assertEqual(TF.format_duration(125), "2m 5s")
        self.assertEqual(TF.format_duration(60), "1m 0s")

    def test_seconds_only(self):
        self.assertEqual(TF.format_duration(45), "45s")
        self.assertEqual(TF.format_duration(0), "0s")


class TestSlugifyAndHash(unittest.TestCase):
    def test_slugify(self):
        self.assertEqual(TF.slugify("Hello World"), "hello-world")
        self.assertEqual(TF.slugify("  Hello WORLD  "), "hello-world")

    def test_normalize_for_hash_idempotent(self):
        h1 = TF.sha256_short(TF.normalize_for_hash("Hello   World"))
        h2 = TF.sha256_short(TF.normalize_for_hash("  hello WORLD  "))
        self.assertEqual(h1, h2)

    def test_hash_differs_for_different_text(self):
        h1 = TF.sha256_short(TF.normalize_for_hash("Task A"))
        h2 = TF.sha256_short(TF.normalize_for_hash("Task B"))
        self.assertNotEqual(h1, h2)

    def test_hash_length(self):
        self.assertEqual(len(TF.sha256_short("anything")), 16)


# ─── Конфиг ───────────────────────────────────────────────────────────────────

class TestValidateConfig(unittest.TestCase):
    def test_default_is_valid(self):
        self.assertEqual(TF.validate_config(TF.DEFAULT_CONFIG), [])

    def test_bad_model(self):
        cfg = json.loads(json.dumps(TF.DEFAULT_CONFIG))
        cfg["models"]["planner"] = "sonnet5"  # not in VALID_MODELS
        errs = TF.validate_config(cfg)
        self.assertTrue(any("planner" in e for e in errs))

    def test_team_count_zero_is_invalid(self):
        cfg = {**TF.DEFAULT_CONFIG, "team_count": 0}
        errs = TF.validate_config(cfg)
        self.assertTrue(any("team_count" in e for e in errs))

    def test_no_topics_is_invalid(self):
        cfg = {**TF.DEFAULT_CONFIG, "topics": []}
        errs = TF.validate_config(cfg)
        self.assertTrue(any("тем" in e.lower() for e in errs))

    def test_unknown_topic(self):
        cfg = {**TF.DEFAULT_CONFIG, "topics": ["bogus"]}
        errs = TF.validate_config(cfg)
        self.assertTrue(any("неизвестные" in e.lower() for e in errs))

    def test_session_limit_out_of_range(self):
        cfg = {**TF.DEFAULT_CONFIG, "session_limit_percent": 0}
        errs = TF.validate_config(cfg)
        self.assertTrue(any("session_limit_percent" in e for e in errs))
        cfg = {**TF.DEFAULT_CONFIG, "session_limit_percent": 150}
        errs = TF.validate_config(cfg)
        self.assertTrue(any("session_limit_percent" in e for e in errs))

    def test_effort_scalar_valid(self):
        cfg = {**TF.DEFAULT_CONFIG, "effort": "medium"}
        self.assertEqual(TF.validate_config(cfg), [])

    def test_effort_none_valid(self):
        cfg = {**TF.DEFAULT_CONFIG, "effort": "none"}
        self.assertEqual(TF.validate_config(cfg), [])

    def test_effort_scalar_bad(self):
        cfg = {**TF.DEFAULT_CONFIG, "effort": "crazy"}
        errs = TF.validate_config(cfg)
        # All three roles get the same scalar, so all three should error.
        self.assertEqual(sum(1 for e in errs if "effort." in e), 3)

    def test_effort_dict_valid(self):
        cfg = {**TF.DEFAULT_CONFIG,
               "effort": {"planner": "max", "executor": "low", "reviewer": "high"}}
        self.assertEqual(TF.validate_config(cfg), [])

    def test_effort_dict_partial_bad(self):
        cfg = {**TF.DEFAULT_CONFIG,
               "effort": {"planner": "crazy", "executor": "high", "reviewer": "high"}}
        errs = TF.validate_config(cfg)
        self.assertEqual(sum(1 for e in errs if "effort.planner" in e), 1)
        self.assertEqual(sum(1 for e in errs if "effort.executor" in e), 0)


# ─── Verdict / title ──────────────────────────────────────────────────────────

class TestVerdictExtraction(unittest.TestCase):
    def test_pass(self):
        s = "---\nverdict: pass\n---\n\n# Review\n..."
        self.assertEqual(TF.TeamRunner._extract_verdict(s), "pass")

    def test_revise_with_extra_yaml_keys(self):
        s = "---\nverdict: revise\nfoo: bar\n---\n\n..."
        self.assertEqual(TF.TeamRunner._extract_verdict(s), "revise")

    def test_discard(self):
        s = "---\nverdict: discard\n---\n\nbla"
        self.assertEqual(TF.TeamRunner._extract_verdict(s), "discard")

    def test_default_revise_when_no_yaml(self):
        s = "no yaml here, just text"
        self.assertEqual(TF.TeamRunner._extract_verdict(s), "revise")


class TestTitleExtraction(unittest.TestCase):
    def test_h1_present(self):
        s = "# Реализовать LRU кэш\n\n## Контекст\n..."
        self.assertEqual(TF.TeamRunner._extract_title(s), "Реализовать LRU кэш")

    def test_no_h1_falls_back_to_first_line(self):
        s = "Just text without heading"
        self.assertTrue(TF.TeamRunner._extract_title(s).startswith("Just text"))

    def test_truncates_long_first_line(self):
        s = "A" * 200
        self.assertLessEqual(len(TF.TeamRunner._extract_title(s)), 80)


# ─── Thinking extraction (mock JSONL) ─────────────────────────────────────────

class TestExtractThinking(unittest.TestCase):
    def _write_jsonl(self, records):
        f = tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8")
        for r in records:
            f.write(json.dumps(r) + "\n")
        f.close()
        return Path(f.name)

    def test_extract_single_thinking(self):
        path = self._write_jsonl([
            {"type": "user", "message": {"role": "user", "content": "hello"}},
            {"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "thinking", "thinking": "Let me think hard"},
                {"type": "text", "text": "Final"},
            ]}},
        ])
        try:
            t = TF._extract_thinking_from_jsonl(path)
            self.assertIn("Let me think hard", t)
            self.assertNotIn("Final", t)  # text blocks excluded
        finally:
            path.unlink()

    def test_extract_multiple_thinking_blocks(self):
        path = self._write_jsonl([
            {"type": "assistant", "message": {"content": [
                {"type": "thinking", "thinking": "First thought"},
            ]}},
            {"type": "assistant", "message": {"content": [
                {"type": "thinking", "thinking": "Second thought"},
            ]}},
        ])
        try:
            t = TF._extract_thinking_from_jsonl(path)
            self.assertIn("First thought", t)
            self.assertIn("Second thought", t)
        finally:
            path.unlink()

    def test_no_thinking_returns_empty(self):
        path = self._write_jsonl([
            {"type": "assistant", "message": {"content": [
                {"type": "text", "text": "Just an answer"},
            ]}},
        ])
        try:
            self.assertEqual(TF._extract_thinking_from_jsonl(path), "")
        finally:
            path.unlink()

    def test_handles_malformed_lines(self):
        f = tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8")
        f.write('{not json\n')
        f.write(json.dumps({
            "type": "assistant",
            "message": {"content": [{"type": "thinking", "thinking": "OK"}]}
        }) + "\n")
        f.close()
        path = Path(f.name)
        try:
            self.assertIn("OK", TF._extract_thinking_from_jsonl(path))
        finally:
            path.unlink()


# ─── effort_for ───────────────────────────────────────────────────────────────

class TestEffortFor(unittest.TestCase):
    class _Orch:
        def __init__(self, cfg): self.config = cfg

    def test_dict_role_specific(self):
        o = self._Orch({"effort": {"planner": "max",
                                    "executor": "low", "reviewer": "high"}})
        self.assertEqual(TF.Orchestrator.effort_for(o, "planner"), "max")
        self.assertEqual(TF.Orchestrator.effort_for(o, "executor"), "low")
        self.assertEqual(TF.Orchestrator.effort_for(o, "reviewer"), "high")

    def test_scalar_applies_to_all_roles(self):
        o = self._Orch({"effort": "medium"})
        self.assertEqual(TF.Orchestrator.effort_for(o, "planner"), "medium")
        self.assertEqual(TF.Orchestrator.effort_for(o, "executor"), "medium")
        self.assertEqual(TF.Orchestrator.effort_for(o, "reviewer"), "medium")

    def test_default_high_when_missing(self):
        self.assertEqual(TF.Orchestrator.effort_for(
            self._Orch({"effort": {}}), "planner"), "high")
        self.assertEqual(TF.Orchestrator.effort_for(
            self._Orch({}), "planner"), "high")

    def test_partial_dict_fills_default(self):
        o = self._Orch({"effort": {"planner": "max"}})
        self.assertEqual(TF.Orchestrator.effort_for(o, "planner"), "max")
        self.assertEqual(TF.Orchestrator.effort_for(o, "reviewer"), "high")


# ─── JSON I/O ─────────────────────────────────────────────────────────────────

class TestJsonIO(unittest.TestCase):
    def test_atomic_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "subdir" / "x.json"
            payload = {"hello": "world", "n": 42, "list": [1, 2, 3]}
            TF.write_json_atomic(p, payload)
            self.assertEqual(TF.read_json(p), payload)

    def test_read_json_missing(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(TF.read_json(Path(d) / "missing.json"))

    def test_read_json_malformed(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bad.json"
            p.write_text("{not json", encoding="utf-8")
            self.assertEqual(TF.read_json(p, default=[]), [])


# ─── Topics ───────────────────────────────────────────────────────────────────

class TestTopics(unittest.TestCase):
    def test_ten_topics(self):
        self.assertEqual(len(TF.TOPICS), 10)

    def test_all_topic_titles_present(self):
        for slug, title in TF.TOPICS:
            self.assertTrue(title)
            self.assertIn(slug, TF.TOPIC_TITLES)


if __name__ == "__main__":
    unittest.main(verbosity=2)
