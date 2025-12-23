# Solution Design Document: Smart-Comp Web Application (Backend + Frontend)

This document describes a high-level solution for the Smart-Comp Web Application based on the provided SRS (backend) and the frontend implementation guidance. It reflects **Option A** for job submission (**submit files with the job request**) and updates the **KW_PERMUTATION ZIP spec** to support **both** “folder-per-group” and “file-per-group” layouts.

## 1. Goals and scope

### 1.1 Objectives

- Provide a web-accessible interface for Smart-Comp analyses:
  
  - Bootstrap hypothesis tests (single dataset and dual dataset)
  
  - Descriptive analysis and plots
  
  - Kruskal–Wallis permutation test for multi-group comparisons

- Enable automation/CI integration via REST endpoints.

- Support asynchronous execution for compute-heavy tasks with:
  
  - job status/progress polling
  
  - cancellation
  
  - artifact download

### 1.2 Explicit constraints

- **No authentication/authorization** (per SRS open issue marked Negative).

- **No OpenAI API usage** (results are computed deterministically; any “interpretation” is local/rule-based at most).

- File retention is temporary; cleaned outputs/logs/artifacts are produced per run and cleaned per policy.

## 2. Architecture overview

### 2.1 Components

1. **Frontend SPA (React + TypeScript, Vite)**
   
   - Upload CSV(s) / KW ZIP
   
   - Edit configuration (with defaults pulled from backend)
   
   - Trigger analysis job (multipart upload)
   
   - Poll job status/progress; support cancel
   
   - Render results (cards/tables/plots) and provide artifact downloads

2. **Backend API (Python, recommended: FastAPI)**
   
   - REST API implementing:
     
     - config defaults
     
     - job creation (Option A multipart: files included)
     
     - job status/progress
     
     - results retrieval
     
     - artifact listing + download
     
     - cancellation
   
   - Wraps Smart-Comp logic as importable library calls (preferred over shelling out).

3. **Async Worker + Queue (recommended: Celery/RQ + Redis)**
   
   - Executes long-running bootstrap/permutation tasks outside request threads
   
   - Updates progress periodically
   
   - Writes artifacts to per-job directory

4. **Storage**
   
   - **Filesystem**: per-job working directories for inputs/outputs
   
   - **Redis**: job metadata/progress/state (and possibly result pointers)

### 2.2 Execution model

- `POST /api/jobs` returns immediately with `jobId`

- Worker executes job steps and updates progress

- Frontend polls `GET /api/jobs/{jobId}` until terminal state

- On `COMPLETED`, frontend fetches normalized JSON results and artifacts.

## 3. Key design decisions

### 3.1 Option A job submission (selected)

- A single request submits:
  
  - job type
  
  - JSON config overrides
  
  - files (CSV(s) or KW ZIP)

- Benefits: simplest client implementation; no separate upload lifecycle.

### 3.2 Normalized web-native results

- Backend produces:
  
  - `results.txt` (legacy/CLI-like format)
  
  - `results.json` (normalized, frontend-friendly)

- Frontend primarily consumes `results.json` and uses artifact endpoints for plots/files.

### 3.3 KW_PERMUTATION ZIP supports two layouts (explicit)

- **Layout A:** folders define groups (supports multiple files per group)

- **Layout B:** each file is one group (flat zip)

Detection rules and mixed-layout behavior are explicitly defined (see §6).

## 4. Backend design

### 4.1 Domain model

#### Job

- `jobId: UUID`

- `jobType: BOOTSTRAP_SINGLE | BOOTSTRAP_DUAL | KW_PERMUTATION | DESCRIPTIVE_ONLY`

- `status: QUEUED | RUNNING | COMPLETED | FAILED | CANCELLED`

- timestamps: `createdAt`, `startedAt`, `finishedAt`

- `progress?: { step: string; percent: number; message?: string }`

- `error?: { code: string; message: string; details?: object }` (when FAILED)

- `inputs`: effective config + input file metadata

- `outputs`: result pointers + artifact list

#### Artifact

- `name` (download key)

- `contentType`

- `sizeBytes?`

- `createdAt?`

### 4.2 Working directory layout

Per job:

```
/tmp/smartcomp/<jobId>/
  input/
    file1.csv
    file2.csv
    kwBundle.zip
  output/
    results.json
    results.txt
    *_cleaned.csv
    plots/
      hist_*.png
      box_*.png
      kde_*.png
    kw_report.json
    kw_summary.csv
    tool.log
```

### 4.3 Cleanup and retention

- Default: follow Smart-Comp behavior (generate cleaned copies/logs if configured).

