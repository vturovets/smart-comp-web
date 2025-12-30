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
const allowedTypes = new Set(["text/csv"]);
const CONTROL_HEIGHT = 56;
const STATUS_LINE_HEIGHT = 28;
const CONFIG_SPACING = 2;
const configFieldSx = {
  "& .MuiInputBase-root": {
    height: CONTROL_HEIGHT,
    alignItems: "center"
  },
  "& .MuiInputBase-input": {
    padding: "0 14px",
    boxSizing: "border-box"
  }
};

interface JobFormProps {
  defaults?: ConfigDefaults;
  onCreate: (payload: CreateJobPayload) => void;
  isCreating: boolean;
  error?: string | null;
  createStatus: MutationStatus;
}

type UploadStatus = "idle" | "uploading" | "uploaded" | "failed";

interface UploadState {
  file: File;
  status: UploadStatus;
  error?: string | null;
}

const numericFields: Array<keyof ConfigOverrides> = [
  "alpha",
  "threshold",
  "bootstrapIterations",
  "permutationCount",
  "sampleSize",
  "outlierLowerBound",
  "outlierUpperBound"
];

interface UploadControlProps {
  label: string;
  accept?: string;
  dataTestId?: string;
  multiple?: boolean;
  onFilesChange: (files: FileList | null) => void;
}

const UploadControl = ({
  label,
  accept = ".csv",
  dataTestId,
  multiple = false,
  onFilesChange
}: UploadControlProps) => {
  return (
    <Stack spacing={0.5} sx={{ width: "100%" }}>
      <Button component="label" variant="contained" fullWidth sx={{ height: CONTROL_HEIGHT }}>
        {label}
        <input
          type="file"
          hidden
          onChange={(e) => {
            const selected = e.target.files;
            onFilesChange(selected ?? null);
          }}
          accept={accept}
          data-testid={dataTestId}
          multiple={multiple}
        />
      </Button>
      <Box sx={{ minHeight: STATUS_LINE_HEIGHT, display: "flex", alignItems: "center" }} />
    </Stack>
  );
};

