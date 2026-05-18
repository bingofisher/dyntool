export type SessionSnapshot = {
  navigation: string[];
  project: { name: string; workdir: string; export_dir: string };
  primary: {
    sample_count?: number;
    name?: string;
    class_name?: string;
    storage_binding?: string;
    metadata_fields?: string[];
  };
  capability: { data_slots?: string[] };
  current_scope: { scope_kind: string; target: string };
  saved_subsets: { name: string; count: number; uids: string[]; timestamp: string }[];
  versions: { primary: number; scope: number; theme: number };
  recent_paths: string[];
  favorite_paths: string[];
  last_preview: TablePayload;
  last_plot: PlotPayload;
  debug: { default_data_path: string };
};

export type SubsetFilterState = {
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

export type SubsetRow = {
  uid: string;
  alias: string;
  metadata?: Record<string, string>;
  data_status?: Record<string, boolean>;
};

export type ProcessingAction = {
  action_name: string;
  label: string;
  defaults: Record<string, string>;
};

export type TaskRow = {
  id: string;
  title: string;
  status: string;
  progress: string;
  progress_percent: number;
  stage: string;
  cancelable: boolean;
  detail: string;
  timestamp: string;
};

export type IssueRow = {
  status: string;
  title: string;
  detail: string;
  timestamp: string;
};

export type ImportPreview = {
  source_path: string;
  detected_scheme: string;
  sample_count: number;
  metadata_mode: string;
  available_series_categories: string[];
  allow_execute: boolean;
  issues: string[];
  warnings: string[];
};

export type DirectoryPayload = {
  path: string;
  parent: string | null;
  directories: string[];
  files: string[];
};

export type TablePayload = {
  columns: string[];
  rows: string[][];
  stale?: boolean;
};

export type PlotPayload = {
  image_format: string;
  image: string;
  output_path?: string;
  stale?: boolean;
};

export type ExportPrecheck = {
  valid: boolean;
  missing_requirements: string[];
  target: string;
};

export type TaskSnapshot = {
  tasks: TaskRow[];
  issues: IssueRow[];
};
