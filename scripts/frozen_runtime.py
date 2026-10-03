"""Packaged runtime entry point: retains the private native bootstrap protocol."""

import sys

from edge.runtime.__main__ import main

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        print('{"event":"runtime.failed"}', file=sys.stderr, flush=True)
        raise SystemExit(1) from None
