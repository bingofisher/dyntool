import type {
  DirectoryPayload,
  ExportPrecheck,
  ImportPreview,
  PlotPayload,
  ProcessingAction,
  SessionSnapshot,
  SubsetRow,
  TablePayload,
  TaskSnapshot
} from "./types";

export const api = async <T>(url: string, init?: RequestInit): Promise<T> => {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...init
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as { detail?: string };
    throw new Error(payload.detail ?? `请求失败：${response.status}`);
  }
  return response.json() as Promise<T>;
};

export const post = (payload: unknown): RequestInit => ({
  method: "POST",
  body: JSON.stringify(payload)
});

export const loadSession = () => api<SessionSnapshot>("/api/session");

export const loadActions = () => api<{ actions: ProcessingAction[] }>("/api/processing/actions");

export const loadTasks = () => api<TaskSnapshot>("/api/tasks");

export const openProject = (path: string) => api<SessionSnapshot>("/api/project/open-path", post({ path }));

export const listDirectory = (path: string) => api<DirectoryPayload>(`/api/fs/list?path=${encodeURIComponent(path)}`);

export const previewImport = (sourcePath: string) =>
  api<ImportPreview>("/api/import/preview", post({ source_path: sourcePath }));

export const bindImport = (sourcePath: string) =>
  api<{ primary: SessionSnapshot["primary"]; capability: SessionSnapshot["capability"]; preview_reused: boolean }>(
    "/api/import/bind",
    post({ source_path: sourcePath })
  );

export type SubsetFilterPayload = {
  name: string;
  keyword: string;
  metadata_field: string;
  match_mode: string;
  raw_data_vars: string[];
  analysis_data_vars: string[];
  sort_by: string;
  sort_desc: boolean;
  offset: number;
  limit: number;
};

export type SubsetPayload = {
  name: string;
  count: number;
  total: number;
  total_mode: string;
  rows: SubsetRow[];
  saved_subset?: { name: string; count: number; uids: string[]; timestamp: string };
  message?: string;
};

export const previewSubset = (payload: SubsetFilterPayload) =>
  api<SubsetPayload>("/api/subsets/preview", post(payload));

export const saveSubset = (payload: SubsetFilterPayload) =>
  api<SubsetPayload>("/api/subsets/save", post(payload));

export const setScope = (target: string, scopeKind = "uid_list") => api("/api/scope/set", post({ scope_kind: scopeKind, target }));

export const runProcessing = (actionName: string, params: Record<string, string>) =>
  api("/api/processing/run", post({ action_name: actionName, params, strict: true, overwrite: true }));

export const previewProcessing = (dataVar: string) =>
  api<TablePayload>("/api/processing/preview", post({ preview_kind: "series_frame", data_var: dataVar, row_limit: 120 }));

export const loadPlotTheme = () => api<{ theme: Record<string, unknown>; theme_path: string }>("/api/plot/theme");

export const savePlotTheme = (theme: Record<string, unknown>) => api("/api/plot/theme", post({ theme }));

export const renderPlot = (sourceName: string) =>
  api<PlotPayload>("/api/plot/render", post({ source_name: sourceName, format: "svg", point_limit: 5000 }));

export const savePlot = (sourceName: string, outputPath: string) =>
  api<PlotPayload>("/api/plot/save", post({ source_name: sourceName, format: "svg", point_limit: 5000, output_path: outputPath }));

export const precheckExport = (dataVar: string) =>
  api<ExportPrecheck>("/api/export/precheck", post({ export_kind: "series_frame", data_var: dataVar }));
