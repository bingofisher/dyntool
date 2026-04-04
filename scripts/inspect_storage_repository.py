"""检查样本或样本集存储仓库的结构与完整性。"""

from __future__ import annotations

import argparse
from pathlib import Path

from dyntool.storage import StorageScheme, inspect_storage_repository


def main() -> int:
    """解析参数并输出仓库检查摘要。"""

    parser = argparse.ArgumentParser(description="检查样本或样本集存储仓库的结构与完整性。")
    parser.add_argument("path", type=Path, help="待检查的样本或样本集存储路径。")
    parser.add_argument(
        "--storage-scheme",
        choices=[scheme.value for scheme in StorageScheme],
        default=None,
        help="可选显式 storage_scheme；提供后会额外校验与自动识别结果是否一致。",
    )
    parser.add_argument(
        "--level",
        choices=["quick", "deep"],
        default="quick",
        help="检查层级：quick 仅做结构检查，deep 额外做索引和 payload 一致性检查。",
    )
    args = parser.parse_args()

    requested_scheme = StorageScheme(args.storage_scheme) if args.storage_scheme is not None else None
    report = inspect_storage_repository(
        args.path,
        storage_scheme=requested_scheme,
        level=args.level,
    )

    print(f"path: {report.path}")
    print(f"level: {report.level}")
    print(f"exists: {report.exists}")
    print(f"detected_scheme: {getattr(report.detected_scheme, 'value', None)}")
    print(f"requested_scheme: {getattr(report.requested_scheme, 'value', None)}")
    print(f"is_valid: {report.is_valid}")
    print(f"sample_count: {report.sample_count}")
    if report.warnings:
        print("warnings:")
        for warning in report.warnings:
            print(f"  - {warning}")
    if report.issues:
        print("issues:")
        for issue in report.issues:
            print(f"  - {issue}")
    return 0 if report.is_valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
