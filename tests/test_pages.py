import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


class PagesTests(unittest.TestCase):
    def test_static_pages_build_contains_public_catalog(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with TemporaryDirectory() as directory:
            output = Path(directory) / "site"
            subprocess.run(
                [sys.executable, str(root / "scripts/build_pages.py"), "--output", str(output)],
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads((output / "data/catalog.json").read_text(encoding="utf-8"))
            html = (output / "index.html").read_text(encoding="utf-8")
            self.assertEqual(payload["summary"]["papers"], 1242)
            self.assertEqual(payload["summary"]["with_code"], 154)
            self.assertEqual(len(payload["papers"]), 1242)
            self.assertTrue((output / ".nojekyll").is_file())
            self.assertIn("assets/site.js", html)
            serialized = json.dumps(payload)
            self.assertNotIn("/" + "Users/", serialized)
            self.assertNotIn("/" + "Volumes/", serialized)


if __name__ == "__main__":
    unittest.main()
