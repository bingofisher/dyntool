"""主库内部结构收敛回归测试。"""

from __future__ import annotations

from dyntool.domain import compute_api
from dyntool.domain.samples import _sample_set_storage as sample_set_storage_module
from dyntool.infrastructure import sample_set_storage as infrastructure_sample_set_storage
from dyntool.plotting import _axes_helpers as axes_helpers


def test_compute_api_uses_aggregated_internal_resolvers() -> None:
    assert hasattr(compute_api, "_ComputeSourceResolver")
    assert not hasattr(compute_api, "_ComputeOperationCatalog")
    for name in (
        "_normalize_source",
        "_time_series_slots",
        "_resolve_sample_source",
        "_resolve_sample_timeseries",
        "_model_available_operations",
    ):
        assert not hasattr(compute_api, name)
    for name in (
        "_ModelProcessNamespace",
        "_ModelDeriveNamespace",
        "_ModelSpectrumNamespace",
        "_ModelResponseNamespace",
        "_ModelEvaluateNamespace",
        "_ModelFeatureNamespace",
        "_SampleProcessNamespace",
        "_SampleSpectrumNamespace",
        "_SampleResponseNamespace",
        "_SampleEvaluateNamespace",
        "_SampleFeatureNamespace",
        "_SamplePlanNamespace",
        "_SampleSetProcessNamespace",
        "_SampleSetSpectrumNamespace",
        "_SampleSetResponseNamespace",
        "_SampleSetEvaluateNamespace",
        "_SampleSetPlanNamespace",
    ):
        assert not hasattr(compute_api, name)


def test_plotting_axes_module_uses_specific_internal_controllers() -> None:
    assert hasattr(axes_helpers, "_LegendComposer")
    assert hasattr(axes_helpers, "_AxisTickController")
    assert not hasattr(axes_helpers, "LegendHelper")
    assert not hasattr(axes_helpers, "AxisHelper")


def test_sample_set_storage_helpers_are_grouped_into_planners() -> None:
    assert hasattr(sample_set_storage_module, "_SampleSetTransferPlanner")
    for name in (
        "_conversion_fields",
        "_filtered_items",
        "_ensure_conversion_source_ready",
        "_is_full_storage_conversion",
        "_build_transfer_sample",
    ):
        assert not hasattr(sample_set_storage_module, name)


def test_infrastructure_sample_set_storage_uses_internal_coordinators() -> None:
    for name in (
        "_SampleSetStorageCoordinator",
        "_SampleSetProgressPolicy",
    ):
        assert not hasattr(infrastructure_sample_set_storage, name)

    assert hasattr(infrastructure_sample_set_storage.SampleSetStorage, "_selected_items")
    assert hasattr(infrastructure_sample_set_storage.SampleSetStorage, "_load_sample_from_entry")
    assert hasattr(infrastructure_sample_set_storage.SampleSetStorage, "_duplicate_uid_error")
    assert hasattr(infrastructure_sample_set_storage.SampleSetStorage, "_raise_or_collect_load_error")
