import { DataTable } from "../components/DataTable";
import type { ExportPrecheck, PlotPayload, SessionSnapshot } from "../types";

type PlotPageProps = {
  session: SessionSnapshot | null;
  sourceName: string;
  outputPath: string;
  plot: PlotPayload | null;
  exportPrecheck: ExportPrecheck | null;
  hasPrimary: boolean;
  onSourceNameChange: (value: string) => void;
  onOutputPathChange: (value: string) => void;
  onRender: () => void;
  onSave: () => void;
  onOpenLargePreview: () => void;
  onOpenThemeEditor: () => void;
  onPrecheckExport: () => void;
};

export const PlotPage = ({
  session,
  sourceName,
  outputPath,
  plot,
  exportPrecheck,
  hasPrimary,
  onSourceNameChange,
  onOutputPathChange,
  onRender,
  onSave,
  onOpenLargePreview,
  onOpenThemeEditor,
  onPrecheckExport
}: PlotPageProps) => (
  <section className="workbench-layout">
    <aside className="control-card narrow">
      <header className="section-header">
        <strong>图形绘制</strong>
        <span>Matplotlib 正式图</span>
      </header>
      <label>
        数据来源
        <select value={sourceName} onChange={(event) => onSourceNameChange(event.target.value)}>
          {(session?.capability.data_slots?.length ? session.capability.data_slots : []).map((slot) => (
            <option key={slot} value={slot}>
              {slot}
            </option>
          ))}
        </select>
      </label>
      <label>
        保存路径
        <input value={outputPath} onChange={(event) => onOutputPathChange(event.target.value)} placeholder="留空则写入项目 exports" />
      </label>
      <section className={`status-box ${hasPrimary ? "ok" : "warn"}`}>
        <strong>绘图前检查</strong>
        <span>{hasPrimary ? "主样本集已绑定，可渲染当前来源；缺结果时后端会返回补算建议。" : "缺少主样本集，暂不可绘图。"}</span>
        <span>当前来源：{sourceName || "未选择"}</span>
      </section>
      <button disabled={!hasPrimary} onClick={onRender}>
        渲染正式图
      </button>
      <button className="secondary" disabled={!hasPrimary} onClick={onSave}>
        保存图片
      </button>
      <button className="secondary" disabled={!plot} onClick={onOpenLargePreview}>
        大图预览
      </button>
      <button className="ghost" onClick={onOpenThemeEditor}>
        Theme 编辑器
      </button>
      <button className="ghost" disabled={!hasPrimary} onClick={onPrecheckExport}>
        导出预检
      </button>
      {!hasPrimary ? <p className="status-box">请先绑定主样本集，再渲染或保存图形。</p> : null}
      {exportPrecheck ? (
        <DataTable
          title="导出预检"
          columns={["项目", "状态"]}
          rows={[
            ["目标", exportPrecheck.target],
            ["状态", exportPrecheck.valid ? "可导出" : "缺少前置结果"],
            ["缺项", exportPrecheck.missing_requirements.join(" / ") || "无"]
          ]}
        />
      ) : null}
    </aside>
    <section className="result-card">
      <header className="section-header">
        <strong>图形预览</strong>
        <span>{plot ? `${plot.image_format.toUpperCase()} 已渲染` : "尚未渲染"}</span>
      </header>
      <div className="plot-frame" dangerouslySetInnerHTML={{ __html: plot?.image ?? "<p>尚未渲染图形。</p>" }} />
    </section>
  </section>
);
