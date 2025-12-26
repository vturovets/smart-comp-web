import { DataGrid, GridColDef } from "@mui/x-data-grid";
import { Alert, Box, Chip, Stack, Typography } from "@mui/material";

import {
  Artifact,
  BootstrapDualResults,
  BootstrapSingleResults,
  DescriptiveOnlyResults,
  JobResults,
  JobType,
  KwGroupResult,
  KwPermutationResults,
  PlotRef
} from "../api";
import { ArtifactsList } from "./ArtifactsList";
import { PlotGallery } from "./PlotGallery";

interface ResultsPanelProps {
  results?: JobResults;
  artifacts?: Artifact[];
  onDownloadArtifact: (artifact: Artifact) => Promise<void>;
  loadPlot: (artifactName: string) => Promise<{ data: any; layout?: any }>;
}

const decisionColor = (significant?: boolean | null) => {
  if (significant === undefined || significant === null) return "default";
  return significant ? "success" : "default";
};

const kvColumns: GridColDef[] = [
  { field: "metric", headerName: "Metric", flex: 1 },
  { field: "value", headerName: "Value", flex: 1 }
];

const groupsColumns: GridColDef[] = [
  { field: "group", headerName: "Group", flex: 1 },
  { field: "file", headerName: "File", flex: 1 },
  { field: "n", headerName: "n", width: 80, type: "number" },
  { field: "median", headerName: "Median", width: 120 },
  { field: "p95", headerName: "p95", width: 120 }
];

const toKvRows = (values: Record<string, unknown> = {}) =>
  Object.entries(values).map(([metric, value], idx) => ({
    id: `${metric}-${idx}`,
    metric,
    value: typeof value === "object" ? JSON.stringify(value) : String(value)
  }));

const toGroupRows = (groups: KwGroupResult[]) =>
  groups.flatMap((group) =>
    group.files.map((file) => ({
      id: `${group.groupName}-${file.fileName}`,
      group: group.groupName,
      file: file.fileName,
      n: file.n,
      median: file.median,
      p95: file.p95
    }))
  );

const getPlots = (results?: JobResults): PlotRef[] => results?.plots ?? [];

export function ResultsPanel({ results, artifacts, onDownloadArtifact, loadPlot }: ResultsPanelProps) {
  if (!results) return null;
  const plots = getPlots(results);
  const renderDecision = (decision: BootstrapSingleResults["decision"] | null | undefined) => {
    if (!decision) return null;
    return (
      <Stack direction="row" spacing={1} alignItems="center">
        <Typography variant="subtitle1">Decision</Typography>
        {decision.significant !== undefined && (
          <Chip label={decision.significant ? "Significant" : "Not significant"} color={decisionColor(decision.significant) as any} />
        )}
        {decision.pValue !== undefined && <Chip label={`p-value ${decision.pValue}`} variant="outlined" />}
        {decision.alpha !== undefined && <Chip label={`alpha ${decision.alpha}`} variant="outlined" />}
      </Stack>
    );
  };

  const renderBody = () => {
    switch (results.jobType) {
      case JobType.BOOTSTRAP_SINGLE: {
        const data = results as BootstrapSingleResults;
        return (
          <Stack spacing={2}>
            {renderDecision(data.decision)}
            <Typography variant="h6">Metrics</Typography>
            <div style={{ height: 260 }}>
              <DataGrid rows={toKvRows(data.metrics)} columns={kvColumns} disableRowSelectionOnClick hideFooter />
            </div>
            <Typography variant="h6">Descriptive</Typography>
            <div style={{ height: 260 }}>
              <DataGrid rows={toKvRows(data.descriptive)} columns={kvColumns} disableRowSelectionOnClick hideFooter />
            </div>
            {data.interpretation && (
              <Alert severity="info">Interpretation: {JSON.stringify(data.interpretation)}</Alert>
            )}
          </Stack>
        );
      }
      case JobType.BOOTSTRAP_DUAL: {
        const data = results as BootstrapDualResults;
        return (
          <Stack spacing={2}>
            {renderDecision(data.decision)}
            <Typography variant="h6">Metrics</Typography>
            <div style={{ height: 260 }}>
              <DataGrid rows={toKvRows(data.metrics)} columns={kvColumns} disableRowSelectionOnClick hideFooter />
            </div>
            <Typography variant="h6">Descriptive</Typography>
            <div style={{ height: 260 }}>
              <DataGrid rows={toKvRows(data.descriptive)} columns={kvColumns} disableRowSelectionOnClick hideFooter />
            </div>
          </Stack>
        );
      }
      case JobType.KW_PERMUTATION: {
        const data = results as KwPermutationResults;
        return (
          <Stack spacing={2}>
            {renderDecision(data.decision)}
            <Typography variant="h6">Omnibus</Typography>
            <div style={{ height: 220 }}>
              <DataGrid rows={toKvRows(data.omnibus)} columns={kvColumns} disableRowSelectionOnClick hideFooter />
            </div>
            <Typography variant="h6">Group details</Typography>
            <div style={{ height: 320 }}>
              <DataGrid rows={toGroupRows(data.groups)} columns={groupsColumns} disableRowSelectionOnClick hideFooter />
            </div>
          </Stack>
        );
      }
      case JobType.DESCRIPTIVE_ONLY: {
        const data = results as DescriptiveOnlyResults;
        return (
          <Stack spacing={2}>
            <Alert severity="info">Descriptive-only job: decision block omitted by design.</Alert>
            <Typography variant="h6">Descriptive summary</Typography>
            <div style={{ height: 260 }}>
              <DataGrid rows={toKvRows(data.descriptive)} columns={kvColumns} disableRowSelectionOnClick hideFooter />
            </div>
          </Stack>
        );
      }
      default:
        return null;
    }
  };

  return (
    <Box border={1} borderColor="divider" borderRadius={2} p={2} data-testid="results-panel">
      <Stack spacing={3}>
        <Typography variant="h6">Results</Typography>
        {renderBody()}
        <PlotGallery jobId={results.jobId} plots={plots} loadPlot={loadPlot} />
        <ArtifactsList artifacts={artifacts} onDownload={onDownloadArtifact} />
      </Stack>
    </Box>
  );
}
