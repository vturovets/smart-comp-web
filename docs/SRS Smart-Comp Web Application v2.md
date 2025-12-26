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

1. **Single Dataset Comparison (see also Annex 1, section A):**
   
   - User uploads a CSV file of latency values and enters a threshold (or uses the default from config).
   
   - The system cleans the data and validates ratio‑scale requirements[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/io/input.py#L16-L28)[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/validation/checks.py#L34-L79).
   
   - Optional descriptive statistics and unimodality tests are run[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/analysis/descriptive.py#L18-L57).
   
   - It runs bootstrap resampling and compares the sample P95 to the threshold, returning P95 estimate, confidence interval, margin of error and p‑value[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/stats/bootstrap.py#L95-L119).
   
   - Results and optional plots are presented; the user can download a text report.

2. **Two‑Dataset Comparison (see also Annex 1, section B):**
   
   - User uploads two CSV files for comparison.
   
   - Both files are cleaned and validated; warnings appear if sample sizes are below the minimum[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/validation/checks.py#L15-L29).
   
   - Optional descriptive statistics and unimodality tests are run[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/analysis/descriptive.py#L18-L57).
   
   - Bootstrap sampling estimates P95 for each dataset; the system compares them and computes p‑value and margins of error[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/stats/bootstrap.py#L26-L59).
   
   - Results and plots are displayed; users can download reports.

3. Descriptive analysis and plot (see also Annex 1, section C)
   
   1. User uploads a CSV file of latency values
   
   2. The system run the analysis according to the [descriptive analysis] section of config.txt
   
   3. Results and plots (if requested) are displayed; users can download reports.

4. **Kruskal–Wallis Permutation Test (see also Annex 1, section D):**
   
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

# Annex 1: The detailed flow description

# Flows in the *smart‑comp* codebase

This section summarises the flows inside the `smart‑comp` toolkit. Each flow describes the major functions executed, the inputs/outputs and key configuration options. These flows can be used as the basis for a web user interface.

## A. Bootstrap hypothesis test for a **single dataset**

**Goal:** compare the 95‑th percentile (P95) of a dataset against a user‑defined threshold using bootstrap resampling.

**Key functions and flow:**

1. **Read and clean data.**
   
   - `run_bootstrap_single_sample_test(sample_file_path1, config, logger)` orchestrates the single‑sample flow. It reads the selected CSV file (first column interpreted as numeric) using `get_data_frame_from_csv` and determines the sample size[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/stats/bootstrap.py#L152-L154).

2. **Configuration parameters.**
   
   - The *test* section of `config.txt` defines significance level (`alpha`), number of bootstrap iterations, target sample size and comparison threshold[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/config.txt#L4-L11). These values are retrieved inside `run_bootstrap_single_sample_test` using the `ConfigParser` API[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/stats/bootstrap.py#L124-L128).

3. **Bootstrap resampling.**
   
   - `bootstrap_percentile(file_path, percentile=95, iterations)` draws bootstrap samples (with replacement) from the dataset. For each bootstrap sample, it calculates the 95‑th percentile and returns an array of resampled P95 values[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/stats/bootstrap.py#L16-L24).

4. **Compare bootstrapped P95s to threshold.**
   
   - `compare_p95_to_threshold(p95_samples, threshold, sample_size, alpha)` calculates the confidence interval for the bootstrapped P95 distribution. If the threshold lies outside the confidence interval, the p‑value is set to 0 and the difference is automatically marked as significant; otherwise the p‑value is computed as the proportion of bootstrap differences above zero[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/stats/bootstrap.py#L95-L120). The function returns the mean P95, threshold, confidence interval, margin of error and a boolean indicating a significant difference[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/stats/bootstrap.py#L95-L120).

5. **Packaging results.**
   
   - `run_bootstrap_single_sample_test` calls `bootstrap_percentile`, runs the threshold comparison and then merges the test statistics with a top‑level dictionary containing the operation name (`"comparing P95 to the threshold"`)[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/stats/bootstrap.py#L130-L149). If configured to output the empirical (non‑bootstrap) P95, it calculates it and stores it in the result[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/stats/bootstrap.py#L139-L146). The result can be printed or written to file via `save_results`.

**Outcome:** a dictionary with fields such as *p95*, *threshold*, *confidence interval*, *p‑value*, *alpha*, *sample size* and *significant difference* is produced. These values drive the UI elements (e.g., charts, p‑value display and decision messaging).

## B. Bootstrap hypothesis test for **two datasets**

**Goal:** compare the 95‑th percentiles of two datasets using bootstrap resampling.

**Key functions and flow:**

1. **Initial checks and data cleaning.**
   
   - The CLI or UI calls `run_bootstrap_test(sample_file_path1, sample_file_path2, config, logger)`. Before this, the CLI performs cleaning and ratio‑scale validation on both files, but in a web UI these checks would be part of data upload and validation steps.

2. **Configuration parameters.**
   
   - The significance level (`alpha`), number of bootstrap iterations and sample size are read from the *test* section of the configuration[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/stats/bootstrap.py#L62-L66).

3. **Bootstrap sampling.**
   
   - `bootstrap_percentile` is invoked separately for each dataset to produce two arrays of bootstrapped P95 values[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/stats/bootstrap.py#L70-L71).

4. **Compare P95 distributions.**
   
   - `compare_p95s(p95_sample1, p95_sample2, sample_size, alpha)` computes the confidence intervals for each P95 distribution and checks whether they overlap. If they do not overlap, the p‑value is set to zero and the difference is considered significant; otherwise, a two‑tailed p‑value is computed based on the difference distribution[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/stats/bootstrap.py#L26-L39). It returns the mean P95s, confidence intervals, margins of error, p‑value, alpha, sample size and a boolean flag indicating significant difference[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/stats/bootstrap.py#L40-L59).

5. **Merge additional fields.**
   
   - The top‑level dictionary stores the operation name (`"comparing two P95s"`) and optionally the empirical P95s and data source paths if those outputs are enabled in the configuration[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/stats/bootstrap.py#L76-L89). The complete result is returned via `_merge_fields`[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/stats/bootstrap.py#L157-L160) and can be displayed or saved using the output helper.

**Outcome:** the UI should display both estimated P95s, their confidence intervals and p‑value, and highlight whether the difference is statistically significant. Users can also download the underlying bootstrapped distributions or empirical values when configured.

## C. Descriptive analysis and plots

**Goal:** compute summary statistics and generate plots for a dataset before running hypothesis tests.

**Key functions and flow:**

1. **Run descriptive analysis.**
   
   - `run_descriptive_analysis(cleaned_file, config, logger)` reads the cleaned CSV (first column as numeric) and creates a results dictionary containing the operation name (`"descriptive analysis"`) and the base filename[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/analysis/descriptive.py#L18-L25).
   
   - It adds summary statistics only if the corresponding flags in the *descriptive analysis* section of the configuration are set. Supported statistics include mean, median, minimum, maximum, sample size, standard deviation, skewness, mode and empirical P95[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/analysis/descriptive.py#L26-L44).

2. **Generate plots.**
   
   - If `diagraming` is enabled in the configuration, histogram and boxplot generation functions are called based on flags in the *output* section[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/analysis/descriptive.py#L45-L49).
   
   - `_generate_histogram(df, base_filename, config)` draws a histogram with optional log‑scale axis. It overlays vertical lines for the mean, median and empirical P95 and saves the figure as `histogram_<filename>.png`[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/analysis/descriptive.py#L63-L107). Log scale is applied only when requested and all values are positive; otherwise, a warning is issued and the scale remains linear[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/analysis/descriptive.py#L84-L99).
   
   - `_generate_boxplot(df, base_filename, config)` produces a horizontal boxplot and saves it as `boxplot_<filename>.png`[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/analysis/descriptive.py#L111-L118).

3. **Unimodality and extended report.**
   
   - If `get extended report` is enabled, `run_unimodality_analysis` is invoked. It computes a Gaussian kernel density estimate of the data using the configured bandwidth, detects peaks, performs Hartigan’s Dip test and calculates the bimodality coefficient[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/analysis/descriptive.py#L170-L191). The results include the number of peaks, p‑value from the dip test and bimodality coefficient; a KDE plot highlighting peaks may be generated when `kde_plot` is enabled[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/analysis/descriptive.py#L201-L204).
   
   - `check_unimodality_kde` provides a high‑level check that prints a warning when the data is not unimodal[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/analysis/descriptive.py#L121-L138). In a web UI, this check can prevent running bootstrap tests on multi‑modal distributions.

**Outcome:** the descriptive analysis flow yields a dictionary of selected summary statistics and optionally saves histogram, boxplot and KDE images. These values and images should be displayed in the UI and used to inform the user about data distribution (e.g., skewness, multimodality) before running inferential tests.

## D. Kruskal–Wallis permutation test for **multi‑group comparisons**

**Goal:** compare medians or distributions across multiple groups when normality assumptions are violated. The test uses the Kruskal–Wallis H statistic and obtains a p‑value via permutation.

**Key functions and flow:**

1. **Load multiple groups.**
   
   - `run_kw_permutation_command(args, config, logger)` is the main entry point. It calls `load_group_durations(folder, pattern, column)` to read multiple CSV files in a folder matching a glob pattern and to select a column (default first numeric). Each file yields a cleaned numeric array and a `GroupMetadata` entry capturing the file name, sample size, median, P95 and counts of dropped invalid values[raw.githubusercontent.com](https://raw.githubusercontent.com/vturovets/smart-comp/HEAD/smart_comp/io/folder_loader.py#:~:text=def%20load_group_durations%28%20folder%3A%20Union,latency%20groups%20for%20statistical%20analysis).

2. **Run Kruskal–Wallis permutation test.**
   
   - The arrays are passed to `kruskal_permutation_test(arrays, iterations, rng)`. Internally, `compute_kruskal_h` ranks all data, computes the H statistic with tie corrections and records group sizes and total N[raw.githubusercontent.com](https://raw.githubusercontent.com/vturovets/smart-comp/HEAD/smart_comp/stats/kruskal.py#:~:text=def%20compute_kruskal_h%28groups%3A%20Sequence%5Bnp.ndarray%5D%29%20,statistic%20for%20the%20provided%20groups). The permutation test shuffles group labels for a specified number of iterations, recomputes the H statistic for each permutation and calculates the p‑value as the proportion of permuted H statistics at least as extreme as the observed one[raw.githubusercontent.com](https://raw.githubusercontent.com/vturovets/smart-comp/HEAD/smart_comp/stats/kruskal.py#:~:text=def%20kruskal_permutation_test%28%20groups%3A%20Sequence%5Bnp.ndarray%5D%2C%20,Wallis%20H%20statistic).
   
   - A random number generator is initialised with the provided seed to make results reproducible[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/cli/kw_permutation.py#L35-L40).

3. **Assemble result and output.**
   
   - `_assemble_result` converts each `GroupMetadata` object into a plain dictionary and constructs an `omnibus` section containing the total sample size, observed H statistic, permutation p‑value, number of permutations, tie correction and group sizes. It also adds the seed when provided[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/cli/kw_permutation.py#L71-L95).
   
   - The result is optionally written to a JSON report and a summary CSV via `write_kw_permutation_reports`[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/cli/kw_permutation.py#L47-L58). The JSON report contains both the `groups` list and the `omnibus` dictionary, while the CSV summarises each group’s metadata (file name, n, median, P95 and dropped counts)[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/io/output.py#L65-L135).
   
   - When `quiet` is not set, `_render_console_output` prints a formatted table showing each group’s statistics followed by overall test statistics and parameters. In a web UI, this formatted output translates directly into a table and summary section for users[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/cli/kw_permutation.py#L127-L188).

**Outcome:** the permutation test flow outputs per‑group summary statistics along with the observed H statistic and permutation p‑value. The UI should display the group table, the p‑value and test parameters, and allow users to download the JSON report and summary CSV.

## E. Updating configuration settings

The toolkit’s behaviour is driven by a plain‑text file (`config.txt`) that defines parameters for hypothesis tests, data cleaning, output fields and descriptive analysis options[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/config.txt#L4-L70). There are no programmatic “update” functions; the CLI loads configuration via `load_config`, which resolves a provided path or defaults to `config.txt` in the project root[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/smart_comp/config/loader.py#L11-L30). To update settings via a web UI:

1. **Read the current configuration.** Use a parser (e.g., Python’s `ConfigParser`) to read `config.txt`. Expose each section (*test*, *input*, *output*, *descriptive analysis*, *clean*, *interpretation*) as editable fields. Show defaults such as significance level, number of bootstrap iterations, sample size, threshold, outlier guard rails and flags for generating plots[github.com](https://github.com/vturovets/smart-comp/blob/HEAD/config.txt#L4-L70).

2. **Modify values.** Allow users to adjust numeric parameters (e.g., `alpha`, `bootstrapping iterations`), boolean switches (e.g., whether to generate histograms or run unimodality tests) and textual values (e.g., bandwidth selection for KDE). For values like the OpenAI API key, hide sensitive input when editing.

3. **Persist the new configuration.** After validation, write the modified values back to the `config.txt` file using `configparser.ConfigParser().write()` or by assembling the file manually. Since the toolkit always reads configuration at runtime using `load_config`, changes saved to the file take effect on the next invocation.

4. **Apply settings in the UI.** When performing analyses from the UI, pass the updated configuration to the corresponding functions (`run_bootstrap_single_sample_test`, `run_bootstrap_test`, `run_descriptive_analysis`, `run_kw_permutation_command`). The UI should disable or hide controls for operations that are turned off (e.g., hide histogram options when `histogram` is false).

**Outcome:** by providing a configuration editor in the UI, users can customise the tool’s behaviour (e.g., significance level, number of bootstraps, whether to generate plots) without editing the file manually. Because the code has no dedicated update function, the UI must handle reading and rewriting the config file.
