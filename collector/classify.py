"""Keyword rules from config/keywords.json decide what is kept and how it is labelled."""
import json
import re
from pathlib import Path

CONFIG = Path(__file__).resolve().parent.parent / "config" / "keywords.json"


def _rx(words):
    words = [w for w in words if w.strip()]
    if not words:
        return re.compile(r"(?!x)x")
    parts = []
    for w in sorted(words, key=len, reverse=True):
        e = re.escape(w.strip())
        # Short Latin tokens (AI, SW, IR) must not match inside other words ("MAIN", "SWIFT").
        parts.append(rf"(?<![A-Za-z]){e}(?![A-Za-z])" if re.fullmatch(r"[A-Za-z.]{1,4}", w.strip()) else e)
    return re.compile("|".join(parts), re.I)


class Rules:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.ai = _rx(cfg.get("aiTerms", []))
        self.related = _rx(cfg.get("relatedTerms", []))
        self.comp = _rx(cfg.get("competitionTerms", []))
        self.exclude = _rx(cfg.get("excludeTerms", []))
        self.topics = {k: _rx(v) for k, v in cfg.get("extraTopics", {}).items()}
        self.cats = [(k, _rx(v)) for k, v in cfg.get("categories", {}).items()]
        self.regions = cfg.get("regions", [])

    @classmethod
    def load(cls, path: Path = CONFIG):
        return cls(json.loads(path.read_text(encoding="utf-8")))

    def judge(self, title: str, *, is_contest_list: bool, extra_text: str = "") -> dict | None:
        """Return labels for a kept item, or None to drop it.

        is_contest_list: the source only lists contests (so the title needn't say "대회").
        """
        text = f"{title} {extra_text}"
        if not self.contest_gate(title, is_contest_list=is_contest_list):
            return None
        ai_strong = bool(self.ai.search(text))
        ai_weak = bool(self.related.search(title))
        topic = next((k for k, rx in self.topics.items() if rx.search(title)), None)
        if not (ai_strong or ai_weak or topic):
            return None
        return {
            "aiRelated": ai_strong or ai_weak,
            "confidence": "high" if ai_strong or topic else "medium",
            "category": self.category(title),
            "region": self.region(text),
        }

    def contest_gate(self, title: str, *, is_contest_list: bool) -> bool:
        """The contest part of judge(): not excluded, and recognisably a contest."""
        if self.exclude.search(title) and not self.comp.search(title):
            return False
        return is_contest_list or bool(self.comp.search(title))

    def region(self, text: str) -> str | None:
        return next((r for r in self.regions if r in text), None)

    def category(self, title: str) -> str:
        return next((k for k, rx in self.cats if rx.search(title)), "other")
