"""资源树模型。"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..session import PlotNode, ProjectSession


@dataclass(slots=True)
class ResourceNode:
    """资源树节点。"""

    title: str
    children: list["ResourceNode"] = field(default_factory=list)


class ResourceTreeBuilder:
    """资源树构造器。"""

    def build(self, session: ProjectSession) -> list[ResourceNode]:
        """根据会话构造资源树。"""

        children = [
            ResourceNode(
                "项目本体",
                [
                    ResourceNode(session.project_name),
                    ResourceNode(f"工作目录: {session.workdir}"),
                    ResourceNode(f"默认导出目录: {session.export_dir}"),
                ],
            ),
            ResourceNode(
                "主 SampleSet",
                [
                    ResourceNode(session.primary_sampleset.name),
                    ResourceNode(f"样本数量: {session.primary_sampleset.sample_count}"),
                    ResourceNode(f"类型: {session.primary_sampleset.class_name}"),
                ],
            ),
        ]
        if session.compare_sampleset is not None:
            children.append(
                ResourceNode(
                    "对比 SampleSet",
                    [
                        ResourceNode(session.compare_sampleset.name),
                        ResourceNode(f"样本数量: {session.compare_sampleset.sample_count}"),
                    ],
                )
            )
        if session.other_samplesets:
            children.append(
                ResourceNode(
                    "附属 SampleSet",
                    [ResourceNode(item.name) for item in session.other_samplesets],
                )
            )
        children.extend(
            [
                ResourceNode("绘图任务", [self._convert_plot_node(node) for node in session.plot_tree]),
                ResourceNode("工程导出", [ResourceNode(item.name) for item in session.exports]),
            ]
        )
        return children

    def _convert_plot_node(self, node: PlotNode) -> ResourceNode:
        """转换绘图树节点。"""

        return ResourceNode(
            node.title,
            [self._convert_plot_node(item) for item in node.children],
        )
