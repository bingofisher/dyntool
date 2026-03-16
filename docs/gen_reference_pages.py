"""为 MkDocs 生成自动模块参考页面。"""

from __future__ import annotations

from pathlib import Path

import mkdocs_gen_files

PACKAGE_ROOT = Path("src") / "dyntool"
REFERENCE_ROOT = Path("reference") / "modules"
nav = mkdocs_gen_files.Nav()
SKIPPED_MODULES = {
    PACKAGE_ROOT / "storage" / "runtime.py",
}


def _is_public_module(path: Path) -> bool:
    """判断模块是否应进入自动参考。"""

    if path in SKIPPED_MODULES:
        return False
    parts = path.relative_to(PACKAGE_ROOT).parts
    return all(not part.startswith("_") for part in parts if part != "__init__.py")


for path in sorted(PACKAGE_ROOT.rglob("*.py")):
    if not _is_public_module(path):
        continue

    module_path = path.relative_to("src").with_suffix("")
    parts = tuple(module_path.parts)
    doc_path = path.relative_to(PACKAGE_ROOT).with_suffix(".md")
    full_doc_path = REFERENCE_ROOT / doc_path

    if path.name == "__init__.py":
        parts = tuple(module_path.parts[:-1])
        full_doc_path = REFERENCE_ROOT / path.relative_to(PACKAGE_ROOT).parent / "index.md"

    ident = ".".join(parts)
    nav[parts] = full_doc_path.relative_to("reference").as_posix()

    with mkdocs_gen_files.open(full_doc_path, "w") as fd:
        fd.write(f"# `{ident}`\n\n")
        fd.write(f"::: {ident}\n")

    mkdocs_gen_files.set_edit_path(full_doc_path, path)

with mkdocs_gen_files.open("reference/SUMMARY.md", "w") as nav_file:
    nav_file.write("* [总览](index.md)\n")
    nav_file.writelines(nav.build_literate_nav())
