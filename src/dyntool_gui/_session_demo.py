"""GUI 演示会话构造器。"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from dyntool_gui._session_types import (
    ExportRecord,
    FilterSpec,
    ImportKind,
    ImportState,
    ImportStep,
    IssueRecord,
    LogRecord,
    MetadataFilterClause,
    ModuleKey,
    PlotNode,
    PlotRecord,
    PlotState,
    ProcessingState,
    ReviewRecord,
    SampleSetSummary,
    ScopeSelection,
    SubsetDefinition,
    SubsetState,
    TaskRecord,
)

if TYPE_CHECKING:
    from dyntool_gui.session import ProjectSession
    from dyntool_gui.session_bus import SessionBus


def build_demo(session_cls: type, demo_key: str = "bridge", *, bus: "SessionBus | None" = None) -> "ProjectSession":
    """构造演示会话。"""

    root = Path.cwd()
    now = "2026-04-21 17:10:00"
    if demo_key == "generic":
        return session_cls(
            bus=bus,
            project_name="通用样本项目骨架",
            workdir=root / "demo_projects" / "generic",
            export_dir=root / "demo_projects" / "generic" / "exports",
            note="展示 default domain 的通用样本演示数据。",
            last_saved=now,
            primary_sampleset=SampleSetSummary(
                name="主样本集 / Generic-Set",
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
            tasks=[TaskRecord("样本集切换", "已完成", "1 / 1", "已切换到通用样本演示项目。")],
            logs=[LogRecord("INFO", "gui.session", "已切换到通用样本演示项目。", now)],
            issues=[IssueRecord("待接入", "真实导入", "请先选择项目目录后执行导入。")],
            exports=[ExportRecord("空导出记录", "-", "未执行", now)],
            reviews=[ReviewRecord("界面一致性检查", "通过", "多 domain 演示切换正常。")],
            plot_tree=(PlotNode("图组 A / 演示记录", children=(PlotNode("图 1 / 待渲染"),)),),
            plot_records=[
                PlotRecord(
                    id="plot.generic.placeholder",
                    title="图形记录 / 待渲染",
                    plot_mode="single_sample",
                    source_name="accel",
                    sample_count=1,
                    saved_path="",
                    created_at=now,
                )
            ],
            recent_import_lines=("最近导入：无",),
            demo_key="generic",
            subset_state=SubsetState(
                subsets=(
                    SubsetDefinition(
                        id="subset.generic.demo",
                        name="演示子样本集 / 前 3 个样本",
                        filter_spec=FilterSpec(keyword="sample_1,sample_2,sample_3"),
                        resolved_uids=("sample_1", "sample_2", "sample_3"),
                        sample_count=3,
                        created_at=now,
                        updated_at=now,
                        note="演示用子样本集。",
                    ),
                ),
                last_message="已加载演示子样本集定义。",
            ),
            import_state=ImportState(
                import_kind=ImportKind.SAMPLE_SET,
                current_step=ImportStep.EXECUTE_IMPORT,
                project_directory_selected=True,
                source_path=root / "demo_projects" / "generic",
                preview_lines=(
                    "来源路径：demo_projects/generic",
                    "识别存储方式：SET_DIR",
                    "仓库检查：通过",
                    "样本数量：12",
                ),
                unit_lines=("默认只执行轻量检查。",),
                parameter_lines=("存储方式：SET_DIR", "加载方式：按需加载（LAZY）"),
                available_series_categories=("accel",),
                metadata_mode_text="generic_metadata",
                detected_scheme="SET_DIR",
                last_success="已从 generic 仓库加载当前主集。",
                can_execute=True,
            ),
            processing_state=ProcessingState(
                current_action="calc_freqspec",
                last_message="演示数据：暂无真实处理结果。",
            ),
            plot_state=PlotState(
                source_name="accel",
                last_message="演示数据：请点击渲染查看图形。",
            ),
            current_scope=ScopeSelection(scope_kind="all_samples"),
        )

    return session_cls(
        bus=bus,
        project_name="桥梁隔振评估骨架项目",
        workdir=root / "demo_projects" / "bridge",
        export_dir=root / "demo_projects" / "bridge" / "exports",
        note="当前为 GUI 演示数据，可用于体验导入、处理、绘图和导出工作流。",
        last_saved=now,
        primary_sampleset=SampleSetSummary(
            name="主样本集 / Bridge-Set-A",
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
            name="对比样本集 / Bridge-Set-B",
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
                name="附属样本集 / C1-C4",
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
            TaskRecord("样本集仓库导入", "已完成", "1 / 1", "已载入桥梁项目的演示主集。"),
            TaskRecord("主集摘要刷新", "已完成", "1 / 1", "演示界面的主集摘要已同步刷新。"),
        ],
        logs=[
            LogRecord("INFO", "gui.session", "已加载桥梁隔振评估骨架项目。", now),
            LogRecord("INFO", "gui.import", "数据接入页当前显示的是演示主集。", now),
            LogRecord("INFO", "gui.project", "可直接切换到数据接入页测试真实仓库接入。", now),
        ],
        issues=[
            IssueRecord("待接入", "真实业务 I/O", "本轮之前仅提供骨架界面。"),
            IssueRecord("待执行", "导出闭环", "建议继续验证图形保存与结果导出闭环。"),
        ],
        exports=[
            ExportRecord("导出记录 / 结果汇总", "demo_projects/bridge/exports/package_a", "成功", now),
            ExportRecord("导出记录 / 图组导出", "demo_projects/bridge/exports/plots", "待执行", now),
        ],
        reviews=[
            ReviewRecord("GUI 骨架设计审查", "通过", "模块边界、dock 结构和按钮归属已固定。"),
            ReviewRecord("真实业务接入审查", "待办", "第二轮优先实现项目导入完整流程。"),
        ],
        plot_tree=(
            PlotNode("图组 A / 基础评估", children=(PlotNode("图 1 / 时程"), PlotNode("图 2 / 频谱"))),
            PlotNode("图组 B / 报告配图", children=(PlotNode("图 1 / 标量摘要"),)),
        ),
        plot_records=[
            PlotRecord(
                id="plot.bridge.a",
                title="图形记录 / 时程",
                plot_mode="single_sample",
                source_name="accel",
                sample_count=1,
                saved_path="demo_projects/bridge/exports/plots/accel.png",
                created_at=now,
            ),
            PlotRecord(
                id="plot.bridge.b",
                title="图形记录 / 频谱对比",
                plot_mode="multi_sample",
                source_name="freqspec",
                sample_count=2,
                saved_path="demo_projects/bridge/exports/plots/freqspec_compare.png",
                created_at=now,
            ),
        ],
        recent_import_lines=("最近导入：演示样本集", "来源：内存演示仓库"),
        demo_key="bridge",
        subset_state=SubsetState(
            subsets=(
                SubsetDefinition(
                    id="subset.bridge.a",
                    name="工况 A / 桥中点",
                    filter_spec=FilterSpec(
                        metadata_clauses=(
                            MetadataFilterClause(
                                field_name="point",
                                field_kind="categorical",
                                match_mode="values",
                                values=("桥中点",),
                            ),
                        )
                    ),
                    resolved_uids=("SMP_001", "SMP_002", "SMP_003"),
                    sample_count=3,
                    created_at=now,
                    updated_at=now,
                    note="桥中点演示工况。",
                ),
                SubsetDefinition(
                    id="subset.bridge.b",
                    name="工况 B / 支座区",
                    filter_spec=FilterSpec(
                        metadata_clauses=(
                            MetadataFilterClause(
                                field_name="point",
                                field_kind="categorical",
                                match_mode="values",
                                values=("支座",),
                            ),
                        )
                    ),
                    resolved_uids=("SMP_011", "SMP_012"),
                    sample_count=2,
                    created_at=now,
                    updated_at=now,
                    note="支座区演示工况。",
                ),
            ),
            last_message="已加载 2 个演示子样本集。",
        ),
        import_state=ImportState(
            import_kind=ImportKind.SAMPLE_SET,
            current_step=ImportStep.EXECUTE_IMPORT,
            project_directory_selected=True,
            source_path=root / "demo_projects" / "bridge",
            preview_lines=(
                "来源路径：demo_projects/bridge",
                "识别存储方式：SET_SQLITE_H5",
                "仓库检查：通过",
                "样本数量：48",
            ),
            unit_lines=("默认只执行轻量检查。",),
            parameter_lines=(
                "存储方式：SET_SQLITE_H5",
                "加载方式：按需加载（LAZY）",
            ),
            available_series_categories=("accel",),
            metadata_mode_text="vibration_test_metadata",
            detected_scheme="SET_SQLITE_H5",
            last_success="已从 bridge 仓库加载当前主集。",
            can_execute=True,
        ),
        processing_state=ProcessingState(
            current_action="calc_freqspec",
            last_message="演示数据：暂无真实处理结果。",
        ),
        plot_state=PlotState(
            source_name="accel",
            last_message="演示数据：请点击渲染查看图形。",
        ),
        current_scope=ScopeSelection(scope_kind="all_samples"),
        current_module=ModuleKey.PROJECT,
    )
