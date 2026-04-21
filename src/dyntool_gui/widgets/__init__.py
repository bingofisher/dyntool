"""GUI 骨架 widgets。"""

from .bottom_panel import BottomPanel
from .dialogs import (
    CodeReviewResultDialog,
    ExportPrecheckDialog,
    FigurePreviewDialog,
    ImportPreviewDialog,
    LogDetailDialog,
    LongTaskProgressDialog,
    PlaceholderDialog,
    ResultPreviewDialog,
    TableDialog,
)
from .info_panel import InformationPanel
from .module_pages import ModuleWorkspace
from .resource_tree import ResourceTreeWidget

__all__ = [
    "BottomPanel",
    "CodeReviewResultDialog",
    "ExportPrecheckDialog",
    "FigurePreviewDialog",
    "ImportPreviewDialog",
    "InformationPanel",
    "LogDetailDialog",
    "LongTaskProgressDialog",
    "ModuleWorkspace",
    "PlaceholderDialog",
    "ResourceTreeWidget",
    "ResultPreviewDialog",
    "TableDialog",
]
