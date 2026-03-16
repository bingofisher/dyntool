"""Numeric conversion helpers used by model classes."""

from __future__ import annotations

from typing import Any

import numpy as np
import xarray as xr

from ..constants import ensure_ndarray


class MagnitudeConversion:
    """Helpers for extracting plain numeric arrays from model payloads."""

    @staticmethod
    def ensure_ndarray(
        x: Any,
        dtype: type[np.floating[Any]] | type[np.integer[Any]] | None = np.float64,
    ) -> np.ndarray:
        """Convert array-like input into a plain ndarray."""

        return ensure_ndarray(x, dtype=dtype)

    @staticmethod
    def to_magnitude(data: Any) -> np.ndarray:
        """Extract numeric values from xarray objects or raw arrays."""

        if isinstance(data, xr.DataArray):
            return ensure_ndarray(data.values, dtype=np.float64)
        if isinstance(data, xr.Dataset):
            raise TypeError("MagnitudeConversion.to_magnitude does not accept Dataset")
        return ensure_ndarray(data, dtype=np.float64)
