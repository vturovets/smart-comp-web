import { useEffect, useState, type ReactNode, type SyntheticEvent } from "react";

import { DataGrid, GridColDef } from "@mui/x-data-grid";
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Box,
  Card,
  CardContent,
  Chip,
  Stack,
  Typography
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import ReactMarkdown from "react-markdown";

import {
  Artifact,
  BootstrapDualResults,
  BootstrapSingleResults,
  DescriptiveOnlyResults,
  InterpretationContent,
  JobResults,
  JobType,
  KwGroupResult,
  KwPermutationResults,
  PlotRef
} from "../api";
import { ArtifactsList } from "./ArtifactsList";
import { PlotGallery } from "./PlotGallery";

interface ResultsPanelProps {
  jobId?: string | null;
  isLoading?: boolean;
  isError?: boolean;
  errorMessage?: string | null;
  results?: JobResults;
  artifacts?: Artifact[];
  onDownloadArtifact: (artifact: Artifact) => Promise<void>;
  loadPlot: (artifactName: string) => Promise<{ data: any; layout?: any }>;
}

const initialExpandedState = {
  metrics: true,
  descriptive: false,
  omnibus: false,
  groupDetails: false,
  descriptiveSummary: false,
  interpretation: false,
  artifacts: false
} as const;

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

interface ResultsAccordionSectionProps {
  id: keyof typeof initialExpandedState;
  title: string;
  expanded: boolean;
  onChange: (event: SyntheticEvent, expanded: boolean) => void;
  children: ReactNode;
  isEmpty?: boolean;
}

const ResultsAccordionSection = ({ id, title, expanded, onChange, children, isEmpty }: ResultsAccordionSectionProps) => (
  <Accordion elevation={0} disableGutters expanded={expanded} onChange={onChange}>
    <AccordionSummary expandIcon={<ExpandMoreIcon />} aria-controls={`${id}-content`} id={`${id}-header`}>
      <Typography variant="h6">{title}</Typography>
    </AccordionSummary>
    <AccordionDetails>{isEmpty ? <Typography color="text.secondary">No data</Typography> : children}</AccordionDetails>
  </Accordion>
);

const normalizeInterpretationText = (interpretation?: InterpretationContent | null): string | null => {
  const normalize = (text: unknown) => (typeof text === "string" ? text.replace(/\\n/g, "\n") : null);

  if (!interpretation) return null;

  if (typeof interpretation === "string") {
    try {
      const parsed = JSON.parse(interpretation);
      if (parsed && typeof parsed === "object" && "text" in parsed) {
        return normalize((parsed as { text?: unknown }).text);
      }
    } catch {
      // fall through to treat as raw text
    }
    return normalize(interpretation);
  }

  if (typeof interpretation === "object" && "text" in interpretation) {
    return normalize((interpretation as { text?: unknown }).text);
  }

  return null;
};

interface InterpretationSectionProps {
  interpretation?: InterpretationContent | null;
  expanded: boolean;
  onChange: (event: SyntheticEvent, expanded: boolean) => void;
}

const InterpretationSection = ({ interpretation, expanded, onChange }: InterpretationSectionProps) => {
  const interpretationText = normalizeInterpretationText(interpretation);
  return (
    <ResultsAccordionSection id="interpretation" title="Interpretation" expanded={expanded} onChange={onChange}>
      <Box
        sx={{
          border: 1,
          borderColor: "divider",
          borderRadius: 1,
          p: 2,
          bgcolor: "background.paper",
          maxHeight: 320,
          overflowY: "auto",
          minWidth: 0
        }}
        data-testid="interpretation-panel"
      >
        {interpretationText ? (
          <ReactMarkdown>{interpretationText}</ReactMarkdown>
        ) : (
          <Typography color="text.secondary">No interpretation available for this job.</Typography>
        )}
      </Box>
    </ResultsAccordionSection>
  );
};

