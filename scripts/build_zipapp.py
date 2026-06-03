from __future__ import annotations

from pathlib import Path
import zipapp


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src"
DIST = ROOT / "dist"
TARGET = DIST / "keyboard-assistant.pyz"


def main() -> int:
    DIST.mkdir(exist_ok=True)
    if TARGET.exists():
        TARGET.unlink()
    zipapp.create_archive(
        SOURCE,
        target=TARGET,
        main="keyboard_assistant.launcher:main",
        interpreter="/usr/bin/env python",
        compressed=True,
    )
    print(f"Built {TARGET}")
    print(f"Size: {TARGET.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
