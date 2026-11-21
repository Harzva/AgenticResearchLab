from contextlib import redirect_stderr
from datetime import date, datetime, timezone
from http.client import IncompleteRead
from io import BytesIO, StringIO
import unittest

from daily import (
    ATOM,
    EXCERPT_CHARS,
    MAX_ATOM_CANDIDATES,
    candidate,
    create_edition,
    edition_markdown,
    stream_atom_candidates,
)


def entry(number):
    return (
        f"<entry><id>http://export.arxiv.org/abs/2611.{number:05d}v1</id>"
        "<title>Agent evaluation fixture</title>"
        "<published>2026-11-20T05:00:00Z</published>"
        "<summary>Evaluation fixture for the Atom reader.</summary></entry>"
    )


def atom(count):
    return (f'<feed xmlns="{ATOM}">' + "".join(entry(i) for i in range(count))).encode()


class InterruptedAtom(BytesIO):
    def read1(self, size):
        chunk = super().read1(size)
        if chunk:
            return chunk
        raise IncompleteRead(b"")


class DailyTest(unittest.TestCase):
    def test_reader_stops_after_enough_complete_entries(self):
        document = BytesIO(atom(MAX_ATOM_CANDIDATES + 100) + b"</feed>")
        candidates = stream_atom_candidates(document)
        self.assertEqual(len(candidates), MAX_ATOM_CANDIDATES)
        self.assertLess(document.tell(), len(document.getvalue()))
        self.assertEqual(candidates[0]["url"], "https://arxiv.org/abs/2611.00000")
        self.assertEqual(candidates[0]["pdf_url"], "https://arxiv.org/pdf/2611.00000")

    def test_wrong_root_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Expected an arXiv Atom feed"):
            stream_atom_candidates(BytesIO(b"<result/>"))

    def test_interruption_only_uses_sufficient_complete_entries(self):
        with self.assertRaises(IncompleteRead):
            stream_atom_candidates(InterruptedAtom(atom(2)))
        with redirect_stderr(StringIO()):
            papers = stream_atom_candidates(InterruptedAtom(atom(5) + b"<entry>"))
        self.assertEqual(len(papers), 5)

    def test_past_promotion_omits_sources_already_used_later(self):
        published = "2026-11-20T05:00:00Z"
        repeated = candidate("Agent evaluation fixture", "https://arxiv.org/abs/2611.00123", None, published, "")
        other = candidate("Agent evaluation fixture", "https://arxiv.org/abs/2611.00456", None, published, "")
        history = [{"date": "2026-11-21", "mode": "fresh", "items": [repeated]}]
        now = datetime(2026, 11, 20, 8, tzinfo=timezone.utc)
        edition = create_edition(date(2026, 11, 20), now, {}, [repeated, other], history)
        self.assertEqual([item["url"] for item in edition["items"]], [other["url"]])

    def test_curated_review_keeps_the_full_editorial_summary(self):
        summary = (
            "ResearchAgent 由一篇种子论文找出相关文献与知识实体，"
            "再逐轮改写研究问题、方法和实验设计。多个评审 Agent 提供结构化反馈。"
        )
        feed = {"items": [{
            "title": "ResearchAgent",
            "summary": summary,
            "published_at": "2024-04-11",
            "sources": [{"type": "paper", "url": "https://arxiv.org/abs/2404.07738"}],
        }]}
        now = datetime(2026, 11, 21, 6, tzinfo=timezone.utc)
        edition = create_edition(date(2026, 11, 21), now, feed, [], [])
        self.assertEqual(edition["mode"], "review")
        self.assertEqual(edition["items"][0]["excerpt"], summary)
        self.assertIn(summary, edition_markdown(edition))

    def test_fresh_excerpt_prefers_a_complete_relevant_sentence(self):
        for sentence, introduction in (
            ("We evaluate the agent on 3.5-hour tasks, e.g. those in Fig. 2.", "Prior work frames the problem. "),
            ("我们用固定实验任务对照两类 Agent。", "背景材料介绍了这项工作的范围。"),
        ):
            with self.subTest(sentence=sentence):
                paper = candidate(
                    "Agent study", "https://arxiv.org/abs/2611.00456", None, "2026-11-21T05:00:00Z",
                    introduction * 25 + sentence,
                )
                now = datetime(2026, 11, 21, 6, tzinfo=timezone.utc)
                edition = create_edition(date(2026, 11, 21), now, {}, [paper], [])
                self.assertEqual(edition["mode"], "fresh")
                self.assertEqual(edition["items"][0]["excerpt"], sentence)

    def test_fresh_long_sentence_falls_back_to_a_whole_word_prefix(self):
        abstract = "Agent evaluation " + "methodology " * 35 + "concludes here."
        paper = candidate("Agent study", "https://arxiv.org/abs/2611.00456", None, "2026-11-21T05:00:00Z", abstract)
        now = datetime(2026, 11, 21, 6, tzinfo=timezone.utc)
        edition = create_edition(date(2026, 11, 21), now, {}, [paper], [])
        excerpt = edition["items"][0]["excerpt"]
        self.assertLessEqual(len(excerpt), EXCERPT_CHARS)
        self.assertTrue(excerpt.startswith("Agent evaluation methodology"))
        self.assertTrue(excerpt.endswith(" methodology…"))


if __name__ == "__main__":
    unittest.main()