export function ResultsPanel({
  jobId,
  isLoading,
  isError,
  errorMessage,
  results,
  artifacts,
  onDownloadArtifact,
  loadPlot
}: ResultsPanelProps) {
  const hasResults = Boolean(results);
  const plots = getPlots(results);
  const [expandedSections, setExpandedSections] = useState<typeof initialExpandedState>(initialExpandedState);

  useEffect(() => {
    if (results) {
      setExpandedSections(initialExpandedState);
    }
  }, [results?.jobId]);

  const handleAccordionChange =
    (section: keyof typeof initialExpandedState) => (_event: SyntheticEvent, isExpanded: boolean) =>
      setExpandedSections((prev) => ({ ...prev, [section]: isExpanded }));

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
        const metricsRows = toKvRows(data.metrics);
        const descriptiveRows = toKvRows(data.descriptive);
        return (
          <Stack spacing={2}>
            {renderDecision(data.decision)}
            <ResultsAccordionSection
              id="metrics"
              title="Metrics"
              expanded={expandedSections.metrics}
              onChange={handleAccordionChange("metrics")}
              isEmpty={!metricsRows.length}
            >
              <Box
                sx={{ height: 260, minWidth: 0, maxWidth: "100%", width: "100%", overflowX: "auto" }}
              >
                <DataGrid rows={metricsRows} columns={kvColumns} disableRowSelectionOnClick hideFooter />
              </Box>
            </ResultsAccordionSection>
            <ResultsAccordionSection
              id="descriptive"
              title="Descriptive"
              expanded={expandedSections.descriptive}
              onChange={handleAccordionChange("descriptive")}
              isEmpty={!descriptiveRows.length}
            >
              <Box
                sx={{ height: 260, minWidth: 0, maxWidth: "100%", width: "100%", overflowX: "auto" }}
              >
                <DataGrid rows={descriptiveRows} columns={kvColumns} disableRowSelectionOnClick hideFooter />
              </Box>
            </ResultsAccordionSection>
            <InterpretationSection
              interpretation={data.interpretation}
              expanded={expandedSections.interpretation}
              onChange={handleAccordionChange("interpretation")}
            />
          </Stack>
        );
      }
      case JobType.BOOTSTRAP_DUAL: {
        const data = results as BootstrapDualResults;
        const metricsRows = toKvRows(data.metrics);
        const descriptiveRows = toKvRows(data.descriptive);
        return (
          <Stack spacing={2}>
            {renderDecision(data.decision)}
            <ResultsAccordionSection
              id="metrics"
              title="Metrics"
              expanded={expandedSections.metrics}
              onChange={handleAccordionChange("metrics")}
              isEmpty={!metricsRows.length}
            >
              <Box
                sx={{ height: 260, minWidth: 0, maxWidth: "100%", width: "100%", overflowX: "auto" }}
              >
                <DataGrid rows={metricsRows} columns={kvColumns} disableRowSelectionOnClick hideFooter />
              </Box>
            </ResultsAccordionSection>
            <ResultsAccordionSection
              id="descriptive"
              title="Descriptive"
              expanded={expandedSections.descriptive}
              onChange={handleAccordionChange("descriptive")}
              isEmpty={!descriptiveRows.length}
            >
              <Box
                sx={{ height: 260, minWidth: 0, maxWidth: "100%", width: "100%", overflowX: "auto" }}
              >
                <DataGrid rows={descriptiveRows} columns={kvColumns} disableRowSelectionOnClick hideFooter />
              </Box>
            </ResultsAccordionSection>
            <InterpretationSection
              interpretation={data.interpretation}
              expanded={expandedSections.interpretation}
              onChange={handleAccordionChange("interpretation")}
            />
          </Stack>
        );
      }
      case JobType.KW_PERMUTATION: {
        const data = results as KwPermutationResults;
        const omnibusRows = toKvRows(data.omnibus);
        const groupRows = toGroupRows(data.groups);
        return (
          <Stack spacing={2}>
            {renderDecision(data.decision)}
            <ResultsAccordionSection
              id="omnibus"
              title="Omnibus"
              expanded={expandedSections.omnibus}
              onChange={handleAccordionChange("omnibus")}
              isEmpty={!omnibusRows.length}
            >
              <Box
                sx={{ height: 220, minWidth: 0, maxWidth: "100%", width: "100%", overflowX: "auto" }}
              >
                <DataGrid rows={omnibusRows} columns={kvColumns} disableRowSelectionOnClick hideFooter />
              </Box>
            </ResultsAccordionSection>
            <ResultsAccordionSection
              id="groupDetails"
              title="Group details"
              expanded={expandedSections.groupDetails}
              onChange={handleAccordionChange("groupDetails")}
              isEmpty={!groupRows.length}
            >
              <Box
                sx={{ height: 320, minWidth: 0, maxWidth: "100%", width: "100%", overflowX: "auto" }}
              >
                <DataGrid rows={groupRows} columns={groupsColumns} disableRowSelectionOnClick hideFooter />
              </Box>
            </ResultsAccordionSection>
          </Stack>
        );
      }
      case JobType.DESCRIPTIVE_ONLY: {
        const data = results as DescriptiveOnlyResults;
        const descriptiveRows = toKvRows(data.descriptive);
        return (
          <Stack spacing={2}>
            <Alert severity="info">Descriptive-only job: decision block omitted by design.</Alert>
            <ResultsAccordionSection
              id="descriptiveSummary"
              title="Descriptive summary"
              expanded={expandedSections.descriptiveSummary}
              onChange={handleAccordionChange("descriptiveSummary")}
              isEmpty={!descriptiveRows.length}
            >
              <Box
                sx={{ height: 260, minWidth: 0, maxWidth: "100%", width: "100%", overflowX: "auto" }}
              >
                <DataGrid rows={descriptiveRows} columns={kvColumns} disableRowSelectionOnClick hideFooter />
              </Box>
            </ResultsAccordionSection>
            <InterpretationSection
              interpretation={data.interpretation}
              expanded={expandedSections.interpretation}
              onChange={handleAccordionChange("interpretation")}
            />
          </Stack>
        );
      }
      default:
        return null;
    }
  };

  const renderEmptyState = () => {
    if (isError) {
      return (
        <Alert severity="error">
          {errorMessage || "Unable to load results. Ensure the backend is running and try again."}
        </Alert>
      );
    }
    if (!jobId) {
      return (
        <Typography color="text.secondary">
          No jobs yet. Start an analysis to see results, plots, and downloadable artifacts here.
        </Typography>
      );
    }
    if (isLoading) {
      return <Typography color="text.secondary">Waiting for job results…</Typography>;
    }
    return (
      <Typography color="text.secondary">
        Results will appear once the job finishes. If you recently started a job, keep this page open.
      </Typography>
    );
  };

  return (
    <Card
      variant="outlined"
      data-testid="results-panel"
      sx={{ width: "100%", minWidth: 0, height: "100%", display: "flex", flexDirection: "column" }}
    >
      <CardContent>
        <Stack spacing={3}>
          <Typography variant="h6">Results</Typography>
          {!hasResults ? (
            renderEmptyState()
          ) : (
            <>
              {renderBody()}
              <Box
                sx={{ minWidth: 0, maxWidth: "100%", width: "100%", overflowX: "auto" }}
              >
                <PlotGallery jobId={results.jobId} plots={plots} loadPlot={loadPlot} />
              </Box>
              <ResultsAccordionSection
                id="artifacts"
                title="Artifacts"
                expanded={expandedSections.artifacts}
                onChange={handleAccordionChange("artifacts")}
                isEmpty={!artifacts?.length}
              >
                <ArtifactsList artifacts={artifacts} onDownload={onDownloadArtifact} showTitle={false} />
              </ResultsAccordionSection>
            </>
          )}
        </Stack>
      </CardContent>
    </Card>
  );
}
