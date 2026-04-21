"""GUI 骨架级项目会话。"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from datetime import datetime
from enum import StrEnum
from pathlib import Path


class ModuleKey(StrEnum):
    """主模块标识。"""

    PROJECT = "project"
    IMPORT = "import"
    PROCESSING = "processing"
    PLOTTING = "plotting"
    EXPORT = "export"


MODULE_LABELS: dict[ModuleKey, str] = {
    ModuleKey.PROJECT: "项目",
    ModuleKey.IMPORT: "导入",
    ModuleKey.PROCESSING: "处理",
    ModuleKey.PLOTTING: "绘图",
    ModuleKey.EXPORT: "工程导出",
}


@dataclass(slots=True)
class SampleSetSummary:
    """样本集摘要占位。"""

    name: str
    class_name: str
    sample_type: str
    sample_domain: str
    metadata_type: str
    metadata_fields: tuple[str, ...]
    supported_categories: tuple[str, ...]
    storable_categories: tuple[str, ...]
    supported_fields: tuple[str, ...]
    sample_count: int
    loaded_count: int
    unloaded_count: int
    storage_binding: str
    strict: bool
    storage_dirty: bool


@dataclass(slots=True)
class TaskRecord:
    """任务摘要占位。"""

    title: str
    status: str
    progress_text: str
    detail: str


@dataclass(slots=True)
class LogRecord:
    """日志记录占位。"""

    level: str
    logger_name: str
    message: str
    timestamp: str


@dataclass(slots=True)
class ExportRecord:
    """导出记录占位。"""

    name: str
    target: str
    status: str
    timestamp: str


@dataclass(slots=True)
class ReviewRecord:
    """审查记录占位。"""

    title: str
    status: str
    summary: str


@dataclass(slots=True)
class PlotNode:
    """绘图任务树节点占位。"""

    title: str
    children: tuple["PlotNode", ...] = ()


@dataclass(slots=True)
class ProjectSession:
    """项目骨架状态。"""

    project_name: str
    workdir: Path
    export_dir: Path
    note: str
    last_saved: str
    primary_sampleset: SampleSetSummary
    compare_sampleset: SampleSetSummary | None
    other_samplesets: tuple[SampleSetSummary, ...]
    tasks: list[TaskRecord] = field(default_factory=list)
    logs: list[LogRecord] = field(default_factory=list)
    exports: list[ExportRecord] = field(default_factory=list)
    reviews: list[ReviewRecord] = field(default_factory=list)
    plot_tree: tuple[PlotNode, ...] = ()
    current_module: ModuleKey = ModuleKey.PROJECT
    current_selection: str = "当前项目"
    dirty: bool = False
    demo_key: str = "bridge"

    @classmethod
    def build_demo(cls, demo_key: str = "bridge") -> "ProjectSession":
        """构造内存假数据会话。"""

        root = Path.cwd()
        now = datetime(2026, 4, 21, 17, 10, 0).strftime("%Y-%m-%d %H:%M:%S")
        demos = {
            "bridge": cls(
                project_name="桥梁隔振评估骨架项目",
                workdir=root / "demo_projects" / "bridge",
                export_dir=root / "demo_projects" / "bridge" / "exports",
                note="当前为 GUI 骨架占位数据，不接真实导入、处理、绘图和导出链。",
                last_saved=now,
                primary_sampleset=SampleSetSummary(
                    name="主 SampleSet / Bridge-Set-A",
                    class_name="DefaultSampleSet",
                    sample_type="VibrationTestSample",
                    sample_domain="vibration_test",
                    metadata_type="VibrationTestMetadata",
                    metadata_fields=("case", "point", "instr", "dir", "record", "timestamp", "extra"),
                    supported_categories=("accel", "freqspec", "otovl", "zvl"),
                    storable_categories=("accel", "freqspec", "otovl", "zvl"),
                    supported_fields=("accel", "freqspec", "otovl", "zvl", "alias", "metadata"),
                    sample_count=48,
                    loaded_count=16,
                    unloaded_count=32,
                    storage_binding="SET_SQLITE_H5 / read_write",
                    strict=True,
                    storage_dirty=False,
                ),
                compare_sampleset=SampleSetSummary(
                    name="对比 SampleSet / Bridge-Set-B",
                    class_name="DefaultSampleSet",
                    sample_type="VibrationTestSample",
                    sample_domain="vibration_test",
                    metadata_type="VibrationTestMetadata",
                    metadata_fields=("case", "point", "instr", "dir", "record", "timestamp", "extra"),
                    supported_categories=("accel", "freqspec", "otovl", "zvl"),
                    storable_categories=("accel", "freqspec", "otovl", "zvl"),
                    supported_fields=("accel", "freqspec", "otovl", "zvl", "alias", "metadata"),
                    sample_count=36,
                    loaded_count=12,
                    unloaded_count=24,
                    storage_binding="SET_H5 / read_only",
                    strict=True,
                    storage_dirty=False,
                ),
                other_samplesets=(
                    SampleSetSummary(
                        name="临时子集 / C1-C4",
                        class_name="DefaultSampleSet",
                        sample_type="VibrationTestSample",
                        sample_domain="vibration_test",
                        metadata_type="VibrationTestMetadata",
                        metadata_fields=("case", "point", "instr", "dir", "record", "timestamp"),
                        supported_categories=("accel", "freqspec", "otovl", "zvl"),
                        storable_categories=("accel", "freqspec", "otovl", "zvl"),
                        supported_fields=("accel", "freqspec", "otovl", "zvl"),
                        sample_count=8,
                        loaded_count=8,
                        unloaded_count=0,
                        storage_binding="视图 / read_only",
                        strict=False,
                        storage_dirty=False,
                    ),
                ),
                tasks=[
                    TaskRecord("导入 CSV 样本", "已完成", "12 / 12", "已生成新的主样本集占位。"),
                    TaskRecord("批量计算 ZVL", "运行中", "18 / 48", "结果和进度均为占位数据。"),
                ],
                logs=[
                    LogRecord("INFO", "gui.session", "已加载桥梁隔振评估骨架项目。", now),
                    LogRecord("WARNING", "gui.import", "单位检测尚未接入真实解析链。", now),
                    LogRecord("INFO", "gui.processing", "当前显示的是占位处理结果。", now),
                ],
                exports=[
                    ExportRecord("工程导出占位", "demo_projects/bridge/exports/package_a", "成功", now),
                    ExportRecord("图组导出占位", "demo_projects/bridge/exports/plots", "待执行", now),
                ],
                reviews=[
                    ReviewRecord("GUI 骨架设计审查", "通过", "模块边界、dock 结构和按钮归属已固定。"),
                    ReviewRecord("真实业务接入审查", "待办", "第二轮再接 import/process/plot/export facade。"),
                ],
                plot_tree=(
                    PlotNode(
                        "图组 A / 基础评估",
                        children=(
                            PlotNode("图 1 / 时程"),
                            PlotNode("图 2 / 频谱"),
                            PlotNode("图 3 / OTOVL"),
                        ),
                    ),
                    PlotNode(
                        "图组 B / 报告配图",
                        children=(
                            PlotNode("图 1 / 标量摘要"),
                            PlotNode("图 2 / 对比图"),
                        ),
                    ),
                ),
                demo_key="bridge",
            ),
            "generic": cls(
                project_name="通用样本项目骨架",
                workdir=root / "demo_projects" / "generic",
                export_dir=root / "demo_projects" / "generic" / "exports",
                note="展示 default domain 的通用 metadata/type 占位。",
                last_saved=now,
                primary_sampleset=SampleSetSummary(
                    name="主 SampleSet / Generic-Set",
                    class_name="DefaultSampleSet",
                    sample_type="Sample",
                    sample_domain="default",
                    metadata_type="Metadata",
                    metadata_fields=("identity", "attributes", "extra"),
                    supported_categories=("accel", "freqspec"),
                    storable_categories=("accel", "freqspec"),
                    supported_fields=("accel", "freqspec", "metadata", "alias"),
                    sample_count=12,
                    loaded_count=4,
                    unloaded_count=8,
                    storage_binding="SET_DIR / read_write",
                    strict=True,
                    storage_dirty=True,
                ),
                compare_sampleset=None,
                other_samplesets=(),
                tasks=[TaskRecord("SampleSet 切换", "已完成", "1 / 1", "已切换到通用样本项目占位。")],
                logs=[LogRecord("INFO", "gui.session", "已切换到通用样本项目占位。", now)],
                exports=[ExportRecord("空导出记录", "-", "未执行", now)],
                reviews=[ReviewRecord("骨架一致性检查", "通过", "多 domain 占位切换正常。")],
                plot_tree=(PlotNode("图组 A / 空占位", children=(PlotNode("图 1 / 待绑定"),)),),
                demo_key="generic",
            ),
        }
        return demos[demo_key]

    def switch_demo(self, demo_key: str) -> None:
        """切换假数据集。"""

        replacement = self.build_demo(demo_key)
        for item in fields(type(self)):
            setattr(self, item.name, getattr(replacement, item.name))

    def set_current_module(self, module: ModuleKey) -> None:
        """切换当前模块。"""

        self.current_module = module

    def set_current_selection(self, selection: str) -> None:
        """更新当前选中对象。"""

        self.current_selection = selection

    def toggle_dirty(self) -> None:
        """切换脏状态。"""

        self.dirty = not self.dirty

    def mark_saved(self, timestamp: str | None = None) -> None:
        """更新保存状态。"""

        self.last_saved = timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.dirty = False
