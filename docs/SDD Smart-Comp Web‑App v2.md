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

The SRS explicitly called out the absence of an auth story. In the initial release the web application **does not require authentication**; it is intended to run inside a trusted internal network so that analysts can submit jobs without providing credentials. Treating the API as unauthenticated by default also simplifies local testing and automation. However, a public API without any form of access control is rarely acceptable in production, and many deployments will eventually sit behind an organisation’s SSO or identity gateway. The design therefore makes authentication **optional and configurable**:

- **Authentication/authorization (disabled by default)** – All endpoints are publicly accessible when `SMARTCOMP_AUTH_ENABLED` is `false` (the default). In this mode the backend assumes that network‑level controls (e.g. VPN, firewall rules) restrict access. When administrators set `SMARTCOMP_AUTH_ENABLED=true` the API **must** verify user identities and protect all non‑trivial endpoints. In order to be considered “done” the following acceptance criteria apply:
  
  1. When authentication is enabled, every request (except health/metrics endpoints) without a valid bearer token returns **401 Unauthorized** with a structured error payload and `WWW‑Authenticate: Bearer` header.
  
  2. Tokens are validated against the configured identity provider (initially Google OAuth2). Only users whose email matches one of the allowed domains (`SMARTCOMP_ALLOWED_DOMAINS`, comma‑separated) are authorised; requests with a valid token but unauthorised domain return **403 Forbidden**.
  
  3. Successful requests populate a `userId` claim on the FastAPI request context which is used to correlate jobs with their submitter. Clients can see only their own job metadata when auth is enabled.
  
  4. The system refuses to start without `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` when `SMARTCOMP_AUTH_ENABLED=true`.

- **No OpenAI API usage** – results are computed deterministically; any interpretation is provided by the Smart‑Comp library’s local summarisation and is never sent to OpenAI.

- **File retention** – Per‑job directories are kept for a configurable time‑to‑live (TTL). By default artefacts and intermediate files are removed **24 hours after job completion** via a background cleanup task. The TTL can be reduced or increased via an environment variable (`SMARTCOMP_JOB_TTL_HOURS`). Cancelled jobs remove their working directory immediately. See §4.3 for details.

- **Resource limits and concurrency** – To guard against denial‑of‑service through oversized uploads or runaway computations, the backend enforces several hard limits. Upload size is bounded by `SMARTCOMP_MAX_UPLOAD_BYTES` (default **100 MiB** per file and **500 MiB** for KW ZIP bundles). Requests exceeding the limit are rejected with **413 Payload Too Large**. Each job also inherits a **wall‑clock timeout** defined by `SMARTCOMP_JOB_TIMEOUT_SECONDS` (default **1 800 seconds**). Workers terminate jobs that exceed this duration and mark them **FAILED** with an appropriate error code. The number of concurrently running jobs is capped by the Celery worker concurrency (`CELERY_WORKER_CONCURRENCY`) and a global semaphore `SMARTCOMP_MAX_CONCURRENT_JOBS`. When the queue depth exceeds this limit the API responds with **429 Too Many Requests** to signal back‑pressure. Finally, the base working directory is configurable via `SMARTCOMP_STORAGE_ROOT`; the default is `/tmp/smartcomp`, but administrators may mount a persistent volume (e.g., `/var/lib/smartcomp`) and update the environment variable. All per‑job paths are created beneath this root, preventing path traversal and clarifying that `/tmp` is merely a default rather than a hard‑coded choice. These controls satisfy the SRS requirement to sanitize file uploads and limit file sizes while supporting concurrency.

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

The backend creates a per‑job working directory where inputs, cleaned copies, intermediate samples, logs and plots are stored. Without explicit cleanup these folders could accumulate on disk. The retention policy therefore has two layers:

- **Immediate cleanup on cancel/failure** – if a job enters a terminal state of **FAILED** or **CANCELLED**, the worker invokes a cleanup routine that removes the job’s working directory and any associated artefacts. This prevents partially processed data from lingering.

