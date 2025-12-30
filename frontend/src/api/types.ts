export enum JobType {
  BOOTSTRAP_SINGLE = "BOOTSTRAP_SINGLE",
  BOOTSTRAP_DUAL = "BOOTSTRAP_DUAL",
  KW_PERMUTATION = "KW_PERMUTATION",
  DESCRIPTIVE_ONLY = "DESCRIPTIVE_ONLY"
}

export enum JobStatus {
  QUEUED = "QUEUED",
  RUNNING = "RUNNING",
  COMPLETED = "COMPLETED",
  FAILED = "FAILED",
  CANCELLED = "CANCELLED"
}

export interface PlotToggles {
  histogram?: boolean | null;
  boxplot?: boolean | null;
  kde?: boolean | null;
}

export interface ConfigOverrides {
  alpha?: number | null;
  threshold?: number | null;
  bootstrapIterations?: number | null;
  permutationCount?: number | null;
  sampleSize?: number | null;
  outlierLowerBound?: number | null;
  outlierUpperBound?: number | null;
  descriptiveEnabled?: boolean | null;
  createLog?: boolean | null;
  cleanAll?: boolean | null;
  plots?: PlotToggles | null;
}

export interface ConfigDefaults extends ConfigOverrides {
  alpha: number | null;
  descriptiveEnabled: boolean;
  createLog: boolean;
  cleanAll: boolean;
  plots: PlotToggles;
}

export interface JobProgress {
  percent: number;
  step?: string | null;
  message?: string | null;
}

export interface JobSummary {
  jobId: string;
  jobType: JobType;
  status: JobStatus;
  createdAt: string;
  startedAt?: string | null;
  finishedAt?: string | null;
  taskId?: string | null;
  progress: JobProgress;
  error?: string | null;
  userId?: string | null;
}

export interface PlotRef {
  kind?: string | null;
  artifactName: string;
}

export interface InterpretationText {
  text?: string | null;
}

export type InterpretationContent = InterpretationText | string | null;

export interface Decision {
  alpha?: number | null;
  pValue?: number | null;
  significant?: boolean | null;
}

export interface KwGroupFile {
  fileName: string;
  n?: number | null;
  p95?: number | null;
  median?: number | null;
}

export interface KwGroupResult {
  groupName: string;
  files: KwGroupFile[];
}

export interface BaseResults {
  jobId: string;
  plots?: PlotRef[];
}

export interface BootstrapSingleResults extends BaseResults {
  jobType: JobType.BOOTSTRAP_SINGLE;
  decision: Decision;
  metrics: Record<string, unknown>;
  descriptive: Record<string, unknown>;
  interpretation?: InterpretationContent;
}

export interface BootstrapDualResults extends BaseResults {
  jobType: JobType.BOOTSTRAP_DUAL;
  decision: Decision;
  metrics: Record<string, unknown>;
  descriptive: Record<string, unknown>;
  interpretation?: InterpretationContent;
}

export interface KwPermutationResults extends BaseResults {
  jobType: JobType.KW_PERMUTATION;
  decision: Decision;
  omnibus: Record<string, unknown>;
  groups: KwGroupResult[];
}

export interface DescriptiveOnlyResults extends BaseResults {
  jobType: JobType.DESCRIPTIVE_ONLY;
  descriptive: Record<string, unknown>;
  interpretation?: InterpretationContent;
}

export type JobResults =
  | BootstrapSingleResults
  | BootstrapDualResults
  | KwPermutationResults
  | DescriptiveOnlyResults;

export interface Artifact {
  name: string;
  contentType?: string | null;
  sizeBytes: number;
  createdAt: string;
}

export interface ArtifactList {
  jobId: string;
  artifacts: Artifact[];
}

export interface JobCreateResponse {
  jobId: string;
}

export interface CreateJobPayload {
  jobType: JobType;
  config?: ConfigOverrides;
  file1?: File | null;
  file2?: File | null;
  file3?: File | null;
}
