"""数值积分与单自由度求解器基础测试。"""

import numpy as np
import pytest

from dyntool.compute.signals import IntegMethod, Integration
from dyntool.compute.solvers import SDOFSolveMethod, SDOFSolver


class TestIntegration:
    """Integration 基本精度与接口。"""

    def test_integ_const_with_dx(self) -> None:
        """常数函数积分：y=1, dx=0.01 -> 积分应为 x。"""
        n = 100
        dx = 0.01
        y = np.ones(n)
        integ = Integration(y, dx=dx)
        result = integ.integ1d(method=IntegMethod.SCIPY_CUMTRAPZ, initial=0.0)
        expected = np.linspace(0, (n - 1) * dx, n)
        np.testing.assert_allclose(result, expected, atol=1e-10)

    def test_integ_linear_with_dx(self) -> None:
        """线性函数 y=x 积分应为 0.5*x^2。"""
        x = np.linspace(0, 1, 101)
        y = x.copy()
        dx = x[1] - x[0]
        integ = Integration(y, dx=dx)
        result = integ.integ1d(method=IntegMethod.SCIPY_CUMTRAPZ, initial=0.0)
        expected = 0.5 * x**2
        np.testing.assert_allclose(result, expected, atol=1e-6)

    def test_integ_requires_x_or_dx(self) -> None:
        with pytest.raises(ValueError, match="积分需要"):
            Integration(np.ones(10))


class TestSDOFSolver:
    """SDOFSolver 输出形状与基本行为。"""

    def test_solve_from_accel_returns_dataframe(self) -> None:
        """solve_from_accel 返回 DataFrame，含预期列。"""
        dt = 0.01
        t = np.arange(0, 2.0, dt)
        accel = np.sin(2 * np.pi * 1.0 * t) * 0.1  # 1 Hz, 0.1g
        periods = np.array([0.5, 1.0, 2.0])
        df = SDOFSolver.solve_from_accel(
            periods=periods,
            accel=accel,
            accel_dt=dt,
            method=SDOFSolveMethod.NIGAM_JENNINGS,
        )
        assert hasattr(df, "columns")
        assert len(df) == len(periods)
        assert any("psa" in c for c in df.columns)
        assert any("periods" in c for c in df.columns)

    def test_sdof_build_and_set_ag(self) -> None:
        """构建 SDOF 并设置加速度后，ag 与 dt 正确。"""
        dt = 0.02
        ag = np.zeros(100)
        solver = SDOFSolver(dt=dt, ag=ag, m=1, xi=0.05, T=1.0)
        np.testing.assert_allclose(solver.ag, ag)
        assert solver.dt == dt
