import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  FormControl,
  FormControlLabel,
  FormGroup,
  Grid,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  Switch,
  TextField,
  Typography
} from "@mui/material";
import { MutationStatus } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import { ConfigDefaults, ConfigOverrides, CreateJobPayload, JobType } from "../api";

const MAX_UPLOAD_BYTES = 50 * 1024 * 1024;
const allowedTypes = new Set(["text/csv", "application/zip", "application/x-zip-compressed"]);

interface JobFormProps {
  defaults?: ConfigDefaults;
  onCreate: (payload: CreateJobPayload) => void;
  isCreating: boolean;
  error?: string | null;
  createStatus: MutationStatus;
}

type UploadStatus = "idle" | "uploading" | "uploaded" | "failed";

interface UploadState {
  file: File | null;
  status: UploadStatus;
  error?: string | null;
}

const initialUploadState: UploadState = {
  file: null,
  status: "idle",
  error: null
};

const numericFields: Array<keyof ConfigOverrides> = [
  "alpha",
  "threshold",
  "bootstrapIterations",
  "permutationCount",
  "sampleSize",
  "outlierLowerBound",
  "outlierUpperBound"
];

export function JobForm({ defaults, onCreate, isCreating, error, createStatus }: JobFormProps) {
  const [jobType, setJobType] = useState<JobType>(JobType.BOOTSTRAP_SINGLE);
  const [config, setConfig] = useState<ConfigOverrides>({});
  const [file1, setFile1] = useState<UploadState>(initialUploadState);
  const [file2, setFile2] = useState<UploadState>(initialUploadState);
  const [file3, setFile3] = useState<UploadState>(initialUploadState);
  const [validationError, setValidationError] = useState<string | null>(null);

  useEffect(() => {
    if (defaults) {
      setConfig(defaults);
    }
  }, [defaults]);

  const isDescriptive = jobType === JobType.DESCRIPTIVE_ONLY;
  const requiresSecondFile = jobType === JobType.BOOTSTRAP_DUAL;
  const isKw = jobType === JobType.KW_PERMUTATION;

  const handleConfigChange = (key: keyof ConfigOverrides, value: string | number | boolean) => {
    setConfig((prev) => ({
      ...prev,
      [key]: value === "" ? null : value
    }));
  };

  const handlePlotToggle = (key: keyof NonNullable<ConfigOverrides["plots"]>) => {
    setConfig((prev) => ({
      ...prev,
      plots: {
        ...prev.plots,
        [key]: !prev.plots?.[key]
      }
    }));
  };

  const sanitizeConfig = (raw: ConfigOverrides): ConfigOverrides => {
    const payload: ConfigOverrides = {};
    for (const [key, value] of Object.entries(raw)) {
      const typedKey = key as keyof ConfigOverrides;
      if (numericFields.includes(typedKey)) {
        const numberValue =
          value === "" || value === null || value === undefined ? null : Number(value);
        if (!Number.isNaN(numberValue as number)) {
          (payload as Record<string, unknown>)[typedKey] = numberValue;
        }
      } else if (value !== undefined) {
        (payload as Record<string, unknown>)[typedKey] = value;
      }
    }
    return payload;
  };

  const validateUploads = (): boolean => {
    if (!file1.file) {
      setValidationError("Primary dataset (file1) is required.");
      return false;
    }
    const files = [file1.file, file2.file, file3.file].filter(Boolean) as File[];
    for (const f of files) {
      if (f.size > MAX_UPLOAD_BYTES) {
        setValidationError(`File ${f.name} exceeds ${Math.round(MAX_UPLOAD_BYTES / 1e6)}MB limit.`);
        return false;
      }
      if (!allowedTypes.has(f.type)) {
        setValidationError(
          `File ${f.name} must be CSV or ZIP. Found ${f.type || "unknown type"}.`
        );
        return false;
      }
    }
    if (requiresSecondFile && !file2.file) {
      setValidationError("File 2 is required for dual bootstrap.");
      return false;
    }
    setValidationError(null);
    return true;
  };

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!validateUploads()) return;
    setFile1((prev) => (prev.file ? { ...prev, status: "uploading", error: null } : prev));
    setFile3((prev) => (prev.file ? { ...prev, status: "uploading", error: null } : prev));

    const payload: CreateJobPayload = {
      jobType,
      config: sanitizeConfig(config),
      file1: file1.file,
      file2: file2.file,
      file3: file3.file
    };
    onCreate(payload);
  };

  useEffect(() => {
    if (createStatus === "success") {
      setFile1((prev) => (prev.file ? { ...prev, status: "uploaded", error: null } : prev));
      setFile3((prev) => (prev.file ? { ...prev, status: "uploaded", error: null } : prev));
    }
    if (createStatus === "error") {
      setFile1((prev) => (prev.file ? { ...prev, status: "failed", error: error ?? null } : prev));
      setFile3((prev) => (prev.file ? { ...prev, status: "failed", error: error ?? null } : prev));
    }
  }, [createStatus, error]);

  const renderStatusLine = (state: UploadState) => {
    if (!state.file) return null;

    let label: string | null = null;
    if (state.status === "uploading") label = "Uploading...";
    if (state.status === "uploaded") label = "Uploaded";
    if (state.status === "failed") label = state.error ? `Failed: ${state.error}` : "Failed";

    const color =
      state.status === "failed"
        ? "error.main"
        : state.status === "uploaded"
          ? "success.main"
          : "text.secondary";

    return (
      <Typography variant="body2" color={color} sx={{ wordBreak: "break-word" }}>
        {state.file.name}
        {label ? ` — ${label}` : ""}
      </Typography>
    );
  };

  const configGridColumns = useMemo(() => {
    const items = [
      {
        label: "Alpha (significance)",
        field: "alpha",
        disabled: isDescriptive
      },
      {
        label: "Threshold",
        field: "threshold",
        disabled: isDescriptive
      },
      {
        label: "Bootstrap iterations",
        field: "bootstrapIterations",
        disabled: isDescriptive || isKw
      },
      {
        label: "Permutation count",
        field: "permutationCount",
        disabled: isDescriptive || !isKw
      },
      {
        label: "Sample size",
        field: "sampleSize",
        disabled: false
      }
    ];
    return items.filter((item) => !item.disabled || item.field === "alpha");
  }, [isDescriptive, isKw]);

  return (
    <Card
      component="form"
      onSubmit={handleSubmit}
      variant="outlined"
      sx={{ width: "100%", minWidth: 0, height: "100%", display: "flex", flexDirection: "column" }}
    >
      <CardContent>
        <Stack spacing={3}>
          <Stack spacing={1}>
            <Typography variant="h5">Create analysis job</Typography>
            <Typography color="text.secondary">
              Upload your datasets, edit configuration, and launch a Smart-Comp job. Status polling and
              cancellations will appear automatically.
            </Typography>
          </Stack>

          <Grid container spacing={2}>
            <Grid item xs={12} md={6}>
              <FormControl fullWidth>
                <InputLabel id="job-type-label">Job type</InputLabel>
                <Select
                  labelId="job-type-label"
                  value={jobType}
                  label="Job type"
                  onChange={(event) => setJobType(event.target.value as JobType)}
                >
                  <MenuItem value={JobType.BOOTSTRAP_SINGLE}>Bootstrap single</MenuItem>
                  <MenuItem value={JobType.BOOTSTRAP_DUAL}>Bootstrap dual</MenuItem>
                  <MenuItem value={JobType.KW_PERMUTATION}>KW permutation</MenuItem>
                  <MenuItem value={JobType.DESCRIPTIVE_ONLY}>Descriptive only</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} md={6}>
              <FormGroup row>
                <FormControlLabel
                  control={
                    <Switch
                      checked={Boolean(config.descriptiveEnabled)}
                      onChange={(event) => handleConfigChange("descriptiveEnabled", event.target.checked)}
                    />
                  }
                  label="Descriptive statistics"
                />
                <FormControlLabel
                  control={
                    <Switch
                      checked={Boolean(config.createLog)}
                      onChange={(event) => handleConfigChange("createLog", event.target.checked)}
                    />
                  }
                  label="Include log artifact"
                />
                <FormControlLabel
                  control={
                    <Switch
                      checked={Boolean(config.cleanAll)}
                      onChange={(event) => handleConfigChange("cleanAll", event.target.checked)}
                    />
                  }
                  label="Clean all data"
                />
              </FormGroup>
            </Grid>
          </Grid>

          <Box
            sx={{
              display: "grid",
              gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" },
              gap: 2,
              alignItems: "start"
            }}
          >
            <Stack spacing={2}>
              <Typography variant="subtitle1">Uploads</Typography>
              <Stack spacing={0.5}>
                <Button component="label" variant="contained" fullWidth>
                  Upload file 1 (required)
                  <input
                    type="file"
                    hidden
                    onChange={(e) => {
                      const selected = e.target.files?.[0] ?? null;
                      setFile1({
                        file: selected,
                        status: "idle",
                        error: null
                      });
                    }}
                    accept=".csv,.zip"
                    data-testid="file1-input"
                  />
                </Button>
                {renderStatusLine(file1)}
              </Stack>
              {requiresSecondFile && (
                <Stack spacing={0.5}>
                  <Button component="label" variant="outlined" fullWidth>
                    Upload file 2
                    <input
                      type="file"
                      hidden
                      onChange={(e) => {
                        const selected = e.target.files?.[0] ?? null;
                        setFile2({
                          file: selected,
                          status: "idle",
                          error: null
                        });
                      }}
                      accept=".csv,.zip"
                      data-testid="file2-input"
                    />
                  </Button>
                </Stack>
              )}
              {(isKw || !requiresSecondFile) && (
                <Stack spacing={0.5}>
                  <Button component="label" variant="outlined" fullWidth>
                    Upload file 3 (optional)
                    <input
                      type="file"
                      hidden
                      onChange={(e) => {
                        const selected = e.target.files?.[0] ?? null;
                        setFile3({
                          file: selected,
                          status: "idle",
                          error: null
                        });
                      }}
                      accept=".csv,.zip"
                      data-testid="file3-input"
                    />
                  </Button>
                  {renderStatusLine(file3)}
                </Stack>
              )}
              {isKw && (
                <Alert severity="info" variant="outlined" data-testid="kw-helper">
                  <Typography fontWeight={600}>KW ZIP guidance</Typography>
                  <ul>
                    <li>If your groups have multiple files, ZIP them into folders per group (recommended).</li>
                    <li>If each group is one CSV, you can upload a flat ZIP with one CSV per group.</li>
                    <li>Do not mix root CSVs and group folders.</li>
                  </ul>
                </Alert>
              )}
              {validationError && <Alert severity="warning">{validationError}</Alert>}
              {error && <Alert severity="error">{error}</Alert>}
            </Stack>

            <Stack spacing={2}>
              <Typography variant="subtitle1">Config overrides</Typography>
              <Grid container spacing={2}>
                {configGridColumns.map((item) => (
                  <Grid item xs={12} sm={6} key={item.field}>
                    <TextField
                      label={item.label}
                      type="number"
                      fullWidth
                      value={(config[item.field] as number | undefined | null) ?? ""}
                      onChange={(e) => handleConfigChange(item.field, e.target.value)}
                      disabled={item.disabled}
                      inputProps={{ min: 0, step: 0.001 }}
                    />
                  </Grid>
                ))}
              </Grid>
              <FormGroup row>
                <FormControlLabel
                  control={
                    <Switch
                      checked={Boolean(config.plots?.histogram)}
                      onChange={() => handlePlotToggle("histogram")}
                    />
                  }
                  label="Histogram"
                />
                <FormControlLabel
                  control={
                    <Switch
                      checked={Boolean(config.plots?.boxplot)}
                      onChange={() => handlePlotToggle("boxplot")}
                    />
                  }
                  label="Boxplot"
                />
                <FormControlLabel
                  control={
                    <Switch
                      checked={Boolean(config.plots?.kde)}
                      onChange={() => handlePlotToggle("kde")}
                    />
                  }
                  label="KDE"
                />
              </FormGroup>
            </Stack>
          </Box>

          {isDescriptive && (
            <Alert severity="info" variant="outlined">
              Descriptive only mode hides significance fields and requires only file 1. Cleaning and plot
              toggles remain available.
            </Alert>
          )}

          <Stack direction="row" justifyContent="flex-end">
            <Button variant="contained" color="primary" type="submit" disabled={isCreating}>
              {isCreating ? "Submitting..." : "Start job"}
            </Button>
          </Stack>
        </Stack>
      </CardContent>
    </Card>
  );
}
