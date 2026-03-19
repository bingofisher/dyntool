"""检查资源清单、canonical 资源路径和重复副本。"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESOURCES_ROOT = PROJECT_ROOT / "src" / "dyntool" / "resources"
MANIFEST_PATH = RESOURCES_ROOT / "manifest.json"


def _load_manifest() -> dict[str, str]:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("manifest.json 必须是 JSON object")
    return {str(key): str(value) for key, value in payload.items()}


def main() -> int:
    violations: list[str] = []
    manifest = _load_manifest()
    referenced_paths: set[Path] = set()

    for key, rel in manifest.items():
        path = (RESOURCES_ROOT / rel).resolve()
        if not path.exists():
            violations.append(f"manifest key {key!r}: missing resource {rel}")
            continue
        if RESOURCES_ROOT.resolve() not in path.parents:
            violations.append(f"manifest key {key!r}: resource escapes resources root: {rel}")
            continue
        referenced_paths.add(path)

    csv_files = sorted(path.resolve() for path in RESOURCES_ROOT.rglob("*.csv"))
    by_name: dict[str, list[Path]] = defaultdict(list)
    for path in csv_files:
        by_name[path.name].append(path)
        if path not in referenced_paths:
            violations.append(f"unreferenced resource file: {path.relative_to(PROJECT_ROOT).as_posix()}")

    for name, paths in sorted(by_name.items()):
        unreferenced = [path for path in paths if path not in referenced_paths]
        if len(paths) > 1 and unreferenced:
            joined = ", ".join(path.relative_to(PROJECT_ROOT).as_posix() for path in paths)
            violations.append(f"duplicate resource basename {name!r}: {joined}")

    if violations:
        print("Resource consistency check failed:")
        for item in violations:
            print(f"  - {item}")
        return 1

    print("Resource consistency check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
