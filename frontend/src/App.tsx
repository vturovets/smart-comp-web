import { useMutation, useQuery } from "@tanstack/react-query";
import { Alert, Container, Grid, Stack, Typography } from "@mui/material";
import { useEffect, useMemo, useState } from "react";

import { Artifact, JobStatus, buildApiClient } from "./api";
import { JobForm } from "./components/JobForm";
import { ResultsPanel } from "./components/ResultsPanel";
import { StatusPanel } from "./components/StatusPanel";
import { env } from "./config/env";

function App() {
  const api = useMemo(() => buildApiClient(env.apiBaseUrl), []);
  const [jobId, setJobId] = useState<string | null>(null);
  const [plotError, setPlotError] = useState<string | null>(null);

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

  const loadPlot = async (artifactName: string) => {
    if (!jobId) throw new Error("Missing job id for plot");
    const blob = await api.downloadArtifact(jobId, artifactName);
    const text = await blob.text();
    try {
      return JSON.parse(text);
    } catch (error) {
      setPlotError(`Plot artifact ${artifactName} is not JSON.`);
      throw error;
    }
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
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <Stack spacing={4}>
        <header>
          <p className="eyebrow">Smart Comp</p>
          <Typography variant="h4" component="h1">
            Analysis console
          </Typography>
          <Typography className="lede">
            Launch bootstrap, Kruskal-Wallis, and descriptive-only jobs, edit configs, watch status, cancel
            when necessary, and review results with Plotly visuals and MUI data grids.
          </Typography>
        </header>

        <Grid container spacing={3} alignItems="stretch">
          <Grid item xs={12} md={6}>
            <Stack spacing={2} sx={{ height: "100%" }}>
              <JobForm
                defaults={defaultsQuery.data}
                isCreating={createJob.isPending}
                onCreate={(payload) => createJob.mutate(payload)}
                error={createJob.isError ? (createJob.error as Error).message : null}
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
          </Grid>
          <Grid item xs={12} md={6}>
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
          </Grid>
        </Grid>
      </Stack>
    </Container>
  );
}

export default App;
