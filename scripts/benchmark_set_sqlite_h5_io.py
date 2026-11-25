"""使用固定数据测量核心库保存、读取、部分更新和比较成本。"""

from __future__ import annotations

import argparse
import gc
import json
import tracemalloc
from unittest.mock import patch

import h5py
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

import numpy as np

from dyntool import AccelSeries, DefaultSample, DefaultSampleSet, Metadata
from dyntool.storage import StorageScheme, inspect_storage_repository


def measure(*, samples: int, points: int, repeat: int) -> dict[str, object]:
    """在独立临时仓库中重复测量，不读取用户工程数据。"""
    results: list[dict[str, float]] = []
    for _ in range(repeat):
        tracemalloc.start()
        rng = np.random.default_rng(20261004)
        source = DefaultSampleSet()
        for index in range(samples):
            sample = DefaultSample(
                metadata=Metadata(extra={"index": index}),
                accel=AccelSeries.from_data(rng.normal(size=points), dt=0.002),
            )
            source[sample.uid] = sample
        with TemporaryDirectory(prefix="advdyntool-benchmark-") as directory:
            path = Path(directory) / "store"
            start = perf_counter()
            source.save(path, storage_scheme=StorageScheme.SET_SQLITE_H5)
            saved = perf_counter()
            loaded = DefaultSampleSet()
            loaded.load(path, storage_scheme=StorageScheme.SET_SQLITE_H5)
            read = perf_counter()
            summary_reads = 0
            original = h5py.Dataset.__getitem__

            def counted(dataset, key):
                nonlocal summary_reads
                summary_reads += 1
                return original(dataset, key)

            with patch.object(h5py.Dataset, "__getitem__", counted):
                loaded.scalar_frame(features=["pga"])
            summary = perf_counter()
            source.save(path, storage_scheme=StorageScheme.SET_SQLITE_H5, categories=["accel"])
            updated = perf_counter()
            source.compare_with(loaded, features=["pga"])
            compared = perf_counter()
            uids = list(loaded)[: max(1, samples // 2)]
            loaded.find(uids=uids)
            loaded.count(uids=uids)
            queried = perf_counter()
            loaded.load_many(uids=uids, categories=["accel"])
            arrays_read = perf_counter()
            loaded.find(uids=list(loaded)[: min(20, samples)]).series_frame("accel", strict=False)
            series = perf_counter()
            deep_reads = 0

            def counted_deep(dataset, key):
                nonlocal deep_reads
                deep_reads += 1
                return original(dataset, key)

            with patch.object(h5py.Dataset, "__getitem__", counted_deep):
                report = inspect_storage_repository(path, level="deep")
            if not report.is_valid:
                raise RuntimeError(f"合成基准仓库检查失败：{report.issues}")
            inspected = perf_counter()
            _, peak_bytes = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            results.append(
                {
                    "save_seconds": saved - start,
                    "read_seconds": read - saved,
                    "summary_seconds": summary - read,
                    "partial_update_seconds": updated - summary,
                    "compare_seconds": compared - updated,
                    "query_seconds": queried - compared,
                    "payload_read_seconds": arrays_read - queried,
                    "series_seconds": series - arrays_read,
                    "deep_seconds": inspected - series,
                    "deep_array_reads": float(deep_reads),
                    "peak_memory_bytes": float(peak_bytes),
                    "summary_array_reads": float(summary_reads),
                    "series_members": float(min(20, samples)),
                    "bytes": float(sum(item.stat().st_size for item in path.rglob("*") if item.is_file())),
                }
            )
            print(
                json.dumps(
                    {
                        "progress": "run_complete",
                        "samples": samples,
                        "points": points,
                        "run": len(results),
                        "metrics": results[-1],
                    }
                ),
                flush=True,
            )
            gc.collect()
    return {"seed": 20261004, "samples": samples, "points": points, "repeat": repeat, "runs": results}


def main() -> None:
    """输出可用于修复前后对照的 JSON 记录。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=20)
    parser.add_argument("--points", type=int, default=2000)
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--matrix", action="store_true", help="测量 20/200/1000 × 2000 和 36 × 8192 点")
    parser.add_argument("--output", type=Path, default=Path(".pytest_tmp/core-benchmark.json"))
    args = parser.parse_args()
    result = (
        {
            "measurements": [
                measure(samples=count, points=points, repeat=args.repeat)
                for count, points in [(20, 2000), (200, 2000), (1000, 2000), (36, 8192)]
            ]
        }
        if args.matrix
        else measure(samples=args.samples, points=args.points, repeat=args.repeat)
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
