"""样本存储策略实现。"""

from __future__ import annotations

import json
import shutil
from typing import TYPE_CHECKING, Any

import h5py
import numpy as np
import pandas as pd

from .sample_storage_strategy_base import _StorageReadSession, _StorageStrategy, _StorageWriteSession
from .sample_storage_sqlite_h5_strategy import _SetSqliteH5Strategy
from .storage_constants import (
    DATA_NPZ_FILENAME,
    H5_ATTR_ALIAS,
    H5_ATTR_METADATA_JSON,
    H5_ATTR_UID,
    H5_ATTR_UNIT,
    META_COL_ALIAS,
    META_COL_METADATA_JSON,
    META_COL_NAME,
    META_COL_UID,
    METADATA_JSON_FILENAME,
)
from ..storage.types import AttrDataFormat, ContainerFormat, StorageScheme

if TYPE_CHECKING:
    from ..domain.samples.base import SampleBaseModel


class _SampleJsonStrategy(_StorageStrategy):
    def prepare_layout(self) -> None:
        self.ctx.base_dir.mkdir(parents=True, exist_ok=True)

    def uid_name_index(self) -> dict[str, str]:
        index: dict[str, str] = {}
        for file_path in self.ctx.base_dir.glob("*.json"):
            with open(file_path, encoding="utf-8") as f:
                payload = json.load(f)
            uid = payload.get("metadata", {}).get("uid")
            if isinstance(uid, str):
                index[uid] = file_path.stem
        return index

    def save_sample(self, sample: SampleBaseModel, categories: list[str] | None = None) -> None:
        name = self.ctx.resolve_name(sample)
        data_dict = self.ctx.sample_data_dict(sample, categories)
        payload = {
            "alias": sample.alias,
            "metadata": sample.metadata.model_dump(),
            "data": {k: self.ctx.to_jsonable(self.ctx.serialize_container(v)) for k, v in data_dict.items()},
        }
        with open(self.ctx.base_dir / f"{name}.json", "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, default=str)

    def load_sample(
        self,
        uid: str,
        name: str,
        categories: list[str] | None = None,
    ) -> SampleBaseModel:
        with open(self.ctx.base_dir / f"{name}.json", encoding="utf-8") as f:
            payload = json.load(f)
        sample = self.ctx.sampleset.sample_type(metadata=self.ctx.metadata_from_dict(payload["metadata"]))
        sample._restore_alias_internal(payload.get("alias", uid))
        selected_categories = set(self.resolve_load_categories(categories))
        for category, value in payload.get("data", {}).items():
            if category not in selected_categories:
                continue
            sample.update(**{category: self.ctx.deserialize_container(category, value)})
        return sample

    def organize(self, valid_uids: set[str]) -> int:
        removed = 0
        for uid, name in self.uid_name_index().items():
            if uid in valid_uids:
                continue
            file_path = self.ctx.base_dir / f"{name}.json"
            if file_path.exists():
                file_path.unlink()
                removed += 1
        return removed


class _SampleH5Strategy(_StorageStrategy):
    def prepare_layout(self) -> None:
        self.ctx.base_dir.mkdir(parents=True, exist_ok=True)

    def uid_name_index(self) -> dict[str, str]:
        import h5py

        index: dict[str, str] = {}
        for file_path in self.ctx.base_dir.glob("*.h5"):
            if file_path.name == self.ctx.set_filename:
                continue
            try:
                with h5py.File(file_path, "r") as f:
                    uid = f.attrs.get(H5_ATTR_UID)
                    if isinstance(uid, bytes):
                        uid = uid.decode("utf-8")
                    if isinstance(uid, str):
                        index[uid] = file_path.stem
            except Exception:
                continue
        return index

    def _write_payload_group(self, group: Any, payload: dict[str, Any]) -> None:
        units = payload.get("_units", {})
        dataset_options = self.ctx.h5_dataset_options()
        for key, value in payload.items():
            if key == "_units" or value is None:
                continue
            if isinstance(value, dict):
                self._write_payload_group(group.create_group(key), value)
                continue
            arr = np.asarray(value)
            if arr.dtype == object:
                raise TypeError(f"H5 存储暂不支持对象数组字段: {key}")
            effective_dataset_options = {} if arr.shape == () else dataset_options
            dataset = group.create_dataset(key, data=arr, **effective_dataset_options)
            unit = units.get(key, "")
            if unit:
                dataset.attrs[H5_ATTR_UNIT] = unit

    def _write_group(self, group: Any, category: str, data: Any) -> None:
        payload = self.ctx.serialize_container(data)
        cat_grp = group.create_group(category)
        self._write_payload_group(cat_grp, payload)

    def _read_group_payload(self, group: Any) -> dict[str, Any]:
        import h5py

        payload: dict[str, Any] = {}
        units: dict[str, Any] = {}
        for key in group.keys():
            node = group[key]
            if isinstance(node, h5py.Group):
                payload[key] = self._read_group_payload(node)
                continue
            if not isinstance(node, h5py.Dataset):
                continue
            value = node[()]
            if isinstance(value, bytes):
                value = value.decode("utf-8")
            payload[key] = value
            if H5_ATTR_UNIT in node.attrs:
                units[key] = node.attrs[H5_ATTR_UNIT]
        if units:
            payload["_units"] = units
        return payload

    def save_sample(self, sample: SampleBaseModel, categories: list[str] | None = None) -> None:
        import h5py

        name = self.ctx.resolve_name(sample)
        data_dict = self.ctx.sample_data_dict(sample, categories)
        with h5py.File(self.ctx.base_dir / f"{name}.h5", "w") as f:
            f.attrs[H5_ATTR_UID] = sample.uid
            f.attrs[H5_ATTR_ALIAS] = sample.alias
            f.attrs[H5_ATTR_METADATA_JSON] = json.dumps(sample.metadata.model_dump(), ensure_ascii=False, default=str)
            for category, data in data_dict.items():
                self._write_group(f, category, data)

    def load_sample(
        self,
        uid: str,
        name: str,
        categories: list[str] | None = None,
    ) -> SampleBaseModel:
        import h5py

        with h5py.File(self.ctx.base_dir / f"{name}.h5", "r") as f:
            metadata_json = f.attrs.get(H5_ATTR_METADATA_JSON, "{}")
            if isinstance(metadata_json, bytes):
                metadata_json = metadata_json.decode("utf-8")
            sample = self.ctx.sampleset.sample_type(metadata=self.ctx.metadata_from_dict(json.loads(metadata_json)))
            alias = f.attrs.get(H5_ATTR_ALIAS, uid)
            sample._restore_alias_internal(alias.decode("utf-8") if isinstance(alias, bytes) else str(alias))
            selected_categories = set(self.resolve_load_categories(categories))
            for category in f.keys():
                if category not in selected_categories:
                    continue
                group = f[category]
                if not isinstance(group, h5py.Group):
                    continue
                sample.update(**{category: self.ctx.deserialize_container(category, self._read_group_payload(group))})
        return sample

    def load_sample_fields(
        self,
        uid: str,
        name: str,
        categories: list[str],
    ) -> dict[str, object]:
        import h5py

        loaded: dict[str, object] = {}
        if not categories:
            return loaded
        with h5py.File(self.ctx.base_dir / f"{name}.h5", "r") as f:
            for category in self.resolve_load_categories(categories):
                if category not in f:
                    continue
                group = f[category]
                if not isinstance(group, h5py.Group):
                    continue
                loaded[category] = self.ctx.deserialize_container(category, self._read_group_payload(group))
        return loaded

    def sample_presence(
        self,
        uid: str,
        name: str,
    ) -> dict[str, bool]:
        import h5py

        del uid
        path = self.ctx.base_dir / f"{name}.h5"
        if not path.exists():
            return {}
        with h5py.File(path, "r") as f:
            return {
                category: category in f and isinstance(f[category], h5py.Group)
                for category in self.ctx.category_fields()
            }

    def organize(self, valid_uids: set[str]) -> int:
        removed = 0
        for uid, name in self.uid_name_index().items():
            if uid in valid_uids:
                continue
            file_path = self.ctx.base_dir / f"{name}.h5"
            if file_path.exists():
                file_path.unlink()
                removed += 1
        return removed


class _SetH5Strategy(_SampleH5Strategy):
    def uid_name_index(self) -> dict[str, str]:
        import h5py

        index: dict[str, str] = {}
        set_path = self.ctx.set_h5_path()
        if not set_path.exists():
            return index
        with h5py.File(set_path, "r") as f:
            for uid in f.keys():
                index[uid] = uid
        return index

    def save_sample(self, sample: SampleBaseModel, categories: list[str] | None = None) -> None:
        import h5py

        data_dict = self.ctx.sample_data_dict(sample, categories)
        with h5py.File(self.ctx.set_h5_path(), "a") as f:
            if sample.uid in f:
                del f[sample.uid]
            grp = f.create_group(sample.uid)
            grp.attrs[H5_ATTR_ALIAS] = sample.alias
            grp.attrs[H5_ATTR_METADATA_JSON] = json.dumps(sample.metadata.model_dump(), ensure_ascii=False, default=str)
            for category, data in data_dict.items():
                self._write_group(grp, category, data)

    def load_sample(
        self,
        uid: str,
        name: str,
        categories: list[str] | None = None,
    ) -> SampleBaseModel:
        import h5py

        del name
        with h5py.File(self.ctx.set_h5_path(), "r") as f:
            grp = f[uid]
            if not isinstance(grp, h5py.Group):
                raise TypeError(f"set_h5 中 UID 节点不是 Group: {uid}")
            metadata_json = grp.attrs.get(H5_ATTR_METADATA_JSON, "{}")
            if isinstance(metadata_json, bytes):
                metadata_json = metadata_json.decode("utf-8")
            sample = self.ctx.sampleset.sample_type(metadata=self.ctx.metadata_from_dict(json.loads(metadata_json)))
            alias = grp.attrs.get(H5_ATTR_ALIAS, uid)
            sample._restore_alias_internal(alias.decode("utf-8") if isinstance(alias, bytes) else str(alias))
            selected_categories = set(self.resolve_load_categories(categories))
            for category in grp.keys():
                if category not in selected_categories:
                    continue
                cat_grp = grp[category]
                if not isinstance(cat_grp, h5py.Group):
                    continue
                sample.update(**{category: self.ctx.deserialize_container(category, self._read_group_payload(cat_grp))})
        return sample

    def load_sample_fields(
        self,
        uid: str,
        name: str,
        categories: list[str],
    ) -> dict[str, object]:
        import h5py

        del name
        loaded: dict[str, object] = {}
        if not categories:
            return loaded
        with h5py.File(self.ctx.set_h5_path(), "r") as f:
            grp = f[uid]
            if not isinstance(grp, h5py.Group):
                raise TypeError(f"set_h5 中 UID 节点不是 Group: {uid}")
            for category in self.resolve_load_categories(categories):
                if category not in grp:
                    continue
                cat_grp = grp[category]
                if not isinstance(cat_grp, h5py.Group):
                    continue
                loaded[category] = self.ctx.deserialize_container(category, self._read_group_payload(cat_grp))
        return loaded

    def load_many_sample_fields(
        self,
        items: list[tuple[str, str]],
        categories: list[str],
    ) -> dict[str, dict[str, object]]:
        import h5py

        loaded: dict[str, dict[str, object]] = {uid: {} for uid, _ in items}
        if not categories or not items:
            return loaded
        selected = self.resolve_load_categories(categories)
        with h5py.File(self.ctx.set_h5_path(), "r") as f:
            for uid, _ in items:
                if uid not in f:
                    raise FileNotFoundError(f"set_h5 中不存在 UID: {uid}")
                grp = f[uid]
                if not isinstance(grp, h5py.Group):
                    raise TypeError(f"set_h5 中 UID 节点不是 Group: {uid}")
                row: dict[str, object] = {}
                for category in selected:
                    if category not in grp:
                        continue
                    cat_grp = grp[category]
                    if not isinstance(cat_grp, h5py.Group):
                        continue
                    row[category] = self.ctx.deserialize_container(category, self._read_group_payload(cat_grp))
                loaded[uid] = row
        return loaded

    def write_session(self) -> _StorageWriteSession:
        return _SetH5WriteSession(self)

    def read_session(self) -> _StorageReadSession:
        return _SetH5ReadSession(self)

    def sample_presence(
        self,
        uid: str,
        name: str,
    ) -> dict[str, bool]:
        import h5py

        del name
        path = self.ctx.set_h5_path()
        if not path.exists():
            return {}
        with h5py.File(path, "r") as f:
            if uid not in f:
                return {}
            grp = f[uid]
            if not isinstance(grp, h5py.Group):
                return {}
            return {
                category: category in grp and isinstance(grp[category], h5py.Group)
                for category in self.ctx.category_fields()
            }

    def organize(self, valid_uids: set[str]) -> int:
        import h5py

        removed = 0
        set_path = self.ctx.set_h5_path()
        if not set_path.exists():
            return 0
        with h5py.File(set_path, "a") as f:
            for uid in list(f.keys()):
                if uid not in valid_uids:
                    del f[uid]
                    removed += 1
        return removed


class _AttrTableStrategy(_StorageStrategy):
    def prepare_layout(self) -> None:
        self.ctx.base_dir.mkdir(parents=True, exist_ok=True)
        for category in self.ctx.category_fields():
            (self.ctx.base_dir / category).mkdir(parents=True, exist_ok=True)

    def uid_name_index(self) -> dict[str, str]:
        index: dict[str, str] = {}
        df = self.ctx.load_metadata_table()
        if df.empty:
            return index
        for _, row in df.iterrows():
            uid = str(row.get(META_COL_UID, "")).strip()
            name = str(row.get(META_COL_NAME, "")).strip()
            if uid and name:
                index[uid] = name
        return index

    def save_sample(self, sample: SampleBaseModel, categories: list[str] | None = None) -> None:
        name = self.ctx.resolve_name(sample)
        data_dict = self.ctx.sample_data_dict(sample, categories)
        fmt = self.ctx.attr_data_format()
        for category, data in data_dict.items():
            attr_dir = self.ctx.base_dir / category
            attr_dir.mkdir(parents=True, exist_ok=True)
            if fmt is AttrDataFormat.CSV:
                file_path = attr_dir / f"{name}.csv"
                options: dict[str, Any] = {}
                if self.ctx.float_format() is not None:
                    options["float_format"] = self.ctx.float_format()
                data_for_csv = self.ctx.prepare_container_for_csv(category, data)
                self.ctx.data_storage.save(
                    file_path,
                    data_for_csv,
                    fmt=ContainerFormat.CSV,
                    category=category,
                    options=options,
                )
            else:
                file_path = attr_dir / f"{name}.npy"
                data_for_npy = self.ctx.prepare_container_for_csv(category, data)
                self.ctx.data_storage.save(
                    file_path,
                    data_for_npy,
                    fmt=ContainerFormat.NPY,
                    category=category,
                )
        self.ctx.upsert_metadata_table_row(sample, name)

    def load_sample(
        self,
        uid: str,
        name: str,
        categories: list[str] | None = None,
    ) -> SampleBaseModel:
        df = self.ctx.load_metadata_table()
        row = df[df[META_COL_UID] == uid]
        if row.empty:
            raise FileNotFoundError(f"metadata.csv 中不存在 UID: {uid}")
        metadata_json = row.iloc[0][META_COL_METADATA_JSON]
        sample = self.ctx.sampleset.sample_type(metadata=self.ctx.metadata_from_dict(json.loads(str(metadata_json))))
        sample._restore_alias_internal(str(row.iloc[0].get(META_COL_ALIAS, uid)))
        fmt = self.ctx.attr_data_format()
        for category in self.resolve_load_categories(categories):
            if fmt is AttrDataFormat.CSV:
                file_path = self.ctx.base_dir / category / f"{name}.csv"
                if not file_path.exists():
                    continue
                data = self.ctx.data_storage.load(
                    file_path,
                    fmt=ContainerFormat.CSV,
                    category=category,
                    container_type=self.ctx.resolve_field_type(category),
                )
            else:
                file_path = self.ctx.base_dir / category / f"{name}.npy"
                if not file_path.exists():
                    continue
                data = self.ctx.data_storage.load(
                    file_path,
                    fmt=ContainerFormat.NPY,
                    category=category,
                    container_type=self.ctx.resolve_field_type(category),
                )
            sample.update(**{category: data})
        return sample

    def organize(self, valid_uids: set[str]) -> int:
        removed = 0
        for uid, name in self.uid_name_index().items():
            if uid in valid_uids:
                continue
            for category in self.ctx.category_fields():
                for ext in ("csv", "npy"):
                    path = self.ctx.base_dir / category / f"{name}.{ext}"
                    if path.exists():
                        path.unlink()
                        removed += 1
        df = self.ctx.load_metadata_table()
        if not df.empty:
            filtered = df[df[META_COL_UID].isin(list(valid_uids))]
            self.ctx.save_metadata_table(pd.DataFrame(filtered))
        return removed


class _SampleDirStrategy(_StorageStrategy):
    def prepare_layout(self) -> None:
        self.ctx.base_dir.mkdir(parents=True, exist_ok=True)

    def uid_name_index(self) -> dict[str, str]:
        index: dict[str, str] = {}
        for child in self.ctx.base_dir.iterdir():
            if not child.is_dir():
                continue
            metadata_path = child / METADATA_JSON_FILENAME
            if not metadata_path.exists():
                continue
            with open(metadata_path, encoding="utf-8") as f:
                payload = json.load(f)
            metadata_dict = payload.get("metadata", payload)
            uid = metadata_dict.get("uid")
            if isinstance(uid, str):
                index[uid] = child.name
        return index

    def save_sample(self, sample: SampleBaseModel, categories: list[str] | None = None) -> None:
        name = self.ctx.resolve_name(sample)
        sample_dir = self.ctx.base_dir / name
        sample_dir.mkdir(parents=True, exist_ok=True)
        with open(sample_dir / METADATA_JSON_FILENAME, "w", encoding="utf-8") as f:
            json.dump(
                {"alias": sample.alias, "metadata": sample.metadata.model_dump()},
                f,
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        data_pack: dict[str, Any] = {}
        for category, data in self.ctx.sample_data_dict(sample, categories).items():
            data_pack[category] = np.array([self.ctx.serialize_container(data)], dtype=object)
        np.savez_compressed(sample_dir / DATA_NPZ_FILENAME, **data_pack)

    def load_sample(
        self,
        uid: str,
        name: str,
        categories: list[str] | None = None,
    ) -> SampleBaseModel:
        sample_dir = self.ctx.base_dir / name
        with open(sample_dir / METADATA_JSON_FILENAME, encoding="utf-8") as f:
            payload = json.load(f)
        metadata_dict = payload.get("metadata", payload)
        metadata = self.ctx.metadata_from_dict(metadata_dict)
        sample = self.ctx.sampleset.sample_type(metadata=metadata)
        sample._restore_alias_internal(str(payload.get("alias", uid)))
        data_path = sample_dir / DATA_NPZ_FILENAME
        if not data_path.exists():
            return sample
        selected_categories = set(self.resolve_load_categories(categories))
        with np.load(data_path, allow_pickle=True) as npz:
            for category in npz.files:
                if category not in selected_categories:
                    continue
                payload = npz[category].item()
                sample.update(**{category: self.ctx.deserialize_container(category, payload)})
        return sample

    def load_sample_fields(
        self,
        uid: str,
        name: str,
        categories: list[str],
    ) -> dict[str, object]:
        del uid
        sample_dir = self.ctx.base_dir / name
        data_path = sample_dir / DATA_NPZ_FILENAME
        loaded: dict[str, object] = {}
        if not data_path.exists():
            return loaded
        selected_categories = set(self.resolve_load_categories(categories))
        with np.load(data_path, allow_pickle=True) as npz:
            for category in npz.files:
                if category not in selected_categories:
                    continue
                payload = npz[category].item()
                loaded[category] = self.ctx.deserialize_container(category, payload)
        return loaded

    def sample_presence(
        self,
        uid: str,
        name: str,
    ) -> dict[str, bool]:
        del uid
        sample_dir = self.ctx.base_dir / name
        data_path = sample_dir / DATA_NPZ_FILENAME
        if not data_path.exists():
            return {category: False for category in self.ctx.category_fields()}
        with np.load(data_path, allow_pickle=True) as npz:
            files = set(npz.files)
        return {category: category in files for category in self.ctx.category_fields()}

    def organize(self, valid_uids: set[str]) -> int:
        removed = 0
        for uid, name in self.uid_name_index().items():
            if uid in valid_uids:
                continue
            sample_dir = self.ctx.base_dir / name
            if sample_dir.exists() and sample_dir.is_dir():
                shutil.rmtree(sample_dir)
                removed += 1
        return removed


STRATEGY_REGISTRY: dict[StorageScheme, type[_StorageStrategy]] = {
    StorageScheme.SAMPLE_JSON: _SampleJsonStrategy,
    StorageScheme.SAMPLE_H5: _SampleH5Strategy,
    StorageScheme.SET_H5: _SetH5Strategy,
    StorageScheme.SET_SQLITE_H5: _SetSqliteH5Strategy,
    StorageScheme.SET_ATTR_TABLE: _AttrTableStrategy,
    StorageScheme.SET_DIR: _SampleDirStrategy,
}


class _SetH5WriteSession(_StorageWriteSession):
    def __init__(self, strategy: _SetH5Strategy) -> None:
        super().__init__(strategy)
        self._strategy = strategy
        self._file: Any | None = None

    def __enter__(self) -> "_SetH5WriteSession":
        import h5py

        self._file = h5py.File(self._strategy.ctx.set_h5_path(), "a")
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        del exc_type, exc, tb
        if self._file is not None:
            self._file.close()
            self._file = None

    def save_sample(self, sample: SampleBaseModel, categories: list[str] | None = None) -> None:
        if self._file is None:
            raise RuntimeError("SET_H5 写入会话尚未打开")
        data_dict = self._strategy.ctx.sample_data_dict(sample, categories)
        if sample.uid in self._file:
            del self._file[sample.uid]
        grp = self._file.create_group(sample.uid)
        grp.attrs[H5_ATTR_ALIAS] = sample.alias
        grp.attrs[H5_ATTR_METADATA_JSON] = json.dumps(sample.metadata.model_dump(), ensure_ascii=False, default=str)
        for category, data in data_dict.items():
            self._strategy._write_group(grp, category, data)


class _SetH5ReadSession(_StorageReadSession):
    def __init__(self, strategy: _SetH5Strategy) -> None:
        super().__init__(strategy)
        self._strategy = strategy
        self._file: Any | None = None

    def __enter__(self) -> "_SetH5ReadSession":
        import h5py

        self._file = h5py.File(self._strategy.ctx.set_h5_path(), "r")
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        del exc_type, exc, tb
        if self._file is not None:
            self._file.close()
            self._file = None

    def load_sample(
        self,
        uid: str,
        name: str,
        categories: list[str] | None = None,
    ) -> SampleBaseModel:
        del name
        if self._file is None:
            raise RuntimeError("SET_H5 读取会话尚未打开")
        grp = self._file[uid]
        if not isinstance(grp, h5py.Group):
            raise TypeError(f"set_h5 中 UID 节点不是 Group: {uid}")
        metadata_json = grp.attrs.get(H5_ATTR_METADATA_JSON, "{}")
        if isinstance(metadata_json, bytes):
            metadata_json = metadata_json.decode("utf-8")
        sample = self._strategy.ctx.sampleset.sample_type(
            metadata=self._strategy.ctx.metadata_from_dict(json.loads(metadata_json))
        )
        alias = grp.attrs.get(H5_ATTR_ALIAS, uid)
        sample._restore_alias_internal(alias.decode("utf-8") if isinstance(alias, bytes) else str(alias))
        selected_categories = set(self._strategy.resolve_load_categories(categories))
        for category in grp.keys():
            if category not in selected_categories:
                continue
            cat_grp = grp[category]
            if not isinstance(cat_grp, h5py.Group):
                continue
            sample.update(
                **{
                    category: self._strategy.ctx.deserialize_container(
                        category, self._strategy._read_group_payload(cat_grp)
                    )
                }
            )
        return sample

    def load_sample_fields(
        self,
        uid: str,
        name: str,
        categories: list[str],
    ) -> dict[str, object]:
        del name
        loaded: dict[str, object] = {}
        if self._file is None:
            raise RuntimeError("SET_H5 读取会话尚未打开")
        if not categories:
            return loaded
        grp = self._file[uid]
        if not isinstance(grp, h5py.Group):
            raise TypeError(f"set_h5 中 UID 节点不是 Group: {uid}")
        for category in self._strategy.resolve_load_categories(categories):
            if category not in grp:
                continue
            cat_grp = grp[category]
            if not isinstance(cat_grp, h5py.Group):
                continue
            loaded[category] = self._strategy.ctx.deserialize_container(
                category, self._strategy._read_group_payload(cat_grp)
            )
        return loaded

    def sample_presence(
        self,
        uid: str,
        name: str,
    ) -> dict[str, bool]:
        del name
        if self._file is None:
            raise RuntimeError("SET_H5 读取会话尚未打开")
        if uid not in self._file:
            return {}
        grp = self._file[uid]
        if not isinstance(grp, h5py.Group):
            return {}
        return {
            category: category in grp and isinstance(grp[category], h5py.Group)
            for category in self._strategy.ctx.category_fields()
        }


__all__ = [
    "_SampleJsonStrategy",
    "_SampleH5Strategy",
    "_SetH5Strategy",
    "_SetSqliteH5Strategy",
    "_AttrTableStrategy",
    "_SampleDirStrategy",
    "STRATEGY_REGISTRY",
]
