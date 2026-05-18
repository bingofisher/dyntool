import { DataTable } from "../components/DataTable";
import type { ProcessingAction, SessionSnapshot, TablePayload } from "../types";

type ProcessingPageProps = {
  session: SessionSnapshot | null;
  actions: ProcessingAction[];
  selectedAction: string;
  params: Record<string, string>;
  resultPreview: TablePayload | null;
  hasPrimary: boolean;
  onActionChange: (actionName: string) => void;
  onParamChange: (key: string, value: string) => void;
  onRun: () => void;
  onPreview: () => void;
};

export const ProcessingPage = ({
  session,
  actions,
  selectedAction,
  params,
  resultPreview,
  hasPrimary,
  onActionChange,
  onParamChange,
  onRun,
  onPreview
}: ProcessingPageProps) => {
  const currentAction = actions.find((action) => action.action_name === selectedAction);
  return (
    <section className="workbench-layout">
      <aside className="control-card narrow">
        <header className="section-header">
          <strong>处理动作</strong>
          <span>{currentAction?.label ?? selectedAction}</span>
        </header>
        <label>
          处理方法
          <select value={selectedAction} onChange={(event) => onActionChange(event.target.value)}>
            {actions.map((action) => (
              <option key={action.action_name} value={action.action_name}>
                {action.label}
              </option>
            ))}
          </select>
        </label>
        <div className="form-stack">
          {Object.entries(params).length ? (
            Object.entries(params).map(([key, value]) => (
              <label key={key}>
                {key}
                <input value={value} onChange={(event) => onParamChange(key, event.target.value)} />
              </label>
            ))
          ) : (
            <p className="muted">当前动作无需专属参数。</p>
          )}
        </div>
        <section className={`status-box ${hasPrimary ? "ok" : "warn"}`}>
          <strong>执行前检查</strong>
          <span>{hasPrimary ? "主样本集已绑定，当前参数可提交执行。" : "缺少主样本集，暂不可执行。"}</span>
          <span>
            当前范围：{session?.current_scope.scope_kind ?? "all_samples"} / {session?.current_scope.target || "全部样本"}
          </span>
        </section>
        <button disabled={!hasPrimary} onClick={onRun}>
          执行分析
        </button>
        <button className="secondary" disabled={!hasPrimary} onClick={onPreview}>
          生成预览表
        </button>
        {!hasPrimary ? <p className="status-box">请先绑定主样本集，再执行分析或生成预览表。</p> : null}
      </aside>
      <section className="result-card">
        <header className="section-header">
          <strong>结果预览表</strong>
          <span>
            当前范围：{session?.current_scope.scope_kind ?? "all_samples"} / {session?.current_scope.target || "全部样本"}
          </span>
        </header>
        <DataTable
          title="结果预览表"
          columns={resultPreview?.columns ?? ["提示"]}
          rows={resultPreview?.rows ?? []}
          emptyText="尚未生成结果预览"
        />
      </section>
    </section>
  );
};
