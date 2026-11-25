"""样本存储策略实现。"""

from __future__ import annotations

import json
import shutil
import warnings
from uuid import uuid4
from zipfile import ZipFile
from typing import TYPE_CHECKING, Any

import h5py
import numpy as np
import pandas as pd

from ._storage_commit import _FileCommit, _StorageConsistencyError, _WriteMarker
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
        _WriteMarker.check(self.ctx.base_dir)
        self.ctx.base_dir.mkdir(parents=True, exist_ok=True)

    def uid_name_index(self) -> dict[str, str]:
        index: dict[str, str] = {}
        for file_path in self.ctx.base_dir.glob("*.json"):
            if file_path.name.startswith(".dyntool-"):
                continue
            with open(file_path, encoding="utf-8") as f:
                payload = json.load(f)
            uid = payload.get("metadata", {}).get("uid")
            if isinstance(uid, str):
                index[uid] = file_path.stem
        return index

    def save_sample(self, sample: SampleBaseModel, categories: list[str] | None = None) -> None:
        if categories == []:
            return
        name = self.ctx.resolve_name(sample)
        plan = self.ctx.write_plan(sample, categories)
        data_dict = plan.data
        target = self.ctx.base_dir / f"{name}.json"
        with self.ctx.write_lock, _FileCommit(self.ctx.base_dir, f"JSON 样本 {sample.uid}") as commit:
            old_data = json.loads(target.read_text(encoding="utf-8")).get("data", {}) if target.exists() else {}
            old_data.update({k: self.ctx.to_jsonable(self.ctx.serialize_container(v)) for k, v in data_dict.items()})
            payload = {"alias": plan.alias, "metadata": plan.metadata, "data": old_data}
            commit.stage(target).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
            )
            commit.commit()

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
            sample._replace_data_var_internal(category, self.ctx.deserialize_container(category, value))
        return sample

    def sample_presence(self, uid: str, name: str) -> dict[str, bool]:
        payload = json.loads((self.ctx.base_dir / f"{name}.json").read_text(encoding="utf-8"))
        return {category: category in payload.get("data", {}) for category in self.ctx.category_fields()}

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
        _WriteMarker.check(self.ctx.base_dir)
        self.ctx.base_dir.mkdir(parents=True, exist_ok=True)

    def uid_name_index(self) -> dict[str, str]:
        import h5py

        index: dict[str, str] = {}
        for file_path in self.ctx.base_dir.glob("*.h5"):
            if file_path.name.startswith(".dyntool-"):
                continue
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
            if key == "_dyntool":
                group.attrs["_dyntool"] = json.dumps(value, ensure_ascii=False)
                continue
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
        if "_dyntool" in group.attrs:
            payload["_dyntool"] = json.loads(str(group.attrs["_dyntool"]))
        return payload

    def save_sample(self, sample: SampleBaseModel, categories: list[str] | None = None) -> None:
        if categories == []:
            return
        name = self.ctx.resolve_name(sample)
        plan = self.ctx.write_plan(sample, categories)
        data_dict = plan.data
        target = self.ctx.base_dir / f"{name}.h5"
        with self.ctx.write_lock, _FileCommit(self.ctx.base_dir, f"H5 样本 {sample.uid}") as commit:
            staged = commit.stage(target, preserve=True)
            with h5py.File(staged, "a" if target.exists() else "w") as f:
                f.attrs[H5_ATTR_UID] = sample.uid
                f.attrs[H5_ATTR_ALIAS] = sample.alias
                f.attrs[H5_ATTR_METADATA_JSON] = json.dumps(plan.metadata, ensure_ascii=False, default=str)
                for category, data in data_dict.items():
                    if category in f:
                        del f[category]
                    self._write_group(f, category, data)
            commit.commit()

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
                sample._replace_data_var_internal(
                    category, self.ctx.deserialize_container(category, self._read_group_payload(group))
                )
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
                if not uid.startswith(".dyntool-"):
                    index[uid] = uid
        return index

    def save_sample(self, sample: SampleBaseModel, categories: list[str] | None = None) -> None:
        if categories == []:
            return
        plan = self.ctx.write_plan(sample, categories)
        data_dict = plan.data
        with self.ctx.write_lock:
            _WriteMarker.check(self.ctx.base_dir)
            marker = _WriteMarker(self.ctx.base_dir, f"集合 H5 样本 {sample.uid}")
            marker.start()
            staged = f".dyntool-stage-{uuid4().hex}"
            backup = f".dyntool-backup-{uuid4().hex}"
            write_error: BaseException | None = None
            try:
                with h5py.File(self.ctx.set_h5_path(), "a") as f:
                    published = False
                    try:
                        grp = f.create_group(staged)
                        if sample.uid in f:
                            previous = f[sample.uid]
                            for category in previous:
                                if category not in data_dict:
                                    grp[category] = previous[category]
                        grp.attrs[H5_ATTR_ALIAS] = sample.alias
                        grp.attrs[H5_ATTR_METADATA_JSON] = json.dumps(plan.metadata, ensure_ascii=False, default=str)
                        for category, data in data_dict.items():
                            self._write_group(grp, category, data)
                        f.flush()
                        if sample.uid in f:
                            f.move(sample.uid, backup)
                        f.move(staged, sample.uid)
                        published = True
                        f.flush()
                    except BaseException as error:
                        write_error = error
                        try:
                            if backup in f:
                                if sample.uid in f:
                                    del f[sample.uid]
                                f.move(backup, sample.uid)
                            elif published and sample.uid in f:
                                del f[sample.uid]
                            if staged in f:
                                del f[staged]
                            f.flush()
                        except BaseException as rollback_error:
                            error.add_note(f"H5 回滚失败：{rollback_error}")
                            raise _StorageConsistencyError("集合 H5 回滚失败，必须停止批次") from error
                    if write_error is None and backup in f:
                        try:
                            del f[backup]
                        except Exception as cleanup_error:
                            warnings.warn(
                                f"样本已提交，旧 H5 group 留待整理：{backup}：{cleanup_error}",
                                RuntimeWarning,
                                stacklevel=2,
                            )
            except _StorageConsistencyError:
                raise
            except BaseException as close_error:
                # 句柄退出失败时无法确认 flush/close 的最终状态，保留标记供只读检查。
                raise _StorageConsistencyError("集合 H5 退出失败，保留中断标记并停止批次") from (
                    write_error or close_error
                )
            try:
                marker.finish()
            except OSError as cleanup_error:
                raise _StorageConsistencyError(
                    "集合 H5 中断标记无法移除，必须停止批次", committed=write_error is None
                ) from (write_error or cleanup_error)
            if write_error is not None:
                raise write_error

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
                sample._replace_data_var_internal(
                    category, self.ctx.deserialize_container(category, self._read_group_payload(cat_grp))
                )
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
        return _StorageWriteSession(self)

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
        _WriteMarker.check(self.ctx.base_dir)
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
        if categories == []:
            return
        name = self.ctx.resolve_name(sample)
        plan = self.ctx.write_plan(sample, categories)
        data_dict = plan.data
        with self.ctx.write_lock, _FileCommit(self.ctx.base_dir, f"属性表样本 {sample.uid}") as commit:
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
                        commit.stage(file_path),
                        data_for_csv,
                        fmt=ContainerFormat.CSV,
                        category=category,
                        options=options,
                    )
                else:
                    file_path = attr_dir / f"{name}.npy"
                    data_for_npy = self.ctx.prepare_container_for_csv(category, data)
                    self.ctx.data_storage.save(
                        commit.stage(file_path),
                        data_for_npy,
                        fmt=ContainerFormat.NPY,
                        category=category,
                    )
            updated = self.ctx.metadata_table_update(sample, name, metadata=plan.metadata)
            updated.to_csv(commit.stage(self.ctx.metadata_table_path()), index=False, encoding="utf-8-sig")
            commit.commit()
            self.ctx._metadata_table_cache = updated

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
            sample._replace_data_var_internal(category, data)
        return sample

    def sample_presence(self, uid: str, name: str) -> dict[str, bool]:
        suffix = ".csv" if self.ctx.attr_data_format() is AttrDataFormat.CSV else ".npy"
        return {
            category: (self.ctx.base_dir / category / f"{name}{suffix}").is_file()
            for category in self.ctx.category_fields()
        }

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
        _WriteMarker.check(self.ctx.base_dir)
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
        if categories == []:
            return
        name = self.ctx.resolve_name(sample)
        sample_dir = self.ctx.base_dir / name
        plan = self.ctx.write_plan(sample, categories)
        data_dict = plan.data
        with self.ctx.write_lock, _FileCommit(self.ctx.base_dir, f"目录样本 {sample.uid}") as commit:
            metadata_path = commit.stage(sample_dir / METADATA_JSON_FILENAME)
            metadata_path.write_text(
                json.dumps({"alias": plan.alias, "metadata": plan.metadata}, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
            target = sample_dir / DATA_NPZ_FILENAME
            staged = commit.stage(target)
            data_pack = {
                category: np.array([self.ctx.serialize_container(data)], dtype=object)
                for category, data in data_dict.items()
            }
            np.savez_compressed(staged, **data_pack)
            # 未选择的 NPZ 项直接复制，不反序列化历史槽位。
            if target.exists():
                with ZipFile(target, "r") as old, ZipFile(staged, "a") as new:
                    for info in old.infolist():
                        if info.filename.removesuffix(".npy") not in data_dict:
                            new.writestr(info, old.read(info.filename))
            commit.commit()

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
                sample._replace_data_var_internal(category, self.ctx.deserialize_container(category, payload))
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
            sample._replace_data_var_internal(
                category,
                self._strategy.ctx.deserialize_container(category, self._strategy._read_group_payload(cat_grp)),
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
