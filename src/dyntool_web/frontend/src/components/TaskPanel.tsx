import type { IssueRow, TaskRow } from "../types";

type TaskPanelProps = {
  tasks: TaskRow[];
  issues: IssueRow[];
};

export const TaskPanel = ({ tasks, issues }: TaskPanelProps) => (
  <footer className="task-panel" data-testid="task-panel">
    <section>
      <details>
        <summary>
          <strong>任务与进度</strong>
          <span aria-label="展开任务详情">{tasks[0] ? `${tasks[0].title} / ${tasks[0].stage}` : "暂无任务"}</span>
        </summary>
        {tasks.slice(0, 8).map((task) => (
          <div className="task-row" key={task.id}>
            <span>{task.title}</span>
            <span>{task.stage}</span>
            <progress max={100} value={task.progress_percent} />
            <span>{task.cancelable ? "可中止" : "暂不可中止"}</span>
            <small>{task.detail}</small>
          </div>
        ))}
        {!tasks.length ? <p className="muted">暂无任务。</p> : null}
      </details>
    </section>
    <section>
      <details>
        <summary>
          <strong>问题列表</strong>
          <span>{issues.length ? `${issues.length} 项` : "无"}</span>
        </summary>
        {issues.slice(0, 6).map((issue, index) => (
          <div className="issue-row" key={`${issue.title}-${index}`}>
            <span>{issue.status}</span>
            <small>{issue.detail}</small>
          </div>
        ))}
        {!issues.length ? <p className="muted">暂无问题。</p> : null}
      </details>
    </section>
  </footer>
);
