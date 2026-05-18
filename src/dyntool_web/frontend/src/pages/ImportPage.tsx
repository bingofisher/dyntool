import { DataTable } from "../components/DataTable";
import type { ImportPreview, SessionSnapshot, SubsetFilterState, SubsetRow } from "../types";

type ImportPageProps = {
  sourcePath: string;
  importPreview: ImportPreview | null;
  session: SessionSnapshot | null;
  subsetKeyword: string;
  subsetName: string;
  subsetFilter: SubsetFilterState;
  subsetRows: SubsetRow[];
  subsetTotalText: string;
  onSubsetKeywordChange: (value: string) => void;
  onSubsetNameChange: (value: string) => void;
  onSubsetFilterChange: (patch: Partial<SubsetFilterState>) => void;
  onPreview: () => void;
  onBind: () => void;
  onPreviewSubset: () => void;
  onSaveSubset: () => void;
  onSetScope: () => void;
  onClearSubset: () => void;
};

export const ImportPage = ({
  sourcePath,
  importPreview,
  session,
  subsetKeyword,
  subsetName,
  subsetFilter,
  subsetRows,
  subsetTotalText,
  onSubsetKeywordChange,
  onSubsetNameChange,
  onSubsetFilterChange,
  onPreview,
  onBind,
  onPreviewSubset,
  onSaveSubset,
  onSetScope,
  onClearSubset
}: ImportPageProps) => {
  const metadataFields = session?.primary.metadata_fields ?? [];
  const dataSlots = session?.capability.data_slots ?? [];
  const selectedRawSlots = splitCsv(subsetFilter.rawDataVars);
  const selectedAnalysisSlots = splitCsv(subsetFilter.analysisDataVars);
  return (
  <section className="import-layout">
    <section className="control-card">
      <header className="section-header">
        <strong>导入数据集</strong>
      </header>
      <section className="status-box">
        <strong>当前固定数据源</strong>
        <span>{sourcePath || "未找到默认数据源"}</span>
      </section>
      <div className="button-row">
        <button onClick={onPreview}>检查数据集</button>
        <button onClick={onBind}>绑定为主集</button>
      </div>
      {importPreview ? (
        <section className="status-box">
          <strong>{importPreview.allow_execute ? "检查通过，可绑定" : "检查未通过"}</strong>
          <span>存储：{importPreview.detected_scheme}</span>
          <span>样本数：{importPreview.sample_count}</span>
          <span>metadata：{importPreview.metadata_mode || "-"}</span>
          <span>数据槽：{importPreview.available_series_categories.join(" / ") || "-"}</span>
        </section>
      ) : null}
    </section>
    <section className="result-card">
      <DataTable
        title="数据集检查结果"
        columns={["字段", "值"]}
        rows={
          importPreview
            ? [
                ["存储方案", importPreview.detected_scheme],
                ["样本数量", String(importPreview.sample_count)],
                ["metadata", importPreview.metadata_mode || "-"],
                ["可绑定", importPreview.allow_execute ? "是" : "否"],
                ["数据槽", importPreview.available_series_categories.join(" / ") || "-"]
              ]
            : []
        }
        emptyText="尚未检查数据集"
      />
    </section>
    <section className="control-card">
      <header className="section-header">
        <strong>子集管理</strong>
      </header>
      <section className="status-box">
        <strong>当前范围</strong>
        <span>
          {session?.current_scope.scope_kind ?? "all_samples"} / {session?.current_scope.target || "全部样本"}
        </span>
      </section>
      <div className="filter-grid">
        <label>
          关键词
          <input value={subsetKeyword} onChange={(event) => onSubsetKeywordChange(event.target.value)} placeholder="UID、alias 或 metadata" />
        </label>
        <label>
          metadata 字段
          <select
            value={subsetFilter.metadataField}
            onChange={(event) => onSubsetFilterChange({ metadataField: event.target.value })}
          >
            <option value="">全部 metadata</option>
            {metadataFields.map((field) => (
              <option key={field} value={field}>
                {field}
              </option>
            ))}
          </select>
        </label>
        <label>
          匹配方式
          <select value={subsetFilter.matchMode} onChange={(event) => onSubsetFilterChange({ matchMode: event.target.value })}>
            <option value="contains">包含</option>
            <option value="equals">等于</option>
            <option value="startswith">开头匹配</option>
            <option value="endswith">结尾匹配</option>
          </select>
        </label>
        <label>
          排序字段
          <input value={subsetFilter.sortBy} onChange={(event) => onSubsetFilterChange({ sortBy: event.target.value })} placeholder="uid / alias / case" />
        </label>
        <label>
          分页数量
          <input value={subsetFilter.limit} onChange={(event) => onSubsetFilterChange({ limit: event.target.value })} />
        </label>
        <label>
          分页偏移
          <input value={subsetFilter.offset} onChange={(event) => onSubsetFilterChange({ offset: event.target.value })} />
        </label>
      </div>
      <section className="filter-block">
        <strong>原始数据条件</strong>
        <div className="checkbox-list">
          {dataSlots.length ? (
            dataSlots.map((slot) => (
              <label className="check-row" key={`raw-${slot}`}>
                <input
                  type="checkbox"
                  checked={selectedRawSlots.includes(slot)}
                  onChange={() => onSubsetFilterChange({ rawDataVars: toggleCsvValue(subsetFilter.rawDataVars, slot) })}
                />
                {slot}
              </label>
            ))
          ) : (
            <span className="muted">无可选项</span>
          )}
        </div>
      </section>
      <section className="filter-block">
        <strong>分析结果条件</strong>
        <div className="checkbox-list">
          {dataSlots.length ? (
            dataSlots.map((slot) => (
              <label className="check-row" key={`analysis-${slot}`}>
                <input
                  type="checkbox"
                  checked={selectedAnalysisSlots.includes(slot)}
                  onChange={() =>
                    onSubsetFilterChange({ analysisDataVars: toggleCsvValue(subsetFilter.analysisDataVars, slot) })
                  }
                />
                {slot}
              </label>
            ))
          ) : (
            <span className="muted">无可选项</span>
          )}
        </div>
      </section>
      <div className="filter-grid">
        <label>
          子集名称
          <input value={subsetName} onChange={(event) => onSubsetNameChange(event.target.value)} />
        </label>
      </div>
      <label className="check-row">
        <input type="checkbox" checked={subsetFilter.sortDesc} onChange={(event) => onSubsetFilterChange({ sortDesc: event.target.checked })} />
        降序排序
      </label>
      <div className="button-row">
        <button onClick={onPreviewSubset}>预览命中</button>
        <button onClick={onSaveSubset}>保存为动态子集</button>
        <button onClick={onSetScope}>设为当前范围</button>
        <button className="ghost" onClick={onClearSubset}>
          清空筛选
        </button>
      </div>
      <DataTable
        title="子集命中预览"
        columns={["UID", "Alias", "metadata.case", "metadata.point", "metadata.record", "数据状态"]}
        rows={subsetRows.map((row) => [
          row.uid,
          row.alias,
          row.metadata?.case ?? "",
          row.metadata?.point ?? "",
          row.metadata?.record ?? "",
          Object.entries(row.data_status ?? {})
            .filter(([, enabled]) => enabled)
            .map(([name]) => name)
            .join(" / ")
        ])}
        emptyText="暂无命中，请先预览"
        totalText={subsetTotalText}
      />
    </section>
  </section>
  );
};

const splitCsv = (value: string): string[] =>
  value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);

const toggleCsvValue = (value: string, target: string): string => {
  const values = splitCsv(value);
  if (values.includes(target)) {
    return values.filter((item) => item !== target).join(",");
  }
  return [...values, target].join(",");
};
