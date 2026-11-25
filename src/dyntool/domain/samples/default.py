"""通用样本与样本集实现。"""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field

from ..metadata import Metadata
from ..models import (
    AccelSeries,
    DispSeries,
    ForceSeries,
    FreqSpec,
    MomentSeries,
    RespSpec,
    StrainSeries,
    StressSeries,
    VelSeries,
)
from .base import SampleBase
from .schema import SampleSchema, SampleSlotSpec
from .sets import SampleSetBase


class Sample(SampleBase):
    """通用样本。"""

    _payload_domain = "default"
    _payload_category = "DefaultSample"
    metadata: Metadata = Field(..., description="样本元数据")
    sample_schema: ClassVar[SampleSchema] = SampleSchema(
        name="default_sample",
        metadata_type=Metadata,
        slots=(
            SampleSlotSpec(name="accel", model_type=AccelSeries, role="primary"),
            SampleSlotSpec(name="vel", model_type=VelSeries, role="derived"),
            SampleSlotSpec(name="disp", model_type=DispSeries, role="derived"),
            SampleSlotSpec(name="force", model_type=ForceSeries, role="primary"),
            SampleSlotSpec(name="moment", model_type=MomentSeries, role="primary"),
            SampleSlotSpec(name="stress", model_type=StressSeries, role="primary"),
            SampleSlotSpec(name="strain", model_type=StrainSeries, role="primary"),
            SampleSlotSpec(
                name="freqspec",
                model_type=FreqSpec,
                role="composite",
            ),
            SampleSlotSpec(
                name="respspec",
                model_type=RespSpec,
                role="composite",
            ),
        ),
    )

    @property
    def accel(self) -> AccelSeries | None:
        """返回加速度时程。"""

        return self.get_data_var("accel")  # type: ignore[return-value]

    @accel.setter
    def accel(self, value: AccelSeries | None) -> None:
        self.set_data_var("accel", value)

    @property
    def vel(self) -> VelSeries | None:
        """返回速度时程。"""

        return self.get_data_var("vel")  # type: ignore[return-value]

    @vel.setter
    def vel(self, value: VelSeries | None) -> None:
        self.set_data_var("vel", value)

    @property
    def disp(self) -> DispSeries | None:
        """返回位移时程。"""

        return self.get_data_var("disp")  # type: ignore[return-value]

    @disp.setter
    def disp(self, value: DispSeries | None) -> None:
        self.set_data_var("disp", value)

    @property
    def force(self) -> ForceSeries | None:
        """返回力时程。"""
        return self.get_data_var("force")  # type: ignore[return-value]

    @force.setter
    def force(self, value: ForceSeries | None) -> None:
        self.set_data_var("force", value)

    @property
    def moment(self) -> MomentSeries | None:
        """返回力矩时程。"""
        return self.get_data_var("moment")  # type: ignore[return-value]

    @moment.setter
    def moment(self, value: MomentSeries | None) -> None:
        self.set_data_var("moment", value)

    @property
    def stress(self) -> StressSeries | None:
        """返回应力分量时程。"""
        return self.get_data_var("stress")  # type: ignore[return-value]

    @stress.setter
    def stress(self, value: StressSeries | None) -> None:
        self.set_data_var("stress", value)

    @property
    def strain(self) -> StrainSeries | None:
        """返回应变分量时程。"""
        return self.get_data_var("strain")  # type: ignore[return-value]

    @strain.setter
    def strain(self, value: StrainSeries | None) -> None:
        self.set_data_var("strain", value)

    @property
    def freqspec(self) -> FreqSpec | None:
        """返回组合频谱对象。"""

        return self.get_data_var("freqspec")  # type: ignore[return-value]

    @freqspec.setter
    def freqspec(self, value: FreqSpec | None) -> None:
        self.set_data_var("freqspec", value)

    @property
    def respspec(self) -> RespSpec | None:
        """返回组合反应谱对象。"""

        return self.get_data_var("respspec")  # type: ignore[return-value]

    @respspec.setter
    def respspec(self, value: RespSpec | None) -> None:
        self.set_data_var("respspec", value)


class SampleSet(SampleSetBase[Sample]):
    """通用样本集。"""

    _sample_type = Sample
    _payload_domain = "default"
    _payload_category = "DefaultSampleSet"


Sample._sample_set_type = SampleSet

DefaultSample = Sample
DefaultSampleSet = SampleSet

__all__ = ["Sample", "SampleSet", "DefaultSample", "DefaultSampleSet"]
