"""振动试验样本与样本集。"""

from __future__ import annotations

from typing import Any, ClassVar

import numpy as np
from pydantic import Field

from ..metadata import VibrationTestMetadata
from ..models import (
    AccelSeries,
    DispSeries,
    FDMVLEval,
    FPVDVEval,
    FreqSpec,
    OTOVLEval,
    RespSpec,
    VelSeries,
    ZVLEval,
)
from .base import SampleBase
from .schema import SampleSchema, SampleSlotSpec
from .sets import SampleSetBase


class VibrationTestSample(SampleBase):
    """振动试验样本。"""

    _payload_domain = "vibration_test"

    metadata: VibrationTestMetadata = Field(..., description="样本元数据")
    sample_schema: ClassVar[SampleSchema] = SampleSchema(
        name="vibration_test_sample",
        metadata_type=VibrationTestMetadata,
        slots=(
            SampleSlotSpec(name="accel", model_type=AccelSeries, role="primary"),
            SampleSlotSpec(name="vel", model_type=VelSeries, role="derived"),
            SampleSlotSpec(name="disp", model_type=DispSeries, role="derived"),
            SampleSlotSpec(
                name="freqspec",
                model_type=FreqSpec,
                role="composite",
                include_in_storage=False,
            ),
            SampleSlotSpec(
                name="respspec",
                model_type=RespSpec,
                role="composite",
                include_in_storage=False,
            ),
            SampleSlotSpec(name="zvl", model_type=ZVLEval, role="evaluation"),
            SampleSlotSpec(name="otovl", model_type=OTOVLEval, role="evaluation"),
            SampleSlotSpec(name="fdmvl", model_type=FDMVLEval, role="evaluation"),
            SampleSlotSpec(name="fpvdv", model_type=FPVDVEval, role="evaluation"),
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

    @property
    def zvl(self) -> ZVLEval | None:
        """返回 ZVL 评价结果。"""

        return self.get_data_var("zvl")  # type: ignore[return-value]

    @zvl.setter
    def zvl(self, value: ZVLEval | None) -> None:
        self.set_data_var("zvl", value)

    @property
    def otovl(self) -> OTOVLEval | None:
        """返回 OTOVL 评价结果。"""

        return self.get_data_var("otovl")  # type: ignore[return-value]

    @otovl.setter
    def otovl(self, value: OTOVLEval | None) -> None:
        self.set_data_var("otovl", value)

    @property
    def fdmvl(self) -> FDMVLEval | None:
        """返回 FDMVL 评价结果。"""

        return self.get_data_var("fdmvl")  # type: ignore[return-value]

    @fdmvl.setter
    def fdmvl(self, value: FDMVLEval | None) -> None:
        self.set_data_var("fdmvl", value)

    @property
    def fpvdv(self) -> FPVDVEval | None:
        """返回 FPVDV 评价结果。"""

        return self.get_data_var("fpvdv")  # type: ignore[return-value]

    @fpvdv.setter
    def fpvdv(self, value: FPVDVEval | None) -> None:
        self.set_data_var("fpvdv", value)

    @staticmethod
    def _resolve_overwrite(*, force: bool | None, overwrite: bool | None) -> bool:
        if overwrite is not None:
            return overwrite
        return bool(force)

    def _format_eval_result(self, result: Any) -> str:
        if result is None:
            return "None"
        if hasattr(result, "zvl"):
            try:
                return f"ZVL={float(np.asarray(result.get_field('zvl')).flat[0]):.4f}"
            except Exception:
                pass
        if hasattr(result, "get_field_unit") and hasattr(result, "env"):
            env = getattr(result, "env", None)
            if env is not None:
                arr = np.asarray(env)
                if arr.size > 0:
                    return f"OTOVL Env Max={float(np.max(arr)):.4f}"
        if hasattr(result, "fdmvl"):
            try:
                return f"FDMVL={float(np.asarray(result.get_field('fdmvl')).flat[0]):.4f}"
            except Exception:
                pass
        if hasattr(result, "fpvdv"):
            try:
                return f"FPVDV={float(np.asarray(result.get_field('fpvdv')).flat[0]):.4f}"
            except Exception:
                pass
        if isinstance(result, int | float):
            return f"{result:.4f}"
        try:
            return str(result)
        except Exception:
            return repr(result)

    def _run_accel_action(
        self,
        *,
        attr_name: str,
        overwrite: bool,
        runner,
        success_message: str | None = None,
        use_eval_formatter: bool = False,
    ) -> tuple[bool, str]:
        if self.accel is None:
            return False, "无加速度数据"
        current = getattr(self, attr_name)
        if not overwrite and current is not None:
            if use_eval_formatter:
                return False, f"已存在，跳过 - {self._format_eval_result(current)}"
            return False, f"已存在，跳过 {attr_name}"
        try:
            result = runner()
            setattr(self, attr_name, result)
            if use_eval_formatter:
                return True, self._format_eval_result(result)
            if success_message is not None:
                return True, success_message
            return True, f"{attr_name} 计算完成"
        except Exception as exc:
            return False, f"计算失败: {exc}"

    def calc_vel(
        self,
        force: bool = False,
        *,
        overwrite: bool | None = None,
        **kwargs: Any,
    ) -> tuple[bool, str]:
        """计算速度时程。"""

        return self._run_accel_action(
            attr_name="vel",
            overwrite=self._resolve_overwrite(force=force, overwrite=overwrite),
            runner=lambda: self.accel.calc_vel(**kwargs),  # type: ignore[union-attr]
            success_message="vel 计算完成",
        )

    def calc_disp(
        self,
        force: bool = False,
        *,
        overwrite: bool | None = None,
        **kwargs: Any,
    ) -> tuple[bool, str]:
        """计算位移时程。"""

        return self._run_accel_action(
            attr_name="disp",
            overwrite=self._resolve_overwrite(force=force, overwrite=overwrite),
            runner=lambda: self.accel.calc_disp(**kwargs),  # type: ignore[union-attr]
            success_message="disp 计算完成",
        )

    def calc_freqspec(
        self,
        force: bool = False,
        *,
        overwrite: bool | None = None,
    ) -> tuple[bool, str]:
        """计算组合频谱。"""

        return self._run_accel_action(
            attr_name="freqspec",
            overwrite=self._resolve_overwrite(force=force, overwrite=overwrite),
            runner=lambda: self.accel.calc_freqspec(),  # type: ignore[union-attr]
            success_message="freqspec 计算完成",
        )

    def calc_respspec(
        self,
        force: bool = False,
        *,
        overwrite: bool | None = None,
        **kwargs: Any,
    ) -> tuple[bool, str]:
        """计算组合反应谱。"""

        return self._run_accel_action(
            attr_name="respspec",
            overwrite=self._resolve_overwrite(force=force, overwrite=overwrite),
            runner=lambda: self.accel.calc_respspec_bundle(**kwargs),  # type: ignore[union-attr]
            success_message="respspec 计算完成",
        )

    def calc_all_derived(
        self,
        force: bool = False,
        *,
        overwrite: bool | None = None,
        **kwargs: Any,
    ) -> dict[str, tuple[bool, str]]:
        """计算全部派生量。"""

        results: dict[str, tuple[bool, str]] = {}
        results["vel"] = self.calc_vel(force=force, overwrite=overwrite, **kwargs)
        results["disp"] = self.calc_disp(force=force, overwrite=overwrite, **kwargs)
        results["freqspec"] = self.calc_freqspec(force=force, overwrite=overwrite)
        results["respspec"] = self.calc_respspec(force=force, overwrite=overwrite, **kwargs)
        return results


class VibrationTestSampleSet(SampleSetBase[VibrationTestSample]):
    """振动试验样本集。"""

    _sample_type = VibrationTestSample
    _payload_domain = "vibration_test"


VibrationTestSample._sample_set_type = VibrationTestSampleSet

__all__ = ["VibrationTestSample", "VibrationTestSampleSet"]