export function JobForm({ defaults, onCreate, isCreating, error, createStatus }: JobFormProps) {
  const [jobType, setJobType] = useState<JobType>(JobType.BOOTSTRAP_SINGLE);
  const [config, setConfig] = useState<ConfigOverrides>({});
  const [uploads, setUploads] = useState<UploadState[]>([]);
  const [validationError, setValidationError] = useState<string | null>(null);

  useEffect(() => {
    if (defaults) {
      setConfig(defaults);
    }
  }, [defaults]);

  const isDescriptive = jobType === JobType.DESCRIPTIVE_ONLY;
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

  const handleFileSelection = (files: FileList | null) => {
    if (!files || files.length === 0) {
      setUploads([]);
      return;
    }
    setUploads(Array.from(files).map((file) => ({ file, status: "idle", error: null })));
    setValidationError(null);
  };

  const describeUploadStatus = (state: UploadState) => {
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
    return {
      text: `${state.file.name}${label ? ` — ${label}` : ""}`,
      color
    };
  };

  const validateUploads = (): boolean => {
    if (uploads.length === 0) {
      setValidationError("Please select at least one CSV file.");
      return false;
    }
    for (const { file } of uploads) {
      if (file.size > MAX_UPLOAD_BYTES) {
        setValidationError(`File ${file.name} exceeds ${Math.round(MAX_UPLOAD_BYTES / 1e6)}MB limit.`);
        return false;
      }
      if (!allowedTypes.has(file.type) && !file.name.toLowerCase().endswith(".csv")) {
        setValidationError(`File ${file.name} must be a CSV file.`);
        return false;
      }
    }
    if (jobType === JobType.BOOTSTRAP_SINGLE && uploads.length !== 1) {
      setValidationError("Bootstrap single requires exactly one CSV file.");
      return false;
    }
    if (jobType === JobType.DESCRIPTIVE_ONLY && uploads.length !== 1) {
      setValidationError("Descriptive only requires exactly one CSV file.");
      return false;
    }
    if (jobType === JobType.BOOTSTRAP_DUAL && uploads.length !== 2) {
      setValidationError("Bootstrap dual requires exactly two CSV files.");
      return false;
    }
    if (jobType === JobType.KW_PERMUTATION && uploads.length < 3) {
      setValidationError("KW permutation requires at least three CSV files.");
      return false;
    }
    setValidationError(null);
    return true;
  };

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!validateUploads()) return;
    setUploads((prev) => prev.map((entry) => ({ ...entry, status: "uploading", error: null })));

    const payload: CreateJobPayload = {
      jobType,
      config: sanitizeConfig(config),
      files: uploads.map((entry) => entry.file)
    };
    onCreate(payload);
  };

  useEffect(() => {
    if (createStatus === "success") {
      setUploads((prev) => prev.map((entry) => ({ ...entry, status: "uploaded", error: null })));
    }
    if (createStatus === "error") {
      setUploads((prev) => prev.map((entry) => ({ ...entry, status: "failed", error: error ?? null })));
    }
  }, [createStatus, error]);

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
    return items.reduce<Record<string, (typeof items)[number]>>((acc, item) => {
      acc[item.field] = item;
      return acc;
    }, {});
  }, [isDescriptive, isKw]);

  const renderConfigInput = (field: keyof ConfigOverrides, gridProps?: { xs?: number; sm?: number }) => {
    const meta = configGridColumns[field];
    if (!meta) return null;

    return (
      <Grid item xs={gridProps?.xs ?? 12} sm={gridProps?.sm ?? 6} key={field}>
        <TextField
          label={meta.label}
          type="number"
          fullWidth
          value={(config[field] as number | undefined | null) ?? ""}
          onChange={(e) => handleConfigChange(field, e.target.value)}
          disabled={meta.disabled}
          inputProps={{ min: 0, step: 0.001 }}
          sx={configFieldSx}
        />
      </Grid>
    );
  };
  const remainingConfigFields = useMemo(
    () =>
      Object.keys(configGridColumns).filter(
        (field) =>
          !["alpha", "threshold", "bootstrapIterations", "sampleSize", "permutationCount"].includes(
            field
          )
      ),
    [configGridColumns]
  );

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

          <Box>
            <Grid container spacing={2} alignItems="stretch">
              <Grid item xs={12} md={6}>
                <Typography variant="subtitle1">Uploads</Typography>
              </Grid>
              <Grid item xs={12} md={6}>
                <Typography variant="subtitle1">Config overrides</Typography>
              </Grid>

              <Grid item xs={12} md={6}>
                <Stack spacing={1}>
                  <UploadControl
                    label="Upload CSV files"
                    multiple
                    onFilesChange={handleFileSelection}
                    dataTestId="files-input"
                  />
                  <Box sx={{ minHeight: STATUS_LINE_HEIGHT * 2 }}>
                    {uploads.length === 0 ? (
                      <Typography variant="body2" color="text.secondary">
                        No files selected.
                      </Typography>
                    ) : (
                      <Stack spacing={0.5}>
                        {uploads.map((state, idx) => {
                          const status = describeUploadStatus(state);
                          return (
                            <Typography
                              key={`${state.file.name}-${idx}`}
                              variant="body2"
                              color={status.color}
                              noWrap
                              sx={{ overflow: "hidden", textOverflow: "ellipsis" }}
                            >
                              {status.text}
                            </Typography>
                          );
                        })}
                      </Stack>
                    )}
                  </Box>
                  {isKw && (
                    <Alert severity="info" variant="outlined" data-testid="kw-helper">
                      <Typography fontWeight={600}>KW permutation uploads</Typography>
                      <ul>
                        <li>Select at least three CSV files.</li>
                        <li>Each CSV is treated as a separate group.</li>
                      </ul>
                    </Alert>
                  )}
                </Stack>
              </Grid>
              <Grid item xs={12} md={6}>
                <Grid container spacing={CONFIG_SPACING} alignItems="stretch">
                  {renderConfigInput("alpha")}
                  {renderConfigInput("threshold")}
                  {renderConfigInput("bootstrapIterations")}
                  {renderConfigInput("sampleSize")}
                  {renderConfigInput("permutationCount")}
                </Grid>
              </Grid>

              {remainingConfigFields.length > 0 && (
                <>
                  <Grid item xs={12} md={6} />
                  <Grid item xs={12} md={6}>
                    <Grid container spacing={CONFIG_SPACING} alignItems="stretch">
                      {remainingConfigFields.map((field) =>
                        renderConfigInput(field as keyof ConfigOverrides, { xs: 12, sm: 12 })
                      )}
                    </Grid>
                  </Grid>
                </>
              )}
            </Grid>

            <Stack spacing={2} sx={{ mt: 2 }}>
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
              {validationError && <Alert severity="warning">{validationError}</Alert>}
              {error && <Alert severity="error">{error}</Alert>}
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
