import {
  Alert,
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
import { useEffect, useMemo, useState } from "react";

import { ConfigDefaults, ConfigOverrides, CreateJobPayload, JobType } from "../api";

const MAX_UPLOAD_BYTES = 50 * 1024 * 1024;
const allowedTypes = new Set(["text/csv", "application/zip", "application/x-zip-compressed"]);

interface JobFormProps {
  defaults?: ConfigDefaults;
  onCreate: (payload: CreateJobPayload) => void;
  isCreating: boolean;
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

export function JobForm({ defaults, onCreate, isCreating, error }: JobFormProps) {
  const [jobType, setJobType] = useState<JobType>(JobType.BOOTSTRAP_SINGLE);
  const [config, setConfig] = useState<ConfigOverrides>({});
  const [file1, setFile1] = useState<File | null>(null);
  const [file2, setFile2] = useState<File | null>(null);
  const [file3, setFile3] = useState<File | null>(null);
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
    if (!file1) {
      setValidationError("Primary dataset (file1) is required.");
      return false;
    }
    const files = [file1, file2, file3].filter(Boolean) as File[];
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
    if (requiresSecondFile && !file2) {
      setValidationError("File 2 is required for dual bootstrap.");
      return false;
    }
    setValidationError(null);
    return true;
  };

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!validateUploads()) return;
    const payload: CreateJobPayload = {
      jobType,
      config: sanitizeConfig(config),
      file1,
      file2,
      file3
    };
    onCreate(payload);
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
    <Card component="form" onSubmit={handleSubmit} variant="outlined">
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

          <Grid container spacing={2}>
            <Grid item xs={12} md={6}>
              <Stack spacing={2}>
                <Typography variant="subtitle1">Uploads</Typography>
                <Button component="label" variant="contained">
                  Upload file 1 (required)
                  <input
                    type="file"
                    hidden
                    onChange={(e) => setFile1(e.target.files?.[0] ?? null)}
                    accept=".csv,.zip"
                    data-testid="file1-input"
                  />
                </Button>
                {requiresSecondFile && (
                  <Button component="label" variant="outlined">
                    Upload file 2
                    <input
                      type="file"
                      hidden
                      onChange={(e) => setFile2(e.target.files?.[0] ?? null)}
                      accept=".csv,.zip"
                      data-testid="file2-input"
                    />
                  </Button>
                )}
                {(isKw || !requiresSecondFile) && (
                  <Button component="label" variant="outlined">
                    Upload file 3 (optional)
                    <input
                      type="file"
                      hidden
                      onChange={(e) => setFile3(e.target.files?.[0] ?? null)}
                      accept=".csv,.zip"
                      data-testid="file3-input"
                    />
                  </Button>
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
            </Grid>

            <Grid item xs={12} md={6}>
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
            </Grid>
          </Grid>

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
