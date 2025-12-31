import { useMutation, useQuery } from "@tanstack/react-query";
import { Alert, Box, Container, IconButton, Popover, Stack, Tooltip, Typography } from "@mui/material";
import { useEffect, useMemo, useState } from "react";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";

import { Artifact, JobStatus, PlotPayload, buildApiClient } from "./api";
import { JobForm } from "./components/JobForm";
import { ResultsPanel } from "./components/ResultsPanel";
import { StatusPanel } from "./components/StatusPanel";
import { env } from "./config/env";

function App() {
  const api = useMemo(() => buildApiClient(env.apiBaseUrl), []);
  const [jobId, setJobId] = useState<string | null>(null);
  const [plotError, setPlotError] = useState<string | null>(null);
  const [analysisInfoAnchor, setAnalysisInfoAnchor] = useState<HTMLElement | null>(null);

  const defaultsQuery = useQuery({
    queryKey: ["config-defaults"],
    queryFn: () => api.getConfigDefaults()
  });

  useEffect(() => {
    setPlotError(null);
  }, [jobId]);

  const createJob = useMutation({
    mutationFn: api.createJob.bind(api),
    onSuccess: (data) => setJobId(data.jobId)
  });

  const jobStatus = useQuery({
    queryKey: ["job-status", jobId],
    queryFn: () => api.getJob(jobId as string),
    enabled: Boolean(jobId),
    refetchInterval(query) {
      const status = query.state.data?.status;
      if (!status) return 1500;
      return status === JobStatus.COMPLETED || status === JobStatus.FAILED ? false : 1500;
    }
  });

  const resultsQuery = useQuery({
    queryKey: ["job-results", jobId],
    queryFn: () => api.getResults(jobId as string),
    enabled: jobStatus.data?.status === JobStatus.COMPLETED
  });

  const artifactsQuery = useQuery({
    queryKey: ["job-artifacts", jobId],
    queryFn: () => api.listArtifacts(jobId as string),
    enabled: jobStatus.data?.status === JobStatus.COMPLETED
  });

  const cancelMutation = useMutation({
    mutationFn: () => api.cancelJob(jobId as string),
    onSuccess: () => jobStatus.refetch()
  });

  const loadPlot = async (artifactName: string): Promise<PlotPayload> => {
    if (!jobId) throw new Error("Missing job id for plot");
    const { blob, contentType } = await api.downloadArtifactWithInfo(jobId, artifactName);
    const type = contentType || blob.type;

    if (type?.includes("json") || artifactName.endsWith(".json")) {
      const text = await blob.text();
      try {
        return JSON.parse(text);
      } catch (error) {
        setPlotError(`Plot artifact ${artifactName} is not JSON.`);
        throw error;
      }
    }

    if (type?.startsWith("image/")) {
      return { imageUrl: URL.createObjectURL(blob), contentType: type };
    }

    setPlotError(`Plot artifact ${artifactName} is not a supported plot format.`);
    throw new Error(`Unsupported plot format for ${artifactName}`);
  };

  const handleDownload = async (artifact: Artifact) => {
    if (!jobId) return;
    const blob = await api.downloadArtifact(jobId, artifact.name);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = artifact.name;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <Container maxWidth={false} disableGutters sx={{ py: 4, px: { xs: 2, sm: 3, md: 4 } }}>
      <Stack spacing={4}>
        <header>
          <p className="eyebrow">Smart Comp</p>
          <Stack direction="row" spacing={1} alignItems="center">
            <Typography variant="h4" component="h1">
              Analysis console
            </Typography>
            <Tooltip title="Show analysis console details">
              <IconButton
                aria-label="Analysis console info"
                size="small"
                onClick={(event) => setAnalysisInfoAnchor(event.currentTarget)}
              >
                <InfoOutlinedIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </Stack>
          <Popover
            open={Boolean(analysisInfoAnchor)}
            anchorEl={analysisInfoAnchor}
            onClose={() => setAnalysisInfoAnchor(null)}
            anchorOrigin={{ vertical: "bottom", horizontal: "left" }}
            transformOrigin={{ vertical: "top", horizontal: "left" }}
          >
            <Box sx={{ p: 2, maxWidth: 360 }}>
              <Typography variant="body2" className="lede">
                Launch bootstrap, Kruskal-Wallis, and descriptive-only jobs, edit configs, watch status, cancel when
                necessary, and review results with Plotly visuals and MUI data grids.
              </Typography>
            </Box>
          </Popover>
        </header>

        <Box
          sx={{
            display: "grid",
            gridTemplateColumns: { xs: "1fr", md: "minmax(0, 1fr) minmax(0, 1fr)" },
            gap: 3,
            alignItems: "stretch"
          }}
        >
          <Stack spacing={2} sx={{ height: "100%", minWidth: 0, width: "100%" }}>
            <JobForm
              defaults={defaultsQuery.data}
              isCreating={createJob.isPending}
              onCreate={(payload) => createJob.mutate(payload)}
              error={createJob.isError ? (createJob.error as Error).message : null}
              createStatus={createJob.status}
            />

            <Stack spacing={2}>
              <StatusPanel
                job={jobStatus.data}
                onCancel={jobStatus.data ? () => cancelMutation.mutate() : undefined}
                isCancelling={cancelMutation.isPending}
              />
              {plotError && <Alert severity="warning">{plotError}</Alert>}
            </Stack>
          </Stack>
          <Box sx={{ height: "100%", minWidth: 0, width: "100%" }}>
            <ResultsPanel
              jobId={jobId}
              isLoading={resultsQuery.isPending}
              isError={resultsQuery.isError}
              errorMessage={resultsQuery.isError ? (resultsQuery.error as Error).message : null}
              results={resultsQuery.data}
              artifacts={artifactsQuery.data?.artifacts}
              onDownloadArtifact={handleDownload}
              loadPlot={loadPlot}
            />
          </Box>
        </Box>
      </Stack>
    </Container>
  );
}

export default App;
