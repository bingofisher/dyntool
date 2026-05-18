"""GUI 骨架 widgets。"""

from .bottom_panel import BottomPanel
from .dialogs import (
    CodeReviewResultDialog,
    ExportPrecheckDialog,
    FigurePreviewDialog,
    HelpDialog,
    ImportPreviewDialog,
    LogDetailDialog,
    LongTaskProgressDialog,
    PlaceholderDialog,
    ResultPreviewDialog,
    SettingsDialog,
    TableDialog,
)
from .export_workspace import ExportWorkspace
from .info_panel import InformationPanel
from .import_filter_workspace import ImportFilterWorkspace
from .import_workflow import ImportWorkflowWidget
from .module_pages import ModuleWorkspace
from .page_header import PageHeader
from .plotting_workspace import PlottingWorkspace
from .processing_workspace import ProcessingWorkspace
from .project_overview import ProjectOverviewWidget
from .resource_tree import ResourceTreeWidget
from .step_indicator import StepIndicator
from .subset_workspace import SubsetWorkspace

__all__ = [
    "BottomPanel",
    "CodeReviewResultDialog",
    "ExportPrecheckDialog",
    "ExportWorkspace",
    "FigurePreviewDialog",
    "HelpDialog",
    "ImportPreviewDialog",
    "ImportFilterWorkspace",
    "ImportWorkflowWidget",
    "InformationPanel",
    "LogDetailDialog",
    "LongTaskProgressDialog",
    "ModuleWorkspace",
    "PageHeader",
    "PlaceholderDialog",
    "PlottingWorkspace",
    "ProcessingWorkspace",
    "ProjectOverviewWidget",
    "ResourceTreeWidget",
    "ResultPreviewDialog",
    "SettingsDialog",
    "StepIndicator",
    "SubsetWorkspace",
    "TableDialog",
]
