"""GUI 工作台布局配置。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WorkbenchLayoutProfile:
    """内部工作台布局参数。"""

    is_landscape: bool
    left_dock_min_width: int
    left_dock_max_width: int
    left_dock_target_min: int
    left_dock_target_max: int
    bottom_dock_min_height: int
    bottom_dock_target_min: int
    bottom_dock_target_max: int
    nav_button_height: int
    context_bar_height: int
    page_header_max_height: int
    import_workflow_max_height: int
    import_workflow_max_width: int
    side_panel_max_width: int
    saved_panel_max_width: int
    result_tabs_max_height: int


DEFAULT_WORKBENCH_PROFILE = WorkbenchLayoutProfile(
    is_landscape=False,
    left_dock_min_width=160,
    left_dock_max_width=240,
    left_dock_target_min=170,
    left_dock_target_max=210,
    bottom_dock_min_height=76,
    bottom_dock_target_min=84,
    bottom_dock_target_max=120,
    nav_button_height=36,
    context_bar_height=40,
    page_header_max_height=72,
    import_workflow_max_height=16777215,
    import_workflow_max_width=480,
    side_panel_max_width=380,
    saved_panel_max_width=260,
    result_tabs_max_height=150,
)


LANDSCAPE_2K_PROFILE = WorkbenchLayoutProfile(
    is_landscape=True,
    left_dock_min_width=150,
    left_dock_max_width=420,
    left_dock_target_min=170,
    left_dock_target_max=180,
    bottom_dock_min_height=72,
    bottom_dock_target_min=96,
    bottom_dock_target_max=112,
    nav_button_height=36,
    context_bar_height=40,
    page_header_max_height=72,
    import_workflow_max_height=16777215,
    import_workflow_max_width=520,
    side_panel_max_width=480,
    saved_panel_max_width=420,
    result_tabs_max_height=136,
)


LANDSCAPE_1080P_PROFILE = WorkbenchLayoutProfile(
    is_landscape=True,
    left_dock_min_width=132,
    left_dock_max_width=260,
    left_dock_target_min=145,
    left_dock_target_max=160,
    bottom_dock_min_height=58,
    bottom_dock_target_min=72,
    bottom_dock_target_max=88,
    nav_button_height=32,
    context_bar_height=32,
    page_header_max_height=56,
    import_workflow_max_height=16777215,
    import_workflow_max_width=400,
    side_panel_max_width=340,
    saved_panel_max_width=320,
    result_tabs_max_height=108,
)


def resolve_workbench_layout_profile(width: int, height: int) -> WorkbenchLayoutProfile:
    """按可用尺寸返回工作台布局配置。"""

    ratio = width / max(1, height)
    if width >= 2200 and height >= 1200:
        return LANDSCAPE_2K_PROFILE
    if width >= 1600 and height >= 900 and ratio >= 1.55:
        return LANDSCAPE_1080P_PROFILE
    return DEFAULT_WORKBENCH_PROFILE
