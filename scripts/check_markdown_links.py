"""Check relative Markdown links.

The checker is intentionally small and dependency-free so it can run in CI
before installing documentation tooling. It validates local file targets for
inline Markdown links and images, while skipping external URLs and code blocks.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import unquote


LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
SKIP_DIRS = {".git", ".pytest_cache", ".mypy_cache", ".ruff_cache", "__pycache__"}
EXTERNAL_PREFIXES = (
    "http://",
    "https://",
    "mailto:",
    "tel:",
    "ftp://",
)


def iter_markdown_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*.md"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        files.append(path)
    return sorted(files)


def clean_target(raw_target: str) -> str:
    target = raw_target.strip()
    if not target:
        return target
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1].strip()
    target = target.split()[0]
    return unquote(target)


def is_external(target: str) -> bool:
    lower = target.lower()
    return lower.startswith(EXTERNAL_PREFIXES)


def check_file(path: Path, root: Path) -> list[str]:
    errors: list[str] = []
    in_fence = False
    fence_marker = ""

    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            marker = stripped[:3]
            if not in_fence:
                in_fence = True
                fence_marker = marker
            elif marker == fence_marker:
                in_fence = False
                fence_marker = ""
            continue
        if in_fence:
            continue

        for match in LINK_RE.finditer(line):
            target = clean_target(match.group(1))
            if not target or is_external(target) or target.startswith("#"):
                continue

            target_no_anchor = target.split("#", 1)[0]
            if not target_no_anchor:
                continue
            if target_no_anchor.startswith("/"):
                # Repository-root absolute links are not used in docs, but skip
                # them rather than guessing the hosting context.
                continue

            target_path = (path.parent / target_no_anchor).resolve()
            try:
                target_path.relative_to(root.resolve())
            except ValueError:
                errors.append(f"{path}:{lineno}: link escapes repository: {target}")
                continue

            if not target_path.exists():
                errors.append(f"{path}:{lineno}: missing target: {target}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Check relative Markdown links")
    parser.add_argument(
        "root",
        nargs="?",
        default=".",
        help="Repository root to scan (default: current directory)",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    errors: list[str] = []
    for path in iter_markdown_files(root):
        errors.extend(check_file(path, root))

    if errors:
        print("Markdown link check failed:")
        for error in errors:
            print(f"  {error}")
        return 1

    print("Markdown link check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