- **Time‑to‑live (TTL) for completed jobs** – completed jobs may be inspected by users for some time. A background task (Celery beat or a cron) scans `/tmp/smartcomp` and deletes directories whose `finishedAt` is older than a configurable TTL (default **24 hours**). The TTL is controlled by an environment variable `SMARTCOMP_JOB_TTL_HOURS`. Administrators can set this to `0` to disable retention entirely or to higher values (e.g., 168 hours for one week) when audits require longer persistence. The cleanup routine logs each deletion and exposes metrics for observability.

- **Configurable cleaning behaviour** – Smart‑Comp’s INI configuration has a `[clean] clean_all` flag that removes cleaned and sampled CSVs immediately after the CLI run. The backend surfaces this as `cleanAll` in the ConfigOverrides model (§8). When `cleanAll = true`, only the final result JSON/TXT and plot artefacts remain; all intermediate data are purged as soon as the job completes.

By combining these layers, the service avoids unbounded storage growth while still giving users reasonable time to download artefacts. Administrators should ensure the underlying filesystem or object store supports automatic expiration.

### 4.4 Observability

- The system must expose enough telemetry to operate reliably in production. In addition to per‑job logs and correlation IDs, the backend instruments internal state and publishes metrics.
  
  - **Structured logs** – per‑job logs (`tool.log` when `createLog=true`) are written in a JSON‑lines format with timestamp, level, `requestId` and `jobId` fields. They record key milestones (start, cleaning, sampling, permutation loops, finish) and any warnings or errors. Because these logs are included as artifacts, analysts can download them for troubleshooting, and they can also be shipped to a log aggregator for long‑term retention.
  
  - **Correlation IDs** – every HTTP request attaches or generates an `X‑Request‑Id` header. This identifier is echoed in structured error payloads (`requestId`) and injected into Celery task context so that traces across the API and worker can be correlated. When troubleshooting a job, operators can search for the `requestId` in application logs and metrics.
  
  - **Metrics** – when `SMARTCOMP_METRICS_ENABLED=true` (enabled by default), the application registers Prometheus collectors to export:
    
    - **HTTP metrics:** request duration, request/response size and status code buckets by endpoint.
    
    - **Job state gauges:** number of jobs by status (queued, running, completed, failed, cancelled) and current Redis queue depth.
    
    - **Job timing histograms:** end‑to‑end wall‑clock durations for each job type and per‑phase timing (cleaning, sampling, permutations).
    
    - **Worker concurrency:** number of active Celery workers and task execution time per worker.
    
    - **Cleanup counters:** number and age distribution of directories deleted by the TTL sweeper and cancellation routine.
    
    - **Upload statistics:** total bytes uploaded and number of uploads rejected because they exceeded `SMARTCOMP_MAX_UPLOAD_BYTES`.
  
    Metrics are exposed at a `/metrics` endpoint in the OpenMetrics format. This endpoint does not require authentication so that infrastructure (Prometheus or a similar collector) can scrape it even when API auth is enabled. Operators can visualise these metrics in dashboards and configure alerts on thresholds such as high error rates, long‑running jobs or disk usage.

### 4.5 Asynchronous worker and cancellation semantics

Smart‑Comp analyses can take tens of seconds or minutes depending on the dataset and permutation count. To keep HTTP requests responsive the backend offloads computation to a task queue (e.g., Celery with Redis broker). The worker pattern introduces additional state transitions and requires a robust cancellation story:

**Task lifecycle**

1. When the API receives `POST /api/jobs`, it writes a **Job** record to Redis with status **QUEUED**, persists the inputs on disk and enqueues a Celery task containing the job identifier and configuration.

2. A worker picks up the task and transitions the job to **RUNNING**, updating `startedAt`. During execution the task periodically updates `progress.percent`, `progress.step` and `message` fields in Redis. For bootstrap jobs these steps might include *cleaning*, *sampling*, *bootstrap loops* and *result writing*. For Kruskal–Wallis permutation jobs the steps include *loading groups*, *computing omnibus statistic* and *permutation loop*.

