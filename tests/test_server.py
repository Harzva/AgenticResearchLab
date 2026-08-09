import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.request import urlopen

from agentic_research_lab.paper_catalog import load_public_catalog
from agentic_research_lab.server import make_handler
from agentic_research_lab.store import index_catalog


class ServerTests(unittest.TestCase):
    def test_dashboard_and_search_api(self) -> None:
        with TemporaryDirectory() as directory:
            store = Path(directory) / "catalog.sqlite3"
            index_catalog(load_public_catalog(), store)
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(store))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                with urlopen(base, timeout=5) as response:
                    html = response.read().decode()
                self.assertIn("AgenticResearchLab", html)
                with urlopen(f"{base}/api/search?q=mobile%20agent", timeout=5) as response:
                    data = json.load(response)
                self.assertTrue(data["hits"])
                self.assertIn("source_url", data["hits"][0])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
