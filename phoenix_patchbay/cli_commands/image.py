"""``patchbay image``: generate one image through the configured image provider."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from phoenix_patchbay.cli import imagegen


def cmd_image(args: list[str]) -> None:
    parser = argparse.ArgumentParser(
        prog="patchbay image",
        description="Generate an image with the provider set by IMAGEGEN_BASE_URL and /settings.",
    )
    parser.add_argument("prompt", nargs="+")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--model", default="", help="defaults to IMAGEGEN_MODEL")
    parser.add_argument("--size", default="", help="e.g. 1024x1024; provider default if omitted")
    parser.add_argument("--overwrite", action="store_true")
    rest = args[args.index("image") + 1 :] if "image" in args else args
    opts = parser.parse_args([a for a in rest if a not in ("-v", "--verbose")])
    try:
        path = imagegen.generate(
            " ".join(opts.prompt),
            opts.out,
            model=opts.model,
            size=opts.size,
            overwrite=opts.overwrite,
        )
    except RuntimeError as exc:
        print(f"patchbay image: {exc}", file=sys.stderr)
        sys.exit(1)
    print(path)
