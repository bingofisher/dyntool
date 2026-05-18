import { DataTable } from "../components/DataTable";
import type { SessionSnapshot, TaskSnapshot } from "../types";

type OverviewPageProps = {
  session: SessionSnapshot | null;
  taskSnapshot: TaskSnapshot;
};

export const OverviewPage = ({ session, taskSnapshot }: OverviewPageProps) => {
  const sampleCount = session?.primary.sample_count ?? 0;
  const dataSlots = session?.capability.data_slots ?? [];
  const savedSubsets = session?.saved_subsets ?? [];
  const currentScope = session?.current_scope;
  const lastTask = taskSnapshot.tasks[0];
  const lastIssue = taskSnapshot.issues[0];

  return (
    <section className="overview-layout">
      <aside className="control-card overview-assets">
        <header className="section-header">
          <strong>项目资产</strong>
          <span>项目级对象</span>
        </header>
        <AssetGroup title="项目" rows={[session?.project.name ?? "AdvDynTool Web 项目", session?.project.workdir ?? "-"]} />
        <AssetGroup
          title="主样本集"
          rows={[session?.primary.name ?? "未绑定", sampleCount ? `${sampleCount} 个样本` : "暂无样本"]}
        />
        <AssetGroup
          title="子样本集"
          rows={savedSubsets.length ? savedSubsets.map((item) => `${item.name}：${item.count} 个样本`) : ["暂无内存子集"]}
        />
        <AssetGroup title="当前范围" rows={[`${currentScope?.scope_kind ?? "all_samples"} / ${currentScope?.target || "全部样本"}`]} />
      </aside>

      <section className="overview-primary">
        <DataTable
          title="主样本集属性"
          columns={["属性", "值"]}
          rows={[
            ["名称", session?.primary.name ?? "未绑定"],
            ["样本数", sampleCount ? String(sampleCount) : "-"],
            ["类型", session?.primary.class_name ?? "-"],
            ["metadata 字段", session?.primary.metadata_fields?.join(" / ") || "-"],
            ["存储绑定", session?.primary.storage_binding ?? "-"]
          ]}
          totalText={session?.primary.storage_binding ?? "等待绑定"}
        />
        <section className="table-card overview-data-assets">
          <header className="section-header">
            <strong>数据与结果资产</strong>
            <span>{dataSlots.length ? `${dataSlots.length} 项` : "无"}</span>
          </header>
          <div className="asset-chip-grid">
            {dataSlots.length ? dataSlots.map((slot) => <span key={slot}>{slot}</span>) : <span>暂无可用数据槽</span>}
          </div>
          <DataTable
            title="最近任务摘要"
            columns={["项目", "值"]}
            rows={[
              ["最近任务", lastTask ? `${lastTask.title} / ${lastTask.status}` : "无"],
              ["最近阶段", lastTask?.stage ?? "-"],
              ["最近问题", lastIssue ? `${lastIssue.title} / ${lastIssue.detail}` : "无"],
              ["结果预览", session?.last_preview.rows.length ? (session.last_preview.stale ? "已过期" : "可用") : "无"]
            ]}
          />
        </section>
      </section>

      <aside className="action-card overview-subsets">
        <header className="section-header">
          <strong>子样本集属性</strong>
          <span>{savedSubsets.length ? `${savedSubsets.length} 个` : "无"}</span>
        </header>
        <DataTable
          title="子样本集属性"
          columns={["名称", "样本数", "更新时间"]}
          rows={savedSubsets.map((item) => [item.name, String(item.count), item.timestamp])}
          emptyText="暂无保存的子样本集"
        />
        <section className="status-box">
          <strong>图形与导出资产</strong>
          <span>图形预览：{session?.last_plot.image ? (session.last_plot.stale ? "已过期" : "可用") : "无"}</span>
          <span>图形格式：{session?.last_plot.image_format || "-"}</span>
          <span>导出目录：{session?.project.export_dir ?? "-"}</span>
        </section>
      </aside>
    </section>
  );
};

const AssetGroup = ({ title, rows }: { title: string; rows: string[] }) => (
  <section className="asset-group">
    <strong>{title}</strong>
    {rows.map((row) => (
      <span key={row}>{row}</span>
    ))}
  </section>
);
