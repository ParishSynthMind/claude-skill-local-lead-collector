#!/usr/bin/env python3
"""Zip the Skill for upload to claude.ai (Customize > Skills).

The zip holds the skill folder at its root, as claude.ai expects:
  local-lead-collector.zip
    local-lead-collector/SKILL.md
    local-lead-collector/scripts/...
    local-lead-collector/references/...
"""
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "local-lead-collector"
SKIP = {"__pycache__", ".DS_Store"}


def build(out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(SKILL.rglob("*")):
            if path.is_file() and not (set(path.parts) & SKIP) and path.suffix != ".pyc":
                zf.write(path, path.relative_to(ROOT).as_posix())
    return out


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "dist" / "local-lead-collector.zip"
    print(build(target))