3. Upon completion, the worker writes `results.json`, assembles the artifact list, sets status **COMPLETED**, populates `finishedAt` and publishes a notification (optional). If an exception escapes, the worker records the error message/traceback under `error`, marks the job **FAILED** and triggers cleanup.

**Cancellation**

The API provides `POST /api/jobs/{jobId}/cancel` to request job cancellation. The semantics are:

- For **QUEUED** jobs the backend removes the entry from the queue (Celery’s `revoke` with `terminate=False`) before a worker starts processing. The job is marked **CANCELLED** and the working directory is removed.

- For **RUNNING** jobs the backend sets a cancellation flag on the job in Redis and calls `revoke(task_id, terminate=True, signal='SIGTERM')` on the Celery task. Termination will send a SIGTERM to the worker process; however Python code can intercept this gracefully. The Smart‑Comp worker periodically checks the cancellation flag between major computation loops (e.g., after each bootstrap iteration or permutation chunk). If detected, it raises a `JobCancelledError`, catches it at the top level, cleans up temporary files and marks the job **CANCELLED**. Clients polling the job status will observe `status: CANCELLED` with no results available.

- If the job is already **COMPLETED**, **FAILED** or **CANCELLED**, the API returns `409 Conflict`.

These semantics ensure cancellations are timely without abruptly killing Python threads in the middle of a NumPy routine. Long loops should be chunked (e.g., update progress every 1000 iterations) to provide responsive cancellation.

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

### 9.1 API examples

While the OpenAPI schema describes the shape of requests and responses, concrete examples help implementers test against the backend. The following examples illustrate typical payloads for each endpoint.

#### `GET /api/config/defaults`

Request (no body):

```http
GET /api/config/defaults HTTP/1.1
Host: smartcomp.example.com
Accept: application/json
```

Response:

```json
{
  "alpha": 0.05,
  "threshold": null,
  "bootstrapIterations": 10000,
  "permutationCount": 10000,
  "sampleSize": null,
  "descriptiveEnabled": true,
  "createLog": false,
  "plots": {
    "histogram": true,
    "boxplot": true,
    "kde": true
  }
}
```

#### `POST /api/jobs` (bootstrap single, Option A)

Multipart FormData fields:

```ini
jobType = BOOTSTRAP_SINGLE
config = {"alpha":0.05,"bootstrapIterations":5000,"sampleSize":1000}
file1  = (binary) contents of dataset.csv
```

A cURL example:

```bash
curl -X POST https://smartcomp.example.com/api/jobs \
  -F jobType=BOOTSTRAP_SINGLE \
  -F config='{"alpha":0.05,"bootstrapIterations":5000,"sampleSize":1000}' \
  -F file1=@/path/to/dataset.csv
```

Example response:

```json
{
  "jobId": "3b0d4f7e-7f9f-4b68-a1b8-6d6b6a3c2a1a"
}
```

#### `GET /api/jobs/{jobId}`

Request:

```http
GET /api/jobs/3b0d4f7e-7f9f-4b68-a1b8-6d6b6a3c2a1a HTTP/1.1
Host: smartcomp.example.com
Accept: application/json
```

Possible running response:

```json
{
  "jobId": "3b0d4f7e-7f9f-4b68-a1b8-6d6b6a3c2a1a",
  "jobType": "BOOTSTRAP_SINGLE",
  "status": "RUNNING",
  "createdAt": "2025-12-23T10:00:00Z",
  "startedAt": "2025-12-23T10:00:01Z",
  "progress": {
    "step": "Bootstrap iterations",
    "percent": 42.1,
    "message": "4200/10000"
  }
}
```

Completed response (single bootstrap):

