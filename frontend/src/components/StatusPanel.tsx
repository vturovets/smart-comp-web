import { Alert, Box, Button, LinearProgress, Stack, Typography } from "@mui/material";

import { JobStatus, JobSummary } from "../api";

interface StatusPanelProps {
  job?: JobSummary;
  onCancel?: () => void;
  isCancelling?: boolean;
}

const statusCopy: Record<JobStatus, string> = {
  [JobStatus.QUEUED]: "Queued",
  [JobStatus.RUNNING]: "Running",
  [JobStatus.COMPLETED]: "Completed",
  [JobStatus.CANCELLED]: "Cancelled",
  [JobStatus.FAILED]: "Failed"
};

export function StatusPanel({ job, onCancel, isCancelling }: StatusPanelProps) {
  if (!job) return null;
  const isActive = job.status === JobStatus.RUNNING || job.status === JobStatus.QUEUED;
  return (
    <Box border={1} borderColor="divider" borderRadius={2} p={2}>
      <Stack spacing={2}>
        <Stack direction="row" justifyContent="space-between" alignItems="center">
          <Typography variant="h6">Job status</Typography>
          <Typography color="text.secondary">{statusCopy[job.status]}</Typography>
        </Stack>
        {job.progress && (
          <Stack spacing={1}>
            <LinearProgress
              variant="determinate"
              value={Math.min(100, job.progress.percent)}
              aria-label="job-progress"
            />
            <Typography variant="body2" color="text.secondary">
              {job.progress.step || "queued"} • {Math.round(job.progress.percent)}%
            </Typography>
            {job.progress.message && (
              <Typography variant="body2" color="text.secondary">
                {job.progress.message}
              </Typography>
            )}
          </Stack>
        )}
        {job.error && (
          <Alert severity="error" data-testid="job-error">
            {job.error}
          </Alert>
        )}
        {isActive && onCancel && (
          <Button variant="outlined" color="secondary" onClick={onCancel} disabled={isCancelling}>
            {isCancelling ? "Cancelling..." : "Cancel job"}
          </Button>
        )}
      </Stack>
    </Box>
  );
}
