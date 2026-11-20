"""Verify the experiment notebook's status, evidence, and static publication contract."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import build


REVISION = "1234567890abcdef" * 2 + "12345678"
RUN_URL = "https://example.org/runs/paperbench-aqua-test-split"
REVIEW_URL = "https://example.org/reviews/paperbench-aqua-test-split"
RUBRIC_NODE = "43f23e0e-2c5b-4a2b-80ab-6cc9c62723f1"
SEED_ID = "paperbench-aqua-test-split"


class CommunityTest(unittest.TestCase):
    def setUp(self):
        self.source_data = build.read_community()
        self.seed = next(note for note in self.source_data["notes"] if note["id"] == SEED_ID)
        self.note = deepcopy(self.seed)
        self.note["status"] = "planned"
        self.note.pop("run", None)
        self.note.pop("review", None)
        self.data = {"schema_version": 1, "notes": [self.note]}
        self.item_ids = {item["id"] for item in build.read_feed()["items"]}

    def validate(self):
        build.validate_community(self.data, self.item_ids)

    def report_run(self, outcome):
        self.note.update(status="reported", run={
            "author": "ExampleAuthor",
            "revision": REVISION,
            "environment": "Python 3.12",
            "method": "按计划检查 JSONL 格式，记录退出状态。",
            "observed": "测试夹具模拟运行记录。",
            "outcome": outcome,
            "evidence": [{"title": "公开测试日志", "url": RUN_URL}],
        })
        return self.note["run"]

    def add_review(self):
        self.note.update(status="reviewed", review={
            "reviewer": "ExampleReviewer",
            "revision": REVISION,
            "url": REVIEW_URL,
            "evidence_url": RUN_URL,
            "summary": "测试夹具模拟复核记录。",
        })
        return self.note["review"]

    def test_seed_build_preserves_the_checked_in_record_and_discovery_links(self):
        self.assertEqual(self.seed["item_id"], "paperbench")
        self.assertIn(RUBRIC_NODE, self.seed["scope"])
        self.assertIn("254", self.seed["expected"])
        urls = [source["url"] for source in self.seed["sources"]]
        for revision in ("b78dab1da774a6456b1ed9c48c9ff194ee3ff36d", "26b64ed1f22208c6742f47df547dfd65088ec30d"):
            self.assertTrue(any(revision in url for url in urls), revision)
        with TemporaryDirectory() as temp:
            out = Path(temp) / "public"
            build.build(out)
            self.assertEqual(json.loads((out / "community/index.json").read_text()), self.source_data)
            markdown = (out / "community" / (SEED_ID + ".md")).read_text()
            self.assertIn(build.COMMUNITY_STATUS[self.seed["status"]], markdown)
            self.assertIn("## 计划步骤", markdown)
            self.assertIn("## 预期产物", markdown)
            self.assertIn("../items/paperbench.md", markdown)
            self.assertIn("?view=community&note=" + SEED_ID, markdown)
            index = (out / "llms.txt").read_text()
            for path in ("community/index.json", f"community/{SEED_ID}.md", "daily/latest.json", "rss.xml"):
                self.assertIn(f"]({path})", index)
            self.assertEqual(json.loads((out / "feed.json").read_text()), build.read_feed())
            self.assertTrue((out / "rss.xml").stat().st_size)

    def test_planned_build_explicitly_has_no_experiment_result(self):
        with TemporaryDirectory() as temp:
            out = Path(temp) / "planned"
            with patch.object(build, "read_community", return_value=self.data):
                build.build(out)
            record = json.loads((out / "community/index.json").read_text())["notes"][0]
            self.assertEqual(record["status"], "planned")
            self.assertNotIn("run", record)
            self.assertNotIn("review", record)
            markdown = (out / "community" / (SEED_ID + ".md")).read_text()
            self.assertIn("待复现", markdown)
            self.assertIn("实验结果未评估", markdown)
            self.assertNotIn("实际观察", markdown)
            self.assertNotIn("## 独立复核", markdown)

    def test_note_id_matches_selected_item_and_route_limit(self):
        fixture = deepcopy(self.note)
        for change, error in (
            ({"item_id": "missing"}, "existing selected item"),
            ({"id": "unlinked-test-split"}, "start with item_id"),
            ({"id": "paperbench-INVALID"}, "lowercase letters"),
            ({"id": "paperbench-" + "x" * 90}, "at most 100 characters"),
        ):
            with self.subTest(change=change):
                self.note.clear()
                self.note.update(fixture, **change)
                with self.assertRaisesRegex(ValueError, error):
                    self.validate()
        self.note.update(id="paperbench-" + "x" * 89)
        self.validate()
        self.data["notes"].append(deepcopy(self.note))
        with self.assertRaisesRegex(ValueError, "duplicates a note ID"):
            self.validate()

    def test_plan_requires_structured_steps_and_has_no_run_or_review(self):
        fixture = deepcopy(self.note)
        for change, error in (
            ({"steps": []}, "non-empty array of text"),
            ({"steps": [" "]}, "non-empty text"),
            ({"status": "done"}, "status must be planned"),
            ({"status": "reported"}, "run is required"),
            ({"run": None}, "must not contain run or review"),
            ({"review": None}, "must not contain run or review"),
        ):
            with self.subTest(change=change):
                self.note.clear()
                self.note.update(fixture, **change)
                with self.assertRaisesRegex(ValueError, error):
                    self.validate()
        self.data["schema_version"] = True
        with self.assertRaisesRegex(ValueError, "schema_version must be 1"):
            self.validate()

    def test_public_url_validation_covers_sources_and_embedded_links(self):
        original = deepcopy(self.note["sources"])
        for invalid in (
            "http://example.org/evidence",
            "https://127.0.0.1/evidence",
            "https://storage.mesh.harzva.online/evidence",
            "https://example.org/evidence?access_token=fake",
        ):
            with self.subTest(url=invalid):
                self.note["sources"] = [{"title": "测试夹具", "url": invalid}]
                with self.assertRaisesRegex(ValueError, "public HTTPS URL"):
                    self.validate()
        self.note["sources"] = original
        self.note["steps"] = ["测试夹具包含 https://127.0.0.1/evidence 链接。"]
        with self.assertRaisesRegex(ValueError, r"steps\[1\].*public HTTPS URL"):
            self.validate()

    def test_run_needs_separate_output_at_an_immutable_revision(self):
        run = self.report_run("not_reproduced")
        source = self.note["sources"][0]
        equivalent_url = source["url"].replace("://github.com", "://GITHUB.COM") + "/"
        run["evidence"] = [{"title": "输入 URL 测试夹具", "url": equivalent_url}]
        with self.assertRaisesRegex(ValueError, "run output distinct from the input materials"):
            self.validate()
        run["evidence"] = []
        with self.assertRaisesRegex(ValueError, "evidence must be a non-empty array"):
            self.validate()
        run["evidence"] = [
            {"title": "测试日志", "url": RUN_URL},
            {"title": "同一测试日志", "url": RUN_URL + "/"},
        ]
        with self.assertRaisesRegex(ValueError, "duplicates a link"):
            self.validate()
        run["evidence"].pop()
        run["revision"] = "main"
        with self.assertRaisesRegex(ValueError, "full Git commit SHA"):
            self.validate()
        run["revision"] = REVISION
        run["outcome"] = "failed"
        with self.assertRaisesRegex(ValueError, "outcome must be"):
            self.validate()
        run["outcome"] = None
        self.validate()
        self.note["review"] = None
        with self.assertRaisesRegex(ValueError, "review requires reviewed status"):
            self.validate()

    def test_review_must_be_independent_and_cover_the_same_run_output(self):
        run = self.report_run("partial")
        self.note["status"] = "reviewed"
        with self.assertRaisesRegex(ValueError, "review has missing or unexpected fields"):
            self.validate()
        review = self.add_review()
        fixture = deepcopy(review)
        run["evidence"].append(deepcopy(self.note["sources"][0]))
        self.validate()
        for change, error in (
            ({"reviewer": " @eXAMPLEaUTHOR "}, "distinct from the run author"),
            ({"revision": "a" * 40}, "does not match the recorded run"),
            ({"evidence_url": self.note["sources"][0]["url"]}, "must match published run output"),
            ({"evidence_url": RUN_URL + "-old"}, "must match published run output"),
            ({"url": "https://review.internal/result"}, "public HTTPS URL"),
        ):
            with self.subTest(change=change):
                review.clear()
                review.update(fixture, **change)
                with self.assertRaisesRegex(ValueError, error):
                    self.validate()

    def test_actual_builds_preserve_negative_partial_and_unassessed_results(self):
        run = self.report_run("not_reproduced")
        with TemporaryDirectory() as temp:
            for index, (outcome, label) in enumerate((
                ("not_reproduced", "未复现"), ("partial", "部分复现"), (None, "未评估"),
            )):
                with self.subTest(outcome=outcome):
                    run["outcome"] = outcome
                    out = Path(temp) / str(index)
                    with patch.object(build, "read_community", return_value=self.data):
                        build.build(out)
                    record = json.loads((out / "community/index.json").read_text())["notes"][0]
                    self.assertEqual(record["run"], run)
                    markdown = (out / "community" / (SEED_ID + ".md")).read_text()
                    self.assertIn("公开运行记录", markdown)
                    self.assertIn(f"**结果** {label}", markdown)
                    self.assertIn(run["observed"], markdown)
                    self.assertIn(RUN_URL, markdown)
            run["outcome"] = "not_reproduced"
            self.add_review()
            out = Path(temp) / "review"
            with patch.object(build, "read_community", return_value=self.data):
                build.build(out)
            markdown = (out / "community" / (SEED_ID + ".md")).read_text()
            self.assertIn("**状态** 独立复核", markdown)
            self.assertIn("**结果** 未复现", markdown)
            self.assertIn(f"**复核版本** {REVISION}", markdown)
            self.assertIn(f"[对应运行证据](<{RUN_URL}>)", markdown)
            self.assertIn(f"[复核记录](<{REVIEW_URL}>)", markdown)
            for name in ("feed.json", "rss.xml"):
                self.assertEqual(
                    sha256((out / name).read_bytes()).digest(),
                    sha256((Path(temp) / "0" / name).read_bytes()).digest(),
                )


if __name__ == "__main__":
    unittest.main()
