"""检查资源清单、canonical 资源路径和资源 CSV 编码规则。"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESOURCES_ROOT = PROJECT_ROOT / "src" / "dyntool" / "resources"
MANIFEST_PATH = RESOURCES_ROOT / "manifest.json"
UTF8_SIG_BOM = b"\xef\xbb\xbf"


def _display_path(path: Path, project_root: Path) -> str:
    try:
        return path.relative_to(project_root).as_posix()
    except ValueError:
        return path.as_posix()


def _load_manifest(manifest_path: Path) -> dict[str, str]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("manifest.json 必须是 JSON object")
    return {str(key): str(value) for key, value in payload.items()}


def _check_resource_csv(path: Path, project_root: Path) -> list[str]:
    violations: list[str] = []
    raw = path.read_bytes()
    display = _display_path(path, project_root)

    if not raw.startswith(UTF8_SIG_BOM):
        violations.append(f"{display}: resource CSV must use UTF-8-SIG")
    try:
        raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        violations.append(f"{display}: not valid UTF-8-SIG ({exc})")
    if b"\r" in raw:
        violations.append(f"{display}: resource CSV must use LF line endings")
    return violations


def main(
    *,
    project_root: Path | None = None,
    resources_root: Path | None = None,
    manifest_path: Path | None = None,
) -> int:
    root = (project_root or PROJECT_ROOT).resolve()
    resolved_resources_root = (resources_root or RESOURCES_ROOT).resolve()
    resolved_manifest_path = (manifest_path or MANIFEST_PATH).resolve()
    violations: list[str] = []
    manifest = _load_manifest(resolved_manifest_path)
    referenced_paths: set[Path] = set()

    for key, rel in manifest.items():
        path = (resolved_resources_root / rel).resolve()
        if not path.exists():
            violations.append(f"manifest key {key!r}: missing resource {rel}")
            continue
        if resolved_resources_root not in path.parents:
            violations.append(f"manifest key {key!r}: resource escapes resources root: {rel}")
            continue
        referenced_paths.add(path)

    csv_files = sorted(path.resolve() for path in resolved_resources_root.rglob("*.csv"))
    by_name: dict[str, list[Path]] = defaultdict(list)
    for path in csv_files:
        by_name[path.name].append(path)
        violations.extend(_check_resource_csv(path, root))
        if path not in referenced_paths:
            violations.append(f"unreferenced resource file: {_display_path(path, root)}")

    for name, paths in sorted(by_name.items()):
        unreferenced = [path for path in paths if path not in referenced_paths]
        if len(paths) > 1 and unreferenced:
            joined = ", ".join(_display_path(path, root) for path in paths)
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
