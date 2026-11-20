from contextlib import redirect_stderr
from datetime import date, datetime, timezone
from http.client import IncompleteRead
from io import BytesIO, StringIO
import unittest

from daily import ATOM, MAX_ATOM_CANDIDATES, candidate, create_edition, stream_atom_candidates


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


if __name__ == "__main__":
    unittest.main()
