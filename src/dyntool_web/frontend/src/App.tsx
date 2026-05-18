import { useEffect, useState } from "react";

import {
  type SubsetFilterPayload,
  bindImport,
  loadActions,
  loadPlotTheme,
  loadSession,
  loadTasks,
  openProject,
  precheckExport,
  previewImport,
  previewProcessing,
  previewSubset,
  renderPlot,
  runProcessing,
  savePlot,
  savePlotTheme,
  saveSubset,
  setScope
} from "./api";
import { DataTable } from "./components/DataTable";
import { Modal } from "./components/Modal";
import { TaskPanel } from "./components/TaskPanel";
import { ImportPage } from "./pages/ImportPage";
import { OverviewPage } from "./pages/OverviewPage";
import { PlotPage } from "./pages/PlotPage";
import { ProcessingPage } from "./pages/ProcessingPage";
import type {
  ExportPrecheck,
  ImportPreview,
  PlotPayload,
  ProcessingAction,
  SessionSnapshot,
  SubsetRow,
  TablePayload,
  TaskSnapshot
} from "./types";

const fallbackNavigation = ["总览", "导入与筛选", "数据处理", "图形绘制"];
const uiStateKey = "advdyntool.web.ui";

export const App = () => {
  const [session, setSession] = useState<SessionSnapshot | null>(null);
  const [actions, setActions] = useState<ProcessingAction[]>([]);
  const [taskSnapshot, setTaskSnapshot] = useState<TaskSnapshot>({ tasks: [], issues: [] });
  const restoredUi = restoreUiState();
  const [activePage, setActivePage] = useState(restoredUi.activePage);
  const [workdir, setWorkdir] = useState("");
  const [sourcePath, setSourcePath] = useState("");
  const [importPreview, setImportPreview] = useState<ImportPreview | null>(null);
  const [subsetKeyword, setSubsetKeyword] = useState(restoredUi.subsetKeyword ?? "");
  const [subsetName, setSubsetName] = useState(restoredUi.subsetName ?? "Web 子集");
  const [subsetFilter, setSubsetFilter] = useState(restoredUi.subsetFilter ?? {
    keyword: "",
    metadataField: "",
    matchMode: "contains",
    rawDataVars: "accel",
    analysisDataVars: "",
    sortBy: "uid",
    sortDesc: false,
    offset: "0",
    limit: "200"
  });
  const [subsetRows, setSubsetRows] = useState<SubsetRow[]>([]);
  const [subsetTotalText, setSubsetTotalText] = useState("");
  const [selectedAction, setSelectedAction] = useState(restoredUi.selectedAction ?? "calc_freqspec");
  const [params, setParams] = useState<Record<string, string>>({});
  const [resultPreview, setResultPreview] = useState<TablePayload | null>(null);
  const [sourceName, setSourceName] = useState(restoredUi.sourceName ?? "freqspec");
  const [outputPath, setOutputPath] = useState("");
  const [plot, setPlot] = useState<PlotPayload | null>(null);
  const [exportPrecheck, setExportPrecheck] = useState<ExportPrecheck | null>(null);
  const [themeText, setThemeText] = useState("");
  const [modal, setModal] = useState<"" | "large-plot" | "theme" | "export">("");
  const [error, setError] = useState("");

  const refresh = async () => {
    const [sessionPayload, actionsPayload, tasksPayload] = await Promise.all([loadSession(), loadActions(), loadTasks()]);
    setSession(sessionPayload);
    setActions(actionsPayload.actions);
    setTaskSnapshot(tasksPayload);
    if (sessionPayload.last_preview.rows.length && !resultPreview) {
      setResultPreview(sessionPayload.last_preview);
    }
    if (sessionPayload.last_plot.image && !plot) {
      setPlot(sessionPayload.last_plot);
    }
    if (!workdir) {
      setWorkdir(sessionPayload.project.workdir);
      setSourcePath(sessionPayload.debug.default_data_path || sessionPayload.project.workdir);
    }
    const selected = actionsPayload.actions.find((action) => action.action_name === selectedAction) ?? actionsPayload.actions[0];
    if (selected && !Object.keys(params).length) {
      setSelectedAction(selected.action_name);
      setParams(selected.defaults);
    }
  };

  useEffect(() => {
    refresh().catch((exc: unknown) => setError(String(exc)));
  }, []);

  useEffect(() => {
    localStorage.setItem(
      uiStateKey,
      JSON.stringify({
        activePage,
        selectedAction,
        sourceName,
        subsetFilter,
        subsetKeyword,
        subsetName
      })
    );
  }, [activePage, selectedAction, sourceName, subsetFilter, subsetKeyword, subsetName]);

  useEffect(() => {
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const socket = new WebSocket(`${protocol}://${window.location.host}/api/tasks/stream`);
    socket.onmessage = (event) => setTaskSnapshot(JSON.parse(event.data) as TaskSnapshot);
    return () => socket.close();
  }, []);

  const run = async (label: string, action: () => Promise<void>) => {
    setError("");
    try {
      await action();
      await refresh();
    } catch (exc) {
      setError(`${label}失败：${String(exc instanceof Error ? exc.message : exc)}`);
    }
  };

  const changeAction = (actionName: string) => {
    setSelectedAction(actionName);
    setParams(actions.find((action) => action.action_name === actionName)?.defaults ?? {});
  };

  const subsetTarget = subsetRows.map((row) => row.uid).join(",");
  const hasPrimary = Boolean(session?.primary.sample_count);
  const subsetPayload = (): SubsetFilterPayload => ({
    name: subsetName,
    keyword: subsetKeyword,
    metadata_field: subsetFilter.metadataField,
    match_mode: subsetFilter.matchMode,
    raw_data_vars: splitList(subsetFilter.rawDataVars),
    analysis_data_vars: splitList(subsetFilter.analysisDataVars),
    sort_by: subsetFilter.sortBy,
    sort_desc: subsetFilter.sortDesc,
    offset: Number.parseInt(subsetFilter.offset || "0", 10) || 0,
    limit: Number.parseInt(subsetFilter.limit || "200", 10) || 200
  });
  const clearSubsetFilter = () => {
    setSubsetKeyword("");
    setSubsetName("Web 子集");
    setSubsetRows([]);
    setSubsetTotalText("");
    setSubsetFilter({
      keyword: "",
      metadataField: "",
      matchMode: "contains",
      rawDataVars: "accel",
      analysisDataVars: "",
      sortBy: "uid",
      sortDesc: false,
      offset: "0",
      limit: "200"
    });
  };
  const acceptSubsetPayload = (payload: { rows: SubsetRow[]; total?: number; total_mode?: string }) => {
    setSubsetRows(payload.rows);
    const totalMode = payload.total_mode === "exact" ? "精确命中" : "当前页";
    setSubsetTotalText(`${totalMode} ${payload.total ?? payload.rows.length}`);
  };

  return (
    <main className="app-shell">
      <header className="topbar">
        <strong>AdvDynTool Web 工作台</strong>
        <span>{session?.project.name ?? "未加载项目"}</span>
        <span>主集：{session?.primary.name ?? "未绑定"}</span>
        <nav className="nav-tabs">
          {(session?.navigation ?? fallbackNavigation).map((page) => (
            <button key={page} className={page === activePage ? "active" : ""} onClick={() => setActivePage(page)}>
              {page}
            </button>
          ))}
        </nav>
      </header>
      <section className="workspace-shell">
        <section className="page-stage">
          {error ? <section className="error-banner">{error}</section> : null}
          {activePage === "总览" ? (
            <OverviewPage
              session={session}
              taskSnapshot={taskSnapshot}
            />
          ) : null}
          {activePage === "导入与筛选" ? (
            <ImportPage
              sourcePath={sourcePath}
              importPreview={importPreview}
              session={session}
              subsetKeyword={subsetKeyword}
              subsetName={subsetName}
              subsetFilter={subsetFilter}
              subsetRows={subsetRows}
              subsetTotalText={subsetTotalText}
              onSubsetKeywordChange={setSubsetKeyword}
              onSubsetNameChange={setSubsetName}
              onSubsetFilterChange={(patch) => setSubsetFilter((current) => ({ ...current, ...patch }))}
              onPreview={() => run("检查数据集", async () => setImportPreview(await previewImport(sourcePath)))}
              onBind={() => run("绑定主集", async () => void (await bindImport(sourcePath)))}
              onPreviewSubset={() => run("预览命中", async () => acceptSubsetPayload(await previewSubset(subsetPayload())))}
              onSaveSubset={() => run("保存子集", async () => acceptSubsetPayload(await saveSubset(subsetPayload())))}
              onSetScope={() => run("设为当前范围", async () => void (await setScope(subsetTarget)))}
              onClearSubset={clearSubsetFilter}
            />
          ) : null}
          {activePage === "数据处理" ? (
            <ProcessingPage
              session={session}
              actions={actions}
              selectedAction={selectedAction}
              params={params}
              resultPreview={resultPreview}
              hasPrimary={hasPrimary}
              onActionChange={changeAction}
              onParamChange={(key, value) => setParams((current) => ({ ...current, [key]: value }))}
              onRun={() => run("执行分析", async () => void (await runProcessing(selectedAction, params)))}
              onPreview={() => run("生成预览表", async () => setResultPreview(await previewProcessing(sourceName)))}
            />
          ) : null}
          {activePage === "图形绘制" ? (
            <PlotPage
              session={session}
              sourceName={sourceName}
              outputPath={outputPath}
              plot={plot}
              exportPrecheck={exportPrecheck}
              hasPrimary={hasPrimary}
              onSourceNameChange={setSourceName}
              onOutputPathChange={setOutputPath}
              onRender={() => run("渲染正式图", async () => setPlot(await renderPlot(sourceName)))}
              onSave={() => run("保存图片", async () => setPlot(await savePlot(sourceName, outputPath)))}
              onOpenLargePreview={() => setModal("large-plot")}
              onOpenThemeEditor={() =>
                run("打开 Theme 编辑器", async () => {
                  const payload = await loadPlotTheme();
                  setThemeText(JSON.stringify(payload.theme, null, 2));
                  setModal("theme");
                })
              }
              onPrecheckExport={() =>
                run("导出预检", async () => {
                  setExportPrecheck(await precheckExport(sourceName));
                  setModal("export");
                })
              }
            />
          ) : null}
        </section>
      </section>
      <TaskPanel tasks={taskSnapshot.tasks} issues={taskSnapshot.issues} />
      <Modal title="大图预览" open={modal === "large-plot"} onClose={() => setModal("")} wide>
        <div className="plot-frame large" dangerouslySetInnerHTML={{ __html: plot?.image ?? "<p>尚未渲染图形。</p>" }} />
      </Modal>
      <Modal title="Theme 编辑器" open={modal === "theme"} onClose={() => setModal("")} wide>
        <p className="muted">编辑项目级 PlotTheme JSON 后保存，后端会写入 TOML 并用 PlotTheme 校验。</p>
        <textarea value={themeText} onChange={(event) => setThemeText(event.target.value)} />
        <button
          onClick={() =>
            run("保存 Theme", async () => {
              await savePlotTheme(JSON.parse(themeText) as Record<string, unknown>);
              setModal("");
            })
          }
        >
          保存 Theme
        </button>
      </Modal>
      <Modal title="导出预检" open={modal === "export"} onClose={() => setModal("")}>
        <DataTable
          title="导出预检"
          columns={["项目", "状态"]}
          rows={
            exportPrecheck
              ? [
                  ["目标", exportPrecheck.target],
                  ["状态", exportPrecheck.valid ? "可导出" : "缺少前置结果"],
                  ["缺项", exportPrecheck.missing_requirements.join(" / ") || "无"]
                ]
              : []
          }
          emptyText="尚未执行导出预检"
        />
      </Modal>
    </main>
  );
};

const splitList = (value: string): string[] =>
  value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);

const restoreUiState = (): {
  activePage: string;
  selectedAction?: string;
  sourceName?: string;
  subsetKeyword?: string;
  subsetName?: string;
  subsetFilter?: {
    keyword: string;
    metadataField: string;
    matchMode: string;
    rawDataVars: string;
    analysisDataVars: string;
    sortBy: string;
    sortDesc: boolean;
    offset: string;
    limit: string;
  };
} => {
  try {
    const raw = localStorage.getItem(uiStateKey);
    if (!raw) {
      return { activePage: "总览" };
    }
    const parsed = JSON.parse(raw) as ReturnType<typeof restoreUiState>;
    return {
      activePage: parsed.activePage ?? "总览",
      selectedAction: parsed.selectedAction,
      sourceName: parsed.sourceName,
      subsetKeyword: parsed.subsetKeyword,
      subsetName: parsed.subsetName,
      subsetFilter: parsed.subsetFilter
    };
  } catch {
    return { activePage: "总览" };
  }
};
