# Software Requirements Specification: Smart-Comp Web Application Backend

## 1. Introduction

### 1.1 Purpose

The Smart‑Comp project is a command‑line toolkit that compares the 95th percentile (P95) of latency or performance data sets. It automates data cleaning, bootstrap‑based hypothesis testing and optional narrative interpretation, allowing users to determine whether a regression or improvement is statistically significant[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/README.md#L3-L11). This specification describes the requirements to integrate the existing CLI as a **backend** for a web application. The web UI should provide a rich yet simple interface for all analytical flows supported by the CLI **except** invoking OpenAI’s language‑model API (LLM) for narrative interpretation[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/interpretation/engine.py#L12-L67). The existing command‑line interface remains available and acts as the underlying engine.

### 1.2 Scope

The web application will allow users to upload or select performance data (CSV files) and perform statistical analyses via the Smart‑Comp backend. Supported operations include:

- Comparing the P95 of a single dataset against a user‑specified threshold.

- Comparing P95 values between two datasets using bootstrap resampling.[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/README.md#L47-L67)

- Performing Kruskal–Wallis permutation tests across multiple groups of CSV files.[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/README.md#L69-L87)

- Running optional descriptive statistics and unimodality checks on the cleaned data.[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/analysis/descriptive.py#L18-L57)

- Displaying results, diagnostics and optional plots (histogram, boxplot, KDE) according to the configuration file.[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/analysis/descriptive.py#L45-L54)[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/analysis/descriptive.py#L63-L109)

The web UI will not call OpenAI’s API for narrative interpretations; instead, it may use the project’s local interpretation logic or allow users to download result files for offline interpretation[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/interpretation/engine.py#L12-L71).

### 1.3 Definitions and Acronyms

- **P95:** 95th percentile of a sample.

- **Bootstrap:** Resampling method for estimating confidence intervals.

- **Kruskal–Wallis Test:** Non‑parametric hypothesis test for comparing medians across multiple groups.

- **Permutation Test:** Statistical test using label shuffling to assess significance.

### 1.4 References

- Smart‑Comp README[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/README.md#L3-L25)

- CLI implementation and modules[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/cli/app.py#L34-L116)[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/stats/kruskal.py#L13-L39)

- Configuration file (config.txt)[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/config.txt#L2-L70)

## 2. Overall Description

### 2.1 Product Perspective

The web application is a new front‑end layer on top of the existing Smart‑Comp library. The CLI currently orchestrates the workflow: argument parsing, data cleaning, sampling, statistical testing and result reporting[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/cli/app.py#L119-L213). The web backend should reuse these Python modules directly (importing functions from `smart_comp` package) rather than spawning CLI processes where practical, to provide better error handling and performance. The configuration file (`config.txt`) will determine default values for thresholds, sample size, bootstrap iterations and output options[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/config.txt#L3-L39).

### 2.2 User Classes

- N/A.

### 2.3 Assumptions and Dependencies

- The server has Python with NumPy, pandas, SciPy, Matplotlib, diptest and pytest installed as per `requirements.txt`[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/README.md#L26-L29).

- Uploads are single‑column CSV files without headers; the system will enforce this requirement via validation[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/io/input.py#L16-L18).

- The OpenAI API key is optional and will not be used by the web interface; local interpretation should be applied instead.

## 3. Functional Requirements

### 3.1 Data Ingestion and Validation

1. **Single CSV Input:** The user may upload one CSV file containing a column of numeric values (latencies). The system shall:
   
   - Load the file into a DataFrame and verify it contains exactly one column[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/io/input.py#L16-L18).
   
   - Coerce values to numeric, drop non‑numeric or NaN rows, and enforce non‑negativity[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/io/input.py#L19-L22).
   
   - Enforce outlier thresholds and lower bounds defined in `[input]` of the configuration[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/io/input.py#L23-L28).
   
   - Persist a cleaned copy with `_cleaned.csv` suffix for reproducibility[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/io/input.py#L29-L35).
   
   - Optionally log the cleaning process when `[output] create_log = True`[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/config.txt#L20-L23).

2. **Dual CSV Input:** When two files are provided, the same validation and cleaning shall be applied separately to each file. A warning is issued if either file has fewer than the minimum sample size configured (`minimum sample size`)[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/validation/checks.py#L15-L29).

3. **Folder Input for KW‑Permutation:** For the Kruskal–Wallis test, users specify a folder and pattern to load multiple CSV groups. The system shall:
   
   - Verify the folder exists and contains at least two matching files[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/io/folder_loader.py#L47-L67).
   
   - Optionally choose a column by name or index; otherwise auto‑detect the first numeric column[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/io/folder_loader.py#L71-L81).
   
   - Clean each series by removing non‑numeric, NaN and negative values, recording the counts dropped[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/io/folder_loader.py#L98-L110).
   
   - Compute per‑file median, P95 and sample size metadata for reporting[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/io/folder_loader.py#L113-L133).

4. **Ratio‑Scale Validation:** After cleaning, the system checks that data values meet ratio‑scale requirements (numeric, non‑negative and not purely binary)[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/validation/checks.py#L34-L79). If invalid, an error is displayed and the analysis is halted.

### 3.2 Descriptive Analysis

1. **Summary Statistics:** If `[descriptive analysis] required = True` in the config, the system shall compute selected descriptive statistics (mean, median, min, max, sample size, standard deviation, skewness, mode, empirical P95) based on flags in `[descriptive analysis]`[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/analysis/descriptive.py#L18-L44).

2. **Diagram Generation:** When diagram flags are enabled in `[descriptive analysis]` and corresponding `[output]` flags are true, the system shall generate and save:
   
   - Histograms with lines marking mean, median and P95; optional log‑scale axes[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/analysis/descriptive.py#L63-L101).
   
   - Boxplots[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/analysis/descriptive.py#L111-L118).
   
   - Kernel density estimate (KDE) plots with detected peaks, used for unimodality analysis[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/analysis/descriptive.py#L141-L152).

3. **Unimodality Check:** If `unimodality_test_enabled` is true, the system shall run a dip test, compute a bimodality coefficient and count peaks using KDE. It reports a warning if the distribution is not unimodal (peak count ≠ 1, dip p‑value ≤ 0.05, or bimodality coefficient ≥ 0.55)[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/analysis/descriptive.py#L121-L138).

4. **Extended Report:** When `get extended report` is enabled, the unimodality analysis results are appended to the descriptive section[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/analysis/descriptive.py#L51-L56).

### 3.3 Hypothesis Testing

1. **P95 vs Threshold:** For a single cleaned dataset, the system shall perform bootstrap sampling (`bootstrapping iterations` iterations) of size `sample` and compute the 95th percentile. It calculates a confidence interval and compares it to the threshold defined in `[test]`. The result includes P95 estimate, confidence interval, margin of error, p‑value, significance flag and sample size[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/stats/bootstrap.py#L95-L119). If the threshold lies outside the confidence interval, a significant difference is detected[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/stats/bootstrap.py#L95-L119).

2. **P95 vs P95:** For two cleaned datasets, the system shall bootstrap both, compute P95 samples and compare them. It determines whether the confidence intervals overlap; if not, the difference is automatically significant. Otherwise it calculates a p‑value by analysing the difference distribution[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/stats/bootstrap.py#L26-L59). Result fields mirror the single‑sample case but include both datasets’ statistics and margins of error[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/stats/bootstrap.py#L26-L59).

3. **Result Saving:** Results are rendered as key‑value lines. Fields to include or omit are controlled by `[output]` flags (e.g., `p95_1`, `p95_2`, `ci lower p95_1`)[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/io/output.py#L41-L48). Users can download the results as a text file or view them in the browser.

4. **Interpretation:** The CLI supports narrative interpretation using an OpenAI GPT‑4 model or a local fallback method[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/interpretation/engine.py#L12-L71). The web UI must **not** call the GPT API; instead it may:
   
   - Use the **simple_local_interpretation** function to produce a Markdown summary with recommendations[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/interpretation/engine.py#L74-L135), or
   
   - Provide the raw results and let users download them for offline analysis.

### 3.4 Kruskal–Wallis Permutation Test

1. **Group Loading:** The system loads multiple CSV files as described in §3.1.3 and extracts cleaned duration arrays and metadata[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/io/folder_loader.py#L136-L182).

2. **Permutation Logic:** Using `kruskal_permutation_test`, the system computes the observed Kruskal–Wallis H statistic and runs a label‑shuffle permutation test for `permutations` iterations with an optional random seed[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/stats/kruskal.py#L43-L97). It returns the permutation distribution and p‑value. The p‑value is the fraction of permutations with an H statistic at least as extreme as the observed one[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/stats/kruskal.py#L43-L97).

3. **Reporting:** The test prints a console table listing each group’s file name, sample size, median, P95, and counts of dropped rows[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/cli/kw_permutation.py#L127-L161). It also reports the total sample size, observed H statistic, permutation p‑value, tie correction and group sizes[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/cli/kw_permutation.py#L163-L182). In quiet mode, results are condensed into a single line.[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/cli/kw_permutation.py#L111-L124)

4. **Output Files:** Users may specify a JSON report path and/or a summary CSV path. The system writes the permutation results and per‑group summary to these files[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/io/output.py#L65-L96).

### 3.5 Configuration Management

1. **Default Configuration:** The system reads `config.txt` by default and falls back to a project‑root copy if a path is not provided[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/config/loader.py#L25-L37). If the file is missing or unparsable, an error is displayed and execution halts[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/config/loader.py#L25-L41).

2. **Custom Configurations:** Administrators can edit `config.txt` to adjust alpha level, bootstrap iterations, sample size, threshold, cleaning guard‑rails, output flags and interpretation settings[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/config.txt#L3-L70).

3. **Configuration in Web UI:** The web UI should expose key tunables (e.g., threshold, sample size, alpha, number of permutations) as user‑editable fields. Less frequently changed settings may remain hidden behind an advanced settings panel. Changes made via the UI should update the backend’s in‑memory ConfigParser without modifying the file on disk unless saved by an administrator.

### 3.6 Logging and Clean‑Up

1. **Logging:** When `[output] create_log = True`, the backend writes a detailed log to `tool.log` using Python’s logging module[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/logging/logger.py#L8-L31). The web interface should provide a way to download or view recent logs.

2. **Temporary Files:** Cleaned and sampled CSV files are deleted at the end of a run if `[clean] clean_all = True`[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/cli/app.py#L292-L293). The backend must manage these temporary files, ensuring they are removed after the request completes.

### 3.7 Error Handling

1. The system shall validate all inputs and configurations; if invalid or insufficient (e.g., sample size too small, missing threshold), it returns an informative error message to the user rather than a stack trace[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/cli/app.py#L130-L143)[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/validation/checks.py#L15-L30).

2. When an exception occurs during analysis, the system logs the error (if logging is enabled) and returns an error response to the web UI. Error messages should not expose internal file paths or sensitive data.

## 4. Non‑Functional Requirements

- **Performance:** Statistical computations should complete within a reasonable time (seconds to minutes). Adjustable parameters like `bootstrapping iterations` and `sample` size allow administrators to balance precision versus speed[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/config.txt#L3-L12).

- **Scalability:** The backend must handle concurrent requests. Resource‑intensive operations (bootstrapping and permutation tests) should execute asynchronously or on worker threads to avoid blocking the web server.

- **Usability:** The web UI should guide users through data upload, configuration and result interpretation with clear forms and tooltips. Results should be presented with headings, key statistics, optional plots and downloadable reports.

- **Reliability:** Input validation ensures only proper CSV files are processed. Tests on library functions are included in the repository to aid maintenance[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/README.md#L108-L116).

- **Maintainability:** The backend should use the existing modular functions (`smart_comp.io`, `analysis`, `sampling`, `stats`, `validation`) to maintain consistency with the CLI. Code should be documented and follow Python best practices.

- **Security:** The web application should sanitize file uploads and limit file sizes. It must not expose the OpenAI API key or call the OpenAI API unless explicitly enabled in a secure configuration.

## 5. Use‑Case Scenarios

1. **Single Dataset Comparison:**
   
   - User uploads a CSV file of latency values and enters a threshold (or uses the default from config).
   
   - The system cleans the data and validates ratio‑scale requirements[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/io/input.py#L16-L28)[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/validation/checks.py#L34-L79).
   
   - It performs optional descriptive analysis and unimodality checks based on configuration[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/analysis/descriptive.py#L18-L57).
   
   - It runs bootstrap resampling and compares the sample P95 to the threshold, returning P95 estimate, confidence interval, margin of error and p‑value[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/stats/bootstrap.py#L95-L119).
   
   - Results and optional plots are presented; the user can download a text report.

2. **Two‑Dataset Comparison:**
   
   - User uploads two CSV files for comparison.
   
   - Both files are cleaned and validated; warnings appear if sample sizes are below the minimum[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/validation/checks.py#L15-L29).
   
   - Optional descriptive statistics and unimodality tests are run[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/analysis/descriptive.py#L18-L57).
   
   - Bootstrap sampling estimates P95 for each dataset; the system compares them and computes p‑value and margins of error[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/stats/bootstrap.py#L26-L59).
   
   - Results and plots are displayed; users can download reports.

3. **Kruskal–Wallis Permutation Test:**
   
   - User selects a folder containing multiple CSV files and specifies permutation count and seed.
   
   - The system loads, cleans and summarises each file[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/io/folder_loader.py#L136-L182).
   
   - It computes the Kruskal–Wallis H statistic and runs the permutation test[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/stats/kruskal.py#L43-L97).
   
   - The table of group metrics and omnibus statistics is shown; optional JSON and CSV reports can be downloaded[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/io/output.py#L65-L96).

## 6. Future Enhancements (Optional)

- **LLM‑Driven Interpretation:** Though not part of the current web release, the backend could later support ChatGPT‑based interpretations by securely storing an API key and adding a toggle in the UI. This would use the GPT interface defined in `smart_comp/interpretation/engine.py`[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/interpretation/engine.py#L12-L67).

- **Multi‑Tenant Configuration:** Allow multiple saved configurations per user or project to support different performance environments.

- **API Endpoints:** Expose REST endpoints for automation, enabling integration with CI pipelines.

## 7. Open Issues / Clarifications

1. **Authentication and Authorization:** The specification does not define user authentication or roles. Should the web UI support user accounts with permissions? - Negative. 

2. **File Retention:** How long should cleaned and sampled CSV files be retained on the server after analysis? The CLI currently deletes them immediately when `clean_all = True`[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/cli/app.py#L292-L293). - The same is applicable for the web app.

3. **Concurrency Model:** The performance implications of running bootstrap and permutation tests concurrently require clarification (e.g., asynchronous tasks, job queue). - preferably run asynchronously.
