"""python -m image_studio [IMAGEN] abre el editor; preparar y diagnostico usan la CLI."""

from __future__ import annotations

import sys

from image_studio.cli import main as cli_main


def principal(argv: list[str]) -> int:
    if argv and argv[0] in ("preparar", "diagnostico", "-h", "--help"):
        return cli_main(argv)
    from image_studio.ui import app

    return app.run(argv)


if __name__ == "__main__":
    raise SystemExit(principal(sys.argv[1:]))