```json
{
  "jobId": "3b0d4f7e-7f9f-4b68-a1b8-6d6b6a3c2a1a",
  "jobType": "BOOTSTRAP_SINGLE",
  "status": "COMPLETED",
  "createdAt": "2025-12-23T10:00:00Z",
  "startedAt": "2025-12-23T10:00:01Z",
  "finishedAt": "2025-12-23T10:02:30Z"
}
```

#### `GET /api/jobs/{jobId}/results`

For a completed single bootstrap job the results JSON may look like this:

```json
{
  "jobId": "…",
  "jobType": "BOOTSTRAP_SINGLE",
  "decision": {
    "significant": false,
    "alpha": 0.05,
    "pValue": 0.27
  },
  "metrics": {
    "p95": 124.3,
    "ciLower": 120.1,
    "ciUpper": 129.8
  },
  "descriptive": {
    "mean": 103.7,
    "median": 102.1,
    "std": 15.2,
    "sampleSize": 1000
  },
  "plots": [
    {"kind": "histogram", "artifactName": "hist_dataset.png"},
    {"kind": "boxplot",    "artifactName": "box_dataset.png"}
  ]
}
```

Similarly, a KW permutation result includes the omnibus statistic and per‑group statistics:

```json
{
  "jobId": "…",
  "jobType": "KW_PERMUTATION",
  "decision": {
    "alpha": 0.05,
    "pValue": 0.003
  },
  "omnibus": {
    "hStatistic": 12.34,
    "permutations": 10000
  },
  "groups": [
    {
      "groupName": "Control",
      "files": [
        {"fileName": "control.csv", "n": 950, "p95": 115.0, "median": 100.1}
      ]
    },
    {
      "groupName": "Variant",
      "files": [
        {"fileName": "variant.csv", "n": 970, "p95": 130.2, "median": 110.0}
      ]
    }
  ],
  "plots": [
    {"kind": "histogram", "artifactName": "hist_omnibus.png"}
  ]
}
```

#### `GET /api/jobs/{jobId}/artifacts`

Response example:

```json
{
  "jobId": "…",
  "artifacts": [
    {"name": "results.json",      "contentType": "application/json",  "sizeBytes": 2345, "createdAt": "2025-12-23T10:02:30Z"},
    {"name": "results.txt",       "contentType": "text/plain",        "sizeBytes": 1123, "createdAt": "2025-12-23T10:02:30Z"},
    {"name": "hist_dataset.png",  "contentType": "image/png",         "sizeBytes": 54321, "createdAt": "2025-12-23T10:02:31Z"},
    {"name": "tool.log",          "contentType": "text/plain",        "sizeBytes": 987,   "createdAt": "2025-12-23T10:02:31Z"}
  ]
}
```

Clients can fetch individual files by requesting `GET /api/jobs/{jobId}/artifacts/{artifactName}` and streaming the binary response.

## 10. Deployment blueprint

- Containers:
  
  - `frontend` (static build via nginx)
  
  - `api` (FastAPI + Uvicorn/Gunicorn)
  
  - `worker` (Celery/RQ worker)
  
  - `redis`

Additional runtime and storage considerations:

- **Storage path configuration** – All job inputs and artefacts are written to a per‑job folder under a configurable base path. By default this base path is `/tmp/smartcomp`, but administrators can override it via a `SMARTCOMP_STORAGE_PATH` environment variable to use a host‑mounted volume or an object store mount (e.g., an NFS share or S3‑backed bucket). When using filesystem storage, mount the same persistent volume to the path specified by `SMARTCOMP_STORAGE_PATH` so that both the API and worker containers can read and write job data. For cloud deployments an object storage bucket with appropriate credentials may replace the shared volume; this decouples storage from compute and enables horizontal scaling.

- **Authentication toggling** – The runtime behaviour of the API with respect to authentication is controlled via `SMARTCOMP_AUTH_ENABLED`. When set to `false` (the default), no authentication is enforced. When set to `true`, the API validates Google OAuth tokens; see §1.2 for details.

