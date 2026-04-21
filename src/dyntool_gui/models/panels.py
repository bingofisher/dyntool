"""右侧信息区与底部表格模型。"""

from __future__ import annotations

from dataclasses import dataclass

from ..session import MODULE_LABELS, ModuleKey, ProjectSession


@dataclass(slots=True)
class PanelSection:
    """信息区段落。"""

    title: str
    lines: tuple[str, ...]


class PanelDataBuilder:
    """面板数据构造器。"""

    def build_info_sections(self, session: ProjectSession) -> list[PanelSection]:
        """构造右侧信息区。"""

        sample_set = session.primary_sampleset
        metadata_fields = "、".join(sample_set.metadata_fields)
        categories = "、".join(sample_set.supported_categories)
        return [
            PanelSection(
                "当前对象",
                (
                    f"模块: {MODULE_LABELS[session.current_module]}",
                    f"选中: {session.current_selection}",
                    f"项目: {session.project_name}",
                ),
            ),
            PanelSection(
                "主 SampleSet 摘要",
                (
                    f"名称: {sample_set.name}",
                    f"类型: {sample_set.class_name} / {sample_set.sample_type}",
                    f"领域: {sample_set.sample_domain}",
                    f"metadata: {sample_set.metadata_type}",
                    f"metadata 字段: {metadata_fields}",
                    f"支持 categories: {categories}",
                ),
            ),
            PanelSection("模块提示", self._module_hints(session.current_module)),
        ]

    def build_bottom_rows(self, session: ProjectSession) -> dict[str, list[tuple[str, ...]]]:
        """构造底部表格数据。"""

        return {
            "任务队列": [(item.title, item.status, item.progress_text, item.detail) for item in session.tasks],
            "运行日志": [(item.timestamp, item.level, item.logger_name, item.message) for item in session.logs],
            "问题列表": [
                ("待接入", "真实业务 I/O", "首轮仅提供骨架界面"),
                ("待接入", "Matplotlib 真实画布", "首轮使用预览占位区"),
            ],
            "导出记录": [(item.timestamp, item.name, item.status, item.target) for item in session.exports],
            "审查结论": [(item.status, item.title, item.summary) for item in session.reviews],
        }

    def _module_hints(self, module: ModuleKey) -> tuple[str, ...]:
        """返回模块提示。"""

        hints = {
            ModuleKey.PROJECT: (
                "聚焦项目本体、主 SampleSet 摘要和工作目录。",
                "对比 SampleSet 与附属对象放在次级区域。",
            ),
            ModuleKey.IMPORT: (
                "区分导入 Sample 与导入 SampleSet。",
                "预览、单位检测和 hook 目前均为占位。",
            ),
            ModuleKey.PROCESSING: (
                "先构建子集，再显示可执行处理入口。",
                "结果预览区固定为 metadata/scalar/series/peaks。",
            ),
            ModuleKey.PLOTTING: (
                "绘图骨架统一，不因图种切换布局。",
                "theme 与 profile 只在参数区作为从属信息显示。",
            ),
            ModuleKey.EXPORT: (
                "工程导出收拢项目摘要、处理结果和图组。",
                "导出预检和输出路径策略为占位展示。",
            ),
        }
        return hints[module]
