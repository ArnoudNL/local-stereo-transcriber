#!/usr/bin/env python3
"""Generate a macOS .icns icon for Local Stereo Transcriber."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app_logging import setup_logging

logger = setup_logging("generate_app_icon", "generate_app_icon.log")


def make_master_icon(size: int = 1024) -> Image.Image:
    """Create an app icon in the page-logo style with a static blob layout."""
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    # Project palette.
    primary = (55, 91, 107, 255)  # #375b6b
    accent = (10, 126, 164, 255)  # #0a7ea4
    surface = (248, 252, 254, 255)  # #f8fcfe
    soft = (231, 245, 250, 255)  # #e7f5fa

    # Squircle base, similar to macOS app icon geometry.
    pad = int(size * 0.04)
    draw.rounded_rectangle(
        [pad, pad, size - pad, size - pad],
        radius=int(size * 0.20),
        fill=surface,
        outline=soft,
        width=max(4, int(size * 0.008)),
    )

    # Static organic blob background.
    draw.ellipse(
        [int(size * 0.22), int(size * 0.20), int(size * 0.82), int(size * 0.84)],
        fill=(231, 245, 250, 225),
    )
    draw.ellipse(
        [int(size * 0.18), int(size * 0.28), int(size * 0.72), int(size * 0.78)],
        fill=(231, 245, 250, 235),
    )

    # Main document card with uniform rounded corners.
    doc = [int(size * 0.40), int(size * 0.26), int(size * 0.78), int(size * 0.78)]
    stroke_w = max(10, int(size * 0.022))
    draw.rounded_rectangle(
        doc,
        radius=int(size * 0.05),
        fill=surface,
        outline=primary,
        width=stroke_w,
    )

    # Text lines centered inside the document.
    line_w = max(6, int(size * 0.012))
    for y in (
        int(size * 0.43),
        int(size * 0.49),
        int(size * 0.55),
        int(size * 0.61),
    ):
        draw.line(
            [(int(size * 0.50), y), (int(size * 0.70), y)],
            fill=(10, 126, 164, 155),
            width=line_w,
        )
    draw.line(
        [(int(size * 0.50), int(size * 0.67)), (int(size * 0.62), int(size * 0.67))],
        fill=(10, 126, 164, 155),
        width=line_w,
    )

    # Audio stamp overlaid on the document.
    stamp = [int(size * 0.24), int(size * 0.43), int(size * 0.48), int(size * 0.67)]
    draw.rounded_rectangle(
        stamp,
        radius=int(size * 0.05),
        fill=surface,
        outline=primary,
        width=stroke_w,
    )

    bar_w = max(7, int(size * 0.015))
    bars_x = [int(size * 0.31), int(size * 0.36), int(size * 0.41)]
    bars_h = [0.04, 0.07, 0.04]
    center_y = int(size * 0.55)
    for x, h in zip(bars_x, bars_h):
        dh = int(size * h)
        draw.line([(x, center_y - dh), (x, center_y + dh)], fill=accent, width=bar_w)

    return image


def build_iconset(master: Image.Image, iconset_dir: Path) -> None:
    """Create the png files expected by iconutil."""
    iconset_dir.mkdir(parents=True, exist_ok=True)
    mapping = [
        ("icon_16x16.png", 16),
        ("icon_16x16@2x.png", 32),
        ("icon_32x32.png", 32),
        ("icon_32x32@2x.png", 64),
        ("icon_128x128.png", 128),
        ("icon_128x128@2x.png", 256),
        ("icon_256x256.png", 256),
        ("icon_256x256@2x.png", 512),
        ("icon_512x512.png", 512),
        ("icon_512x512@2x.png", 1024),
    ]

    for filename, px in mapping:
        resized = master.resize((px, px), Image.Resampling.LANCZOS)
        resized.save(iconset_dir / filename, format="PNG")


def generate_icns(output_path: Path, preview_png: Path | None = None) -> None:
    if shutil.which("iconutil") is None:
        logger.error("iconutil not found on PATH")
        raise RuntimeError("iconutil is required (macOS only) and was not found.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    master = make_master_icon()
    if preview_png is not None:
        preview_png.parent.mkdir(parents=True, exist_ok=True)
        master.save(preview_png, format="PNG")

    with tempfile.TemporaryDirectory(prefix="iconset_") as tmp_dir:
        iconset_dir = Path(tmp_dir) / "AppIcon.iconset"
        build_iconset(master, iconset_dir)
        subprocess.run(
            ["iconutil", "-c", "icns", str(iconset_dir), "-o", str(output_path)],
            check=True,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate macOS icns app icon")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("assets/AppIcon.icns"),
        help="Output .icns path (default: assets/AppIcon.icns)",
    )
    parser.add_argument(
        "--preview-png",
        type=Path,
        default=Path("assets/AppIcon.png"),
        help="Optional PNG preview path (default: assets/AppIcon.png)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logger.info("Generating app icon: output={} preview={}", args.output, args.preview_png)
    generate_icns(args.output, args.preview_png)
    print(f"Generated icon: {args.output}")
    if args.preview_png:
        print(f"Generated preview: {args.preview_png}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