- Add a **TTL cleanup** (e.g., 24h) as a safety net to prevent orphaned job folders.

- If “clean_all” behavior exists in Smart-Comp config, expose it as a backend config option.

### 4.4 Observability

- Per-job structured logs (`tool.log` artifact when enabled)

- Correlation via `X-Request-Id` header; include `requestId` in error payloads.

## 5. REST API (Option A)

### 5.1 Endpoints

- `GET /api/config/defaults`

- `POST /api/jobs` **multipart/form-data** (Option A)

- `GET /api/jobs/{jobId}`

- `POST /api/jobs/{jobId}/cancel`

- `GET /api/jobs/{jobId}/results`

- `GET /api/jobs/{jobId}/artifacts`

- `GET /api/jobs/{jobId}/artifacts/{artifactName}`

### 5.2 `POST /api/jobs` (multipart/form-data)

#### Common fields

- `jobType`: one of `BOOTSTRAP_SINGLE | BOOTSTRAP_DUAL | KW_PERMUTATION | DESCRIPTIVE_ONLY`

- `config`: JSON string of config overrides (see schema in §8)

#### Files by job type

- `DESCRIPTIVE_ONLY`
  
  - `file1` (CSV)
  
  - ignores threshold/bootstrap/permutation fields (or validates they’re absent)
  
  - respects plot toggles (`plots.*`) and any cleaning settings

- `BOOTSTRAP_SINGLE`
  
  - `file1` (CSV)

- `BOOTSTRAP_DUAL`
  
  - `file1` (CSV)
  
  - `file2` (CSV)

- `KW_PERMUTATION`
  
  - `kwBundle` (ZIP) — supports Layout A and Layout B (see §6)

#### Response

- `201 Created`

```json
{ "jobId": "3b0d4f7e-7f9f-4b68-a1b8-6d6b6a3c2a1a" }
```

### 5.3 Job status

`GET /api/jobs/{jobId}` returns metadata + progress:

```json
{
  "jobId": "…",
  "jobType": "KW_PERMUTATION",
  "status": "RUNNING",
  "createdAt": "2025-12-23T10:00:00Z",
  "progress": { "step": "Permutation loop", "percent": 42.1, "message": "4200/10000" }
}
```

### 5.4 Results and artifacts

- `GET /api/jobs/{jobId}/results` returns normalized `results.json` (409 if not ready)

- `GET /api/jobs/{jobId}/artifacts` lists files available for download

- `GET /api/jobs/{jobId}/artifacts/{artifactName}` streams the artifact

### 5.5 Cancellation

- `POST /api/jobs/{jobId}/cancel`
  
  - `202` on accepted cancel request
  
  - `409` if job is already terminal

### 6.1 Supported ZIP layouts

#### Layout A — folder-per-group (recommended when groups have multiple files)

Top-level folder name is the group label; all CSVs under it belong to that group.

Example:

```
GroupA/a1.csv
GroupA/a2.csv
GroupB/b1.csv
GroupB/b2.csv
```

#### Layout B — file-per-group (flat ZIP)

Each root-level CSV is a group; group label derived from filename stem.

Example:

```
Control.csv
Variant.csv
Treatment.csv
```

### 6.2 Detection and precedence

Backend determines layout as follows:

1. Ignore hidden/system files and folders (e.g., `__MACOSX/`, `.DS_Store`, dotfiles).

2. If **any CSV** exists under a top-level folder (`<folder>/.../*.csv`) → **Layout A**.

3. Else if CSV files exist **only at ZIP root** → **Layout B**.

### 6.3 Mixed layouts are rejected

If ZIP contains both:

- root-level CSVs **and**

- CSVs under group folders

→ `400` with:

- `code: "MIXED_KW_ZIP_LAYOUT"`

This avoids ambiguous grouping.

### 6.4 Nested directories

- Layout A: allowed; the **first path segment** determines the group
  
  - `GroupA/sub/run1.csv` still belongs to `GroupA`

- Layout B: nested directories are **not allowed**
  
  - reject with `code: "INVALID_KW_ZIP_LAYOUT"`

### 6.5 Group name rules

- Layout A: group name = top-level folder name

- Layout B: group name = filename stem (without `.csv`)

Sanitization (both layouts):

- trim whitespace

- replace non `[A-Za-z0-9._-]` with `_`

- collapse repeated `_`

- max length 64

Collisions after sanitization (case-insensitive) are rejected:

- `code: "DUPLICATE_GROUP_NAME"`

### 6.6 Minimum requirements

- At least **2 groups**

