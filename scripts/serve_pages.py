from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from build_pages import DEFAULT_OUTPUT, build


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and serve the static Pages site")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18767)
    args = parser.parse_args()
    result = build(DEFAULT_OUTPUT)
    handler = partial(SimpleHTTPRequestHandler, directory=str(DEFAULT_OUTPUT))
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(
        f"AgenticResearchLab Pages preview: http://{args.host}:{args.port} "
        f"({result['papers']} papers)"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