- **Worker concurrency** – Configure the number of Celery worker processes based on available CPU cores and expected dataset sizes. Excessive parallelism on large bootstrap or permutation jobs can exhaust memory. Administrators should tune `CELERY_WORKER_CONCURRENCY` in accordance with hardware resources and workload characteristics.

## 11. Dependencies and environment versions

Reproducible deployments require explicit version pins for all major components. The following versions are recommended as of **December 2025**; newer patch versions may be used when they are backwards compatible.

| Component              | Recommended version                                  | Notes                                                                                                                                        |
| ---------------------- | ---------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| **Python**             | `3.11`                                               | FastAPI and Celery support Python 3.11; align worker and API images.                                                                         |
| **Smart‑Comp library** | git commit or PyPI release used for this integration | Pin the Smart‑Comp dependency via `pip install smart-comp @ git+https://github.com/vturovets/smart-comp@<commit>` to avoid breaking changes. |
| **FastAPI**            | `0.127.0`                                            | Latest stable release (Dec 2025). Requires Pydantic 2.x.                                                                                     |
| **Uvicorn**            | `0.27.0`                                             | ASGI server; pair with FastAPI.                                                                                                              |
| **Pydantic**           | `2.5.2`                                              | Used by FastAPI for data validation.                                                                                                         |
| **Celery**             | `5.6.0`                                              | Stable distributed task queue (Nov 2025).                                                                                                    |
| **Redis** (server)     | `7.2`                                                | Acts as Celery broker and result store. Use `redis-py` `5.0.0`.                                                                              |
| **Node.js**            | `20.x LTS`                                           | Required to build the React frontend via Vite.                                                                                               |
| **npm**/`pnpm`         | `10.x`                                               | Use a lockfile to pin package versions.                                                                                                      |
| **React**              | `19.2.1`                                             | Latest minor release of React 19 (Dec 2025).                                                                                                 |
| **TypeScript**         | `5.3`                                                | Matches React 19 typing support.                                                                                                             |
| **Vite**               | `5.0`                                                | Build tool for the SPA.                                                                                                                      |
| **MUI (Material UI)**  | `6.x`                                                | Used for tables and UI components.                                                                                                           |

Create `requirements.txt` and `package.json` with these pins. Use Docker base images such as `python:3.11-slim` and `node:20-alpine` to ensure consistent environments. Continuous integration should run `pip install --no-cache-dir -r requirements.txt` and `npm ci` to honour the lock files.

### Backend requirements file

To support the web API and asynchronous worker, create a dedicated `backend/requirements.txt` alongside the Smart‑Comp source tree. This file should pin all Python dependencies required to serve the API and execute jobs. In addition to the core numerical stack (NumPy, pandas, SciPy, Matplotlib, diptest) provided by the Smart‑Comp library, it **must** include:

- **FastAPI** and **Uvicorn/Gunicorn** – to build and run the REST API. Use the versions listed in the table above (e.g., `fastapi==0.127.0`, `uvicorn==0.27.0`).

- **Pydantic 2.x** – for request/response models used by FastAPI.

- **Celery** and **redis‑py** – to offload long‑running jobs and communicate via Redis. Pin to `celery==5.6.0` and `redis==5.0.0`.

- **python‑dotenv** (or similar) – to load environment variables (e.g., `SMARTCOMP_STORAGE_PATH`, `SMARTCOMP_AUTH_ENABLED`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`) from an `.env` file during development.

- **google‑auth** and **google‑auth‑oauthlib** – when authentication is enabled, these libraries verify Google ID tokens. Include pins such as `google-auth==2.24.0` and `google-auth-oauthlib==1.1.0`. They may be marked as optional extras for deployments that enable Google OAuth.

Separating `backend/requirements.txt` from the Smart‑Comp library’s own `requirements.txt` allows maintainers to update backend dependencies without impacting the CLI. CI pipelines should run `pip install --no-cache-dir -r backend/requirements.txt` for the API and worker builds to ensure all packages are present.