- Each group must include at least **1 CSV**

- Each CSV must meet Smart-Comp ingestion rules (numeric column requirements, cleaning, bounds/outliers, etc.)

Recommended related errors:

- `INSUFFICIENT_GROUPS`

- `EMPTY_GROUP`

- `INVALID_CSV`

## 7. Frontend design (aligned with implementation guidance)

### 7.1 Responsibilities

- Manage input selection and validation hints (size/type/basic checks)

- Fetch config defaults and render editable config form

- Trigger analysis job (multipart FormData)

- Poll job status and display progress

- Support cancel when enabled

- Render results:
  
  - decision summary (p-value, alpha, significant)
  
  - tables (MUI X Data Grid recommended)
  
  - plots (Plotly; either from backend-provided plot data or by displaying plot image artifacts)

- Provide artifact downloads (CSV/JSON/PNG/logs)

### 7.2 State management

- TanStack Query:
  
  - mutation: create job
  
  - polling query: job status while running
  
  - queries: results + artifacts when completed

### 7.3 UI notes for KW upload

Show clear helper text:

- “If your groups have multiple files, ZIP them into folders per group (recommended).”

- “If each group is one CSV, you can upload a flat ZIP with one CSV per group.”

- “Do not mix root CSVs and group folders.”

### 7.4 Frontend impact: DESCRIPTIVE_ONLY mode

Include:

- Add “Descriptive only” to the analysis type selector

- When selected:
  
  - require `file1`
  
  - hide/disable irrelevant fields (threshold, bootstrapIterations, permutationCount, etc.)
  
  - keep cleaning + plot toggles visible

- Results screen:
  
  - render descriptive card/table + plots
  
  - no “significance” decision block

---

## 8. Data contracts

### 8.1 Error response

```json
{
  "error": {
    "code": "INVALID_CSV",
    "message": "CSV must contain exactly one numeric column.",
    "details": { "fileField": "file1", "droppedRows": 12 }
  },
  "requestId": "b1b6c7..."
}
```

### 8.2 Config defaults / overrides (web model)

Backend should expose defaults via `GET /api/config/defaults` and accept overrides via `config` JSON in multipart.

Recommended fields:

- `alpha: number`

- `threshold?: number` (single bootstrap)

- `bootstrapIterations?: number`

- `permutationCount?: number`

- `sampleSize?: number`

- cleaning/outlier bounds (if supported by Smart-Comp config)

- `descriptiveEnabled?: boolean`

- `plots?: { histogram?: boolean; boxplot?: boolean; kde?: boolean }`

- `createLog?: boolean`

- cleanup toggles if present (e.g., `cleanAll?: boolean`)

### 8.3 Normalized results JSON (high-level shape)

- Bootstrap single/dual:
  
  - `decision: { significant, alpha, pValue }`
  
  - `metrics: p95 / delta`
  
  - optional descriptive summary + unimodality checks
  
  - `plots[]` references by artifact name (or embed Plotly traces later)

- KW permutation:
  
  - `decision: { alpha, pValue }`
  
  - `omnibus: { hStatistic, permutations }`
  
  - `groups[]` with per-group/per-file stats

## 9. OpenAPI “near-complete” snippet (Option A + KW ZIP rules)

> This is intentionally compact; it’s ready to paste into an OpenAPI 3.0 file with `info/servers` added.

