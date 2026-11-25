"""建筑振动展示生成器，属于 Private / implementation detail。"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import numpy as np

from dyntool import AccelSeries, DefaultSample, DefaultSampleSet, SampleDomain, UnitSystem, VibrationTestMetadata
from dyntool.storage import StorageScheme, inspect_storage_repository, save_sample_set

from .managers.plot_manager import PlotManager
from .session import (
    AnalysisDataState,
    FilterSpec,
    ImportStep,
    MetadataFilterClause,
    ModuleKey,
    ProjectSession,
)
from .persistence import ProjectFileStore


_SEED = 20261004
_SAMPLE_RATE = 256
_POINTS = 8192
_CASES = ("背景", "交通", "设备隔振前", "设备隔振后")
_FLOORS = (("地下室", 0.6), ("二层室内", 1.0), ("六层室内", 1.4))
_DIRECTIONS = (("X", 0.7), ("Y", 0.8), ("Z", 1.0))
_TIME = "2026-01-01 12:00:00"
_COMPARE_SUBSET = "building.isolation.2f.z"


@dataclass(frozen=True, slots=True)
class BuildingShowcaseResult:
    """已生成的建筑展示项目，属于 GUI Internal API。

    Attributes:
        project_file: 可通过普通打开项目操作读取的 JSON。
        output_dir: 包含原始仓库、分析仓库和导出结果的目录。
    """

    project_file: Path
    output_dir: Path


class _BuildingShowcaseBuilder:
    """聚合确定性数据、预计算、真实子集和项目交付生命周期。"""

    def build(self, output_dir: Path | None) -> BuildingShowcaseResult:
        """在同目录暂存完整结果，全部验证成功后交付。"""

        target = (output_dir or Path.cwd() / "tmp/gui_showcase" / f"building-{uuid4().hex[:8]}").resolve()
        if target.exists() and (not target.is_dir() or any(target.iterdir())):
            raise ValueError("展示项目目标必须是空目录，不能覆盖已有项目。")
        target.parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(prefix=".building-showcase-", dir=target.parent) as temporary:
            staged = Path(temporary) / "project"
            staged.mkdir()
            sample_set = self.make_samples()
            save_sample_set(sample_set, staged / "raw_data", scheme=StorageScheme.SET_SQLITE_H5, strict=True)
            self._export_inputs(sample_set, staged)
            self._calculate(sample_set)
            save_sample_set(sample_set, staged / "analysis_data", scheme=StorageScheme.SET_SQLITE_H5, strict=True)
            for name in ("raw_data", "analysis_data"):
                check = inspect_storage_repository(staged / name, level="deep")
                if not check.is_valid:
                    raise ValueError(f"展示仓库完整性检查失败：{name}，{check}")
            session = self._make_session(sample_set, target)
            self._export_results(session, staged)
            session.mark_saved(_TIME)
            ProjectFileStore().save(session, staged / "building.dyntool.json")
            self._write_manifest(staged, session)
            if target.exists():
                target.rmdir()
            staged.replace(target)
        return BuildingShowcaseResult(target / "building.dyntool.json", target)

    def make_samples(self) -> DefaultSampleSet:
        """以固定种子生成标注为合成的完整 36 样本矩阵。"""

        rng = np.random.default_rng(_SEED)
        time = np.arange(_POINTS, dtype=float) / _SAMPLE_RATE
        samples: list[DefaultSample] = []
        for floor, floor_factor in _FLOORS:
            for direction, direction_factor in _DIRECTIONS:
                background = 0.001 * rng.standard_normal(_POINTS) + 0.003 * np.sin(2 * np.pi * 3 * time)
                envelope = sum(np.exp(-0.5 * ((time - center) / 1.5) ** 2) for center in (6, 16, 26))
                traffic = background + envelope * (
                    0.012 * np.sin(2 * np.pi * 8 * time) + 0.006 * np.sin(2 * np.pi * 16 * time)
                )
                equipment = background + 0.02 * np.sin(2 * np.pi * 25 * time) + 0.008 * np.sin(2 * np.pi * 50 * time)
                signals = (background, traffic, equipment, equipment * 0.35)
                for case, signal in zip(_CASES, signals, strict=True):
                    accel = AccelSeries.from_data(
                        signal * floor_factor * direction_factor,
                        dt=1 / _SAMPLE_RATE,
                        axis_unit="second",
                        data_unit="meter/second**2",
                    )
                    samples.append(
                        DefaultSample.from_models(
                            sample_domain=SampleDomain.VIBRATION_TEST,
                            metadata_cls=VibrationTestMetadata,
                            case=case,
                            point=floor,
                            instr="SIM_ACC",
                            dir=direction,
                            record="展示01",
                            timestamp=_TIME,
                            extra={"synthetic": True, "seed": _SEED, "场景": "建筑室内振动展示"},
                            accel=accel,
                        )
                    )
                    samples[-1].set_alias(f"{floor} / {direction} / {case}")
        return DefaultSampleSet.from_samples(samples, sample_domain=SampleDomain.VIBRATION_TEST)

    def _calculate(self, sample_set: DefaultSampleSet) -> None:
        reports = (
            sample_set.calc_freqspec(strict=True),
            sample_set.calc_respspec(
                strict=True, periods=np.geomspace(0.05, 2.0, 40), output_unit_system=UnitSystem.si()
            ),
            sample_set.eval_zvl(
                strict=True,
                freq_range=(0.5, 80.0),
                time_windows=1.0,
                calc_unit_system=UnitSystem.si(),
                output_unit_system=UnitSystem.si(),
            ),
            sample_set.eval_otovl(
                strict=True,
                freq_range=(0.5, 80.0),
                time_windows=1.0,
                calc_unit_system=UnitSystem.si(),
                output_unit_system=UnitSystem.si(),
            ),
        )
        for report in reports:
            if report.stats.succeeded != len(sample_set) or report.stats.failed:
                raise ValueError(f"展示项目预计算未全部成功：{report}")

    def _make_session(self, sample_set: DefaultSampleSet, target: Path) -> ProjectSession:
        session = ProjectSession.build_empty()
        session.project_name = "建筑室内振动与隔振效果展示"
        session.workdir = target
        session.export_dir = target / "exports"
        session.note = "合成演示数据：36 样本，256 Hz、32 秒；隔振后为前值的 0.35 倍，不作工程合格判定。"
        session.bind_primary_runtime(
            sample_set, name="建筑振动展示 / 36 样本", storage_binding=str(target / "analysis_data")
        )
        session.analysis_data = AnalysisDataState(path=target / "analysis_data", last_saved=_TIME)
        state = session.import_state
        state.project_directory_selected = True
        state.current_step = ImportStep.EXECUTE_IMPORT
        state.source_path = target / "raw_data"
        state.requested_scheme = StorageScheme.SET_SQLITE_H5
        state.detected_scheme = StorageScheme.SET_SQLITE_H5.value
        state.available_series_categories = ("accel",)
        state.last_success = "已生成并验证合成建筑展示项目。"
        state.metadata_mode_text = "VibrationTestMetadata / 合成演示"
        session.issues.clear()
        for index, case in enumerate(_CASES):
            self._add_subset(session, f"building.case.{index}", f"工况 / {case}", {"case": (case,)})
        for index, (floor, _) in enumerate(_FLOORS):
            self._add_subset(session, f"building.floor.{index}", f"楼层 / {floor}", {"point": (floor,)})
        self._add_subset(
            session, _COMPARE_SUBSET, "二层 Z 向隔振前后", {"case": _CASES[2:], "point": ("二层室内",), "dir": ("Z",)}
        )
        session.select_subset_definition(_COMPARE_SUBSET)
        session.set_current_scope("saved_subset", subset_ids=(_COMPARE_SUBSET,))
        session.set_current_module(ModuleKey.PLOTTING)
        return session

    def _add_subset(
        self, session: ProjectSession, identifier: str, name: str, fields: dict[str, tuple[str, ...]]
    ) -> None:
        spec = FilterSpec(
            metadata_clauses=tuple(
                MetadataFilterClause(field_name=field, field_kind="categorical", match_mode="values", values=values)
                for field, values in fields.items()
            )
        )
        session.preview_subset(spec)
        subset = session.save_subset_definition(name=name, subset_id=identifier, note="由合成数据元数据实际筛选。")
        subset.created_at = _TIME
        subset.updated_at = _TIME

    def _export_inputs(self, sample_set: DefaultSampleSet, staged: Path) -> None:
        directory = staged / "raw_csv"
        directory.mkdir()
        for index, sample in enumerate(sample_set.values(), start=1):
            sample.accel.to_csv(
                directory / f"{index:02d}_{sample.metadata.case}_{sample.metadata.point}_{sample.metadata.dir}.csv"
            )

    def _export_results(self, session: ProjectSession, staged: Path) -> None:
        exports = staged / "exports"
        exports.mkdir()
        sample_set = session.primary_runtime
        sample_set.scalar_frame(
            metadata_fields=("case", "point", "dir"), data_vars=("zvl",), features=("rms", "pga"), strict=True
        ).to_csv(exports / "scalar_results.csv", encoding="utf-8-sig", index=False)
        manager = PlotManager(session)
        for source in ("accel", "freqspec", "otovl", "respspec"):
            result = manager.render_sync(plot_mode="multi_sample", source_kind="sample_model", source_name=source)
            manager.save_figure(result.figure, exports / f"{source}_compare.png")
            result.figure.clear()

    def _write_manifest(self, staged: Path, session: ProjectSession) -> None:
        manifest = {
            "synthetic": True,
            "seed": _SEED,
            "sampling_hz": _SAMPLE_RATE,
            "points": _POINTS,
            "nominal_duration_seconds": 32,
            "sample_count": 36,
            "axis_unit": "second",
            "data_unit": "meter/second**2",
            "isolation_scale": 0.35,
            "evaluation": {"freq_range_hz": [0.5, 80.0], "window_seconds": 1.0, "zvl_weight": "wk"},
            "response_periods_seconds": np.geomspace(0.05, 2.0, 40).tolist(),
            "subsets": {item.id: list(item.resolved_uids) for item in session.subset_state.subsets},
            "notice": "合成演示，不是实测数据或建筑物理仿真；无工程合格判定。",
        }
        (staged / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
        )
        (staged / "README.md").write_text(
            "# 建筑室内振动与隔振效果展示\n\n"
            "合成演示数据，不作工程合格判定。打开 building.dyntool.json，进入图形绘制，"
            "选择多样本对比、当前子样本集、二层 Z 向隔振前后，点击渲染。"
            "来源可切换 accel、freqspec、otovl、respspec。\n\n"
            "数据处理已有结果需开启覆盖；先保存分析数据，再保存项目。"
            "raw_data/raw_csv 为原始数据，analysis_data 为可写分析仓库，exports 为实际计算结果。"
            "时间戳为固定演示时间。项目引用使用绝对路径，移动目录后需重新生成项目。\n",
            encoding="utf-8",
            newline="\n",
        )


def build_building_showcase(output_dir: Path | None = None) -> BuildingShowcaseResult:
    """生成完整建筑展示项目，属于 GUI Internal API。

    Args:
        output_dir: 空目标目录；省略时在当前目录 tmp/gui_showcase 下创建新目录。

    Returns:
        已通过仓库检查的项目与输出路径。

    Raises:
        ValueError: 目标非空或预计算、完整性检查失败。
    """

    return _BuildingShowcaseBuilder().build(output_dir)