```yaml
paths:
  /api/config/defaults:
    get:
      summary: Get default configuration values
      responses:
        "200":
          description: Default config
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/ConfigDefaults"

  /api/jobs:
    post:
      summary: Create analysis job (multipart upload; Option A)
      description: >
        Multipart job submission. The `config` field is a JSON string of ConfigOverrides.
        File requirements depend on jobType:
          - BOOTSTRAP_SINGLE: file1 required
          - BOOTSTRAP_DUAL: file1 and file2 required
          - KW_PERMUTATION: kwBundle required (ZIP)
          - DESCRIPTIVE_ONLY: file1 required
      requestBody:
        required: true
        content:
          multipart/form-data:
            schema:
              type: object
              required: [jobType, config]
              properties:
                jobType:
                  $ref: "#/components/schemas/JobType"
                config:
                  description: JSON string of ConfigOverrides
                  type: string
                file1:
                  type: string
                  format: binary
                file2:
                  type: string
                  format: binary
                kwBundle:
                  description: >
                    ZIP for KW_PERMUTATION. Supports:
                    (A) Folder-per-group: GroupA/a1.csv, GroupA/a2.csv, GroupB/b1.csv ...
                    (B) File-per-group (flat ZIP): Control.csv, Variant.csv, Treatment.csv ...
                    Detection: if any CSV exists under a top-level folder -> (A), else (B).
                    Mixed layouts (root CSVs + group folders) rejected.
                  type: string
                  format: binary
      responses:
        "201":
          description: Created
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/JobCreateResponse"
        "400":
          description: Validation error
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/ErrorResponse"

  /api/jobs/{jobId}:
    get:
      summary: Get job status and progress
      parameters:
        - in: path
          name: jobId
          required: true
          schema: { type: string, format: uuid }
      responses:
        "200":
          description: Job
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/Job"
        "404":
          description: Not found
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/ErrorResponse"

  /api/jobs/{jobId}/cancel:
    post:
      summary: Cancel a queued/running job
      parameters:
        - in: path
          name: jobId
          required: true
          schema: { type: string, format: uuid }
      responses:
        "202":
          description: Cancellation requested
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/Job"
        "409":
          description: Invalid state transition
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/ErrorResponse"

  /api/jobs/{jobId}/results:
    get:
      summary: Get normalized results JSON (completed jobs only)
      parameters:
        - in: path
          name: jobId
          required: true
          schema: { type: string, format: uuid }
      responses:
        "200":
          description: Results
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/Results"
        "409":
          description: Not ready
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/ErrorResponse"
        "404":
          description: Not found
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/ErrorResponse"

  /api/jobs/{jobId}/artifacts:
    get:
      summary: List downloadable artifacts
      parameters:
        - in: path
          name: jobId
          required: true
          schema: { type: string, format: uuid }
      responses:
        "200":
          description: Artifact list
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/ArtifactList"
        "404":
          description: Not found
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/ErrorResponse"

  /api/jobs/{jobId}/artifacts/{artifactName}:
    get:
      summary: Download an artifact
      parameters:
        - in: path
          name: jobId
          required: true
          schema: { type: string, format: uuid }
        - in: path
          name: artifactName
          required: true
          schema: { type: string }
      responses:
        "200":
          description: Binary artifact
          content:
            application/octet-stream:
              schema:
                type: string
                format: binary
        "404":
          description: Not found
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/ErrorResponse"

components:
  schemas:
    # ----------------------------
    # Core enums and shared models
    # ----------------------------
    JobType:
      type: string
      enum: [BOOTSTRAP_SINGLE, BOOTSTRAP_DUAL, KW_PERMUTATION, DESCRIPTIVE_ONLY]

    JobStatus:
      type: string
      enum: [QUEUED, RUNNING, COMPLETED, FAILED, CANCELLED]

    Progress:
      type: object
      required: [step, percent]
      properties:
        step: { type: string }
        percent: { type: number, minimum: 0, maximum: 100 }
        message: { type: string }

    JobCreateResponse:
      type: object
      required: [jobId]
      properties:
        jobId: { type: string, format: uuid }

    Error:
      type: object
      required: [code, message]
      properties:
        code: { type: string }
        message: { type: string }
        details: { type: object, additionalProperties: true }

    ErrorResponse:
      type: object
      required: [error, requestId]
      properties:
        error: { $ref: "#/components/schemas/Error" }
        requestId: { type: string }

    Job:
      type: object
      required: [jobId, jobType, status, createdAt]
      properties:
        jobId: { type: string, format: uuid }
        jobType: { $ref: "#/components/schemas/JobType" }
        status: { $ref: "#/components/schemas/JobStatus" }
        createdAt: { type: string, format: date-time }
        startedAt: { type: string, format: date-time, nullable: true }
        finishedAt: { type: string, format: date-time, nullable: true }
        progress: { $ref: "#/components/schemas/Progress" }
        error: { $ref: "#/components/schemas/Error", nullable: true }

    # ----------------------------
    # Config
    # ----------------------------
    ConfigDefaults:
      type: object
      properties:
        alpha: { type: number, default: 0.05 }
        threshold: { type: number, nullable: true }
        bootstrapIterations: { type: integer, default: 10000 }
        permutationCount: { type: integer, default: 10000 }
        sampleSize: { type: integer, nullable: true }
        descriptiveEnabled: { type: boolean, default: true }
        createLog: { type: boolean, default: false }
        plots:
          type: object
          properties:
            histogram: { type: boolean, default: true }
            boxplot: { type: boolean, default: true }
            kde: { type: boolean, default: true }

    ConfigOverrides:
      type: object
      additionalProperties: false
      properties:
        alpha: { type: number }
        threshold: { type: number }
        bootstrapIterations: { type: integer }
        permutationCount: { type: integer }
        sampleSize: { type: integer }
        outlierLowerBound: { type: number }
        outlierUpperBound: { type: number }
        descriptiveEnabled: { type: boolean }
        createLog: { type: boolean }
        plots:
          type: object
          properties:
            histogram: { type: boolean }
            boxplot: { type: boolean }
            kde: { type: boolean }

    # ----------------------------
    # Artifacts
    # ----------------------------
    Artifact:
      type: object
      required: [name, contentType]
      properties:
        name: { type: string }
        contentType: { type: string }
        sizeBytes: { type: integer }
        createdAt: { type: string, format: date-time }

    ArtifactList:
      type: object
      required: [jobId, artifacts]
      properties:
        jobId: { type: string, format: uuid }
        artifacts:
          type: array
          items: { $ref: "#/components/schemas/Artifact" }

    # ----------------------------
    # Results union and members
    # ----------------------------
    Results:
      oneOf:
        - $ref: "#/components/schemas/BootstrapSingleResults"
        - $ref: "#/components/schemas/BootstrapDualResults"
        - $ref: "#/components/schemas/KwPermutationResults"
        - $ref: "#/components/schemas/DescriptiveOnlyResults"

    PlotRef:
      type: object
      properties:
        kind: { type: string }
        artifactName: { type: string }

    BootstrapSingleResults:
      type: object
      required: [jobId, jobType, decision]
      properties:
        jobId: { type: string, format: uuid }
        jobType: { type: string, enum: [BOOTSTRAP_SINGLE] }
        decision:
          type: object
          required: [significant, alpha, pValue]
          properties:
            significant: { type: boolean }
            alpha: { type: number }
            pValue: { type: number }
        metrics: { type: object, additionalProperties: true }
        descriptive: { type: object, additionalProperties: true }
        plots:
          type: array
          items: { $ref: "#/components/schemas/PlotRef" }
        interpretation:
          type: object
          properties:
            markdown: { type: string }

    BootstrapDualResults:
      type: object
      required: [jobId, jobType, decision]
      properties:
        jobId: { type: string, format: uuid }
        jobType: { type: string, enum: [BOOTSTRAP_DUAL] }
        decision:
          type: object
          required: [significant, alpha, pValue]
          properties:
            significant: { type: boolean }
            alpha: { type: number }
            pValue: { type: number }
        metrics: { type: object, additionalProperties: true }
        descriptive: { type: object, additionalProperties: true }
        plots:
          type: array
          items: { $ref: "#/components/schemas/PlotRef" }

    KwPermutationResults:
      type: object
      required: [jobId, jobType, decision]
      properties:
        jobId: { type: string, format: uuid }
        jobType: { type: string, enum: [KW_PERMUTATION] }
        decision:
          type: object
          required: [alpha, pValue]
          properties:
            alpha: { type: number }
            pValue: { type: number }
        omnibus: { type: object, additionalProperties: true }
        groups:
          type: array
          items:
            type: object
            properties:
              groupName: { type: string }
              files:
                type: array
                items:
                  type: object
                  properties:
                    fileName: { type: string }
                    n: { type: integer }
                    p95: { type: number, nullable: true }
                    median: { type: number, nullable: true }
        plots:
          type: array
          items: { $ref: "#/components/schemas/PlotRef" }

    DescriptiveOnlyResults:
      type: object
      required: [jobId, jobType, descriptive]
      properties:
        jobId: { type: string, format: uuid }
        jobType: { type: string, enum: [DESCRIPTIVE_ONLY] }
        descriptive:
          description: >
            Descriptive statistics output. Structure may evolve; keep flexible.
            Should include sample size, central tendency/dispersion metrics, tail metrics,
            cleaning summary, and (optionally) unimodality checks.
          type: object
          additionalProperties: true
        plots:
          type: array
          items: { $ref: "#/components/schemas/PlotRef" }
```

## 10. Deployment blueprint (recommended)

- Containers:
  
  - `frontend` (static build via nginx)
  
  - `api` (FastAPI + Uvicorn/Gunicorn)
  
  - `worker` (Celery/RQ worker)
  
  - `redis`

- Shared volume for `/tmp/smartcomp` (or replace with object storage later).

- Cap worker concurrency based on CPU and dataset sizes.

---

## 11. Open issues filled by best guess (current best default)

- **AuthN/AuthZ:** none.

- **Retention:** artifacts kept until TTL cleanup (e.g., 24h) and/or Smart-Comp cleanup policy.

- **KW ZIP layout:** both supported; mixed layouts rejected (explicit, deterministic rule).
