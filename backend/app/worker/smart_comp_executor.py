from __future__ import annotations

import configparser
import json
import logging
import os
import shutil
import warnings
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

os.environ.setdefault("MPLBACKEND", "Agg")

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
from scipy.stats import rankdata
from smart_comp.analysis import run_descriptive_analysis
from smart_comp.io import save_results, validate_and_clean
from smart_comp.io.folder_loader import (
    GroupMetadata,
    _clean_duration_series,
    _select_column,
    _summarise_group,
)
from smart_comp.logging import setup_logger
from smart_comp.sampling import get_autosized_sample
from smart_comp.stats.bootstrap import compare_p95s, compare_p95_to_threshold
from smart_comp.utils import sanitize_for_json
from smart_comp.validation import validate_ratio_scale

from app.core.storage import JobPaths

ProgressCallback = Callable[[float, str, str | None], None]
GuardCallback = Callable[[], None]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExecutionResult:
    normalized: dict[str, Any]
    raw: dict[str, Any]


class SmartCompExecutor:
    """Run Smart-Comp analyses for a job and persist artifacts."""

    def __init__(
        self,
        job_id: str,
        job_type: str,
        job_paths: JobPaths,
        payload: dict[str, Any],
        *,
        progress_cb: ProgressCallback,
        guard_cb: GuardCallback,
        random_seed: int = 42,
    ) -> None:
        self.job_id = job_id
        self.job_type = job_type
        self.job_paths = job_paths
        self.payload = payload
        self.progress_cb = progress_cb
        self.guard_cb = guard_cb
        self.random_seed = random_seed

        self.config = self._build_config()
        self.logger = None
        self.warnings: list[str] = []

    def run(self) -> ExecutionResult:
        self._set_seed()
        with self._working_directory(self.job_paths.output_dir):
            self.logger = setup_logger(self.config)
            self._ensure_log_placeholder()
            if self.job_type == "KW_PERMUTATION":
                result = self._run_kw_permutation()
            else:
                result = self._run_bootstrap_flows()

            self._write_results(result)
            self._move_plots()
            return result

    def _run_bootstrap_flows(self) -> ExecutionResult:
        self._update_progress(5, "prepare", "Preparing inputs")
        self.guard_cb()

        descriptive_enabled = bool(self.payload.get("descriptiveEnabled", True))
        plots_requested = any(self._plot_flags().values())

        paths = self._prepare_input_files()
        cleaned = self._clean_inputs(paths)
        self._update_progress(25, "clean", "Inputs cleaned")
        self.guard_cb()

        self._apply_effective_sample_size(cleaned)

        descriptive_results: dict[str, Any] = {}
        if descriptive_enabled or self.job_type == "DESCRIPTIVE_ONLY":
            descriptive_results = self._run_descriptive(cleaned, plots_requested)
            self._update_progress(40, "descriptive", "Descriptive analysis complete")
            self.guard_cb()

        if self.job_type == "DESCRIPTIVE_ONLY":
            normalized = self._normalize_descriptive(descriptive_results, plots_requested)
            raw = {"descriptive": descriptive_results}
            return ExecutionResult(normalized=normalized, raw=raw)

        samples = self._sample_inputs(cleaned)
        self._update_progress(50, "sampling", "Sampling ready")
        self.guard_cb()

        bootstrap_iterations = int(self.payload.get("bootstrapIterations") or 5)
        if self.job_type == "BOOTSTRAP_SINGLE":
            bootstrap_data = self._bootstrap_single(samples[0], bootstrap_iterations)
        else:
            bootstrap_data = self._bootstrap_dual(samples, bootstrap_iterations)

        self._update_progress(85, "bootstrap", "Bootstrap complete")
        raw = {"bootstrap": bootstrap_data}
        if descriptive_results:
            raw["descriptive"] = descriptive_results

        normalized = self._normalize_bootstrap(bootstrap_data, descriptive_results, plots_requested)
        return ExecutionResult(normalized=normalized, raw=raw)

    def _run_kw_permutation(self) -> ExecutionResult:
        self._update_progress(10, "prepare", "Preparing KW groups")
        self.guard_cb()
        groups_payload = self.payload.get("kwGroups") or []
        if not groups_payload:
            raise ValueError("KW permutation requires kwGroups in payload.")

        group_arrays: list[np.ndarray] = []
        file_metadata: dict[str, list[GroupMetadata]] = {}
        aggregated_metadata: list[GroupMetadata] = []

        lower = float(self.payload.get("outlierLowerBound") or 0)
        upper_raw = self.payload.get("outlierUpperBound")
        upper = float(upper_raw) if upper_raw is not None else None

        for group_name in groups_payload:
            arrays, file_entries, group_meta = self._load_kw_group(group_name, lower, upper)
            group_arrays.append(np.concatenate(arrays))
            file_metadata[group_name] = file_entries
            aggregated_metadata.append(group_meta)
            self.guard_cb()

        iterations = int(self.payload.get("permutationCount") or 5)
        permutation_result = self._permutation_with_guard(group_arrays, iterations)
        report_path = self.job_paths.output_dir / "kw_report.json"
        summary_path = self.job_paths.output_dir / "kw_summary.csv"

        # Persist reports
        from smart_comp.io.output import write_kw_permutation_reports

        write_kw_permutation_reports(
            aggregated_metadata,
            permutation_result,
            report_path=report_path,
            summary_csv_path=summary_path,
        )

        raw = {
            "kw_permutation": {
                "p_value": permutation_result.get("p_value"),
                "iterations": permutation_result.get("iterations"),
                "observed_h": permutation_result.get("observed", {}).get("h_statistic"),
                "tie_correction": permutation_result.get("observed", {}).get("tie_correction"),
            },
        }
        normalized = self._normalize_kw(permutation_result, file_metadata)
        self._update_progress(90, "finalize", "KW artifacts ready")
        return ExecutionResult(normalized=normalized, raw=raw)

    def _prepare_input_files(self) -> list[Path]:
        inputs: list[Path] = []
        for name in ("file1.csv", "file2.csv"):
            source = self.job_paths.input_dir / name
            if source.exists():
                target = self.job_paths.output_dir / name
                shutil.copy(source, target)
                inputs.append(target)
        if not inputs:
            raise FileNotFoundError("No input CSVs found for job.")
        return inputs

    def _clean_inputs(self, inputs: Sequence[Path]) -> list[Path]:
        cleaned: list[Path] = []
        for path in inputs:
            cleaned_path = Path(validate_and_clean(str(path), self.config, self.logger))
            if not validate_ratio_scale(str(cleaned_path), self.config, self.logger):
                message = f"Ratio scale validation failed for {path.name}"
                self.warnings.append(message)
                if self.logger:
                    self.logger.warning(message)
            cleaned.append(cleaned_path)
            self.guard_cb()
        return cleaned

    def _apply_effective_sample_size(self, cleaned: Sequence[Path]) -> None:
        sample_size_override = self.payload.get("sampleSize")
        if sample_size_override is not None:
            sample_size = int(sample_size_override)
        else:
            lengths = [self._count_rows(path) for path in cleaned]
            sample_size = min(lengths) if lengths else 0
        sample_size = max(sample_size, 1)
        self.config.set("test", "sample", str(sample_size))
        self.config.set("input", "minimum sample size", str(sample_size))

    def _run_descriptive(self, cleaned: Sequence[Path], plots_requested: bool) -> dict[str, Any]:
        results: dict[str, Any] = {}
        for idx, path in enumerate(cleaned, start=1):
            key = f"dataset{idx}"
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                results[key] = run_descriptive_analysis(str(path), self.config, self.logger)
            if plots_requested:
                self._flag_plot_outputs()
            self.guard_cb()
        return results

    def _sample_inputs(self, cleaned: Sequence[Path]) -> list[Path]:
        if len(cleaned) == 1:
            sample = get_autosized_sample(str(cleaned[0]), None, self.config.getint("test", "sample"))
            return [Path(sample)]
        sample1, sample2 = get_autosized_sample(
            str(cleaned[0]),
            str(cleaned[1]),
            self.config.getint("test", "sample"),
        )
        return [Path(sample1), Path(sample2)]

    def _bootstrap_single(self, sample_path: Path, iterations: int) -> dict[str, Any]:
        alpha = float(self.payload.get("alpha") or self.config.getfloat("test", "alpha"))
        threshold = float(
            self.payload.get("threshold") or self.config.get("test", "threshold", fallback="0")
        )
        samples = self._bootstrap_percentile(sample_path, iterations, 95)
        return compare_p95_to_threshold(
            samples,
            threshold,
            self._count_rows(sample_path),
            alpha=alpha,
        )

    def _bootstrap_dual(self, samples: Sequence[Path], iterations: int) -> dict[str, Any]:
        alpha = float(self.payload.get("alpha") or self.config.getfloat("test", "alpha"))
        sample1 = self._bootstrap_percentile(samples[0], iterations, 95)
        sample2 = self._bootstrap_percentile(samples[1], iterations, 95)
        sample_size = min(self._count_rows(samples[0]), self._count_rows(samples[1]))
        return compare_p95s(sample1, sample2, sample_size, alpha=alpha)

    def _bootstrap_percentile(self, file_path: Path, iterations: int, percentile: int) -> np.ndarray:
        data = pd.read_csv(file_path, header=None).iloc[:, 0].to_numpy()
        n = data.size
        results = np.empty(iterations, dtype=float)
        for idx in range(iterations):
            self.guard_cb()
            sample = np.random.choice(data, n, replace=True)
            results[idx] = float(np.percentile(sample, percentile))
            self._update_loop_progress("bootstrap", idx + 1, iterations, start=55, span=25)
        return results

    def _load_kw_group(
        self,
        group_name: str,
        lower_threshold: float,
        upper_threshold: float | None,
    ) -> tuple[list[np.ndarray], list[GroupMetadata], GroupMetadata]:
        group_dir = self.job_paths.input_dir / group_name
        if not group_dir.exists():
            raise FileNotFoundError(f"Group directory missing: {group_dir}")
        files = sorted(group_dir.glob("*.csv"))
        if not files:
            raise ValueError(f"No CSV files found for KW group {group_name}")

        arrays: list[np.ndarray] = []
        file_entries: list[GroupMetadata] = []
        dropped_non_numeric = 0
        dropped_negative = 0

        for file_path in files:
            frame = pd.read_csv(file_path)
            series = _select_column(frame, None)
            cleaned, nn_count, neg_count = _clean_duration_series(series)

            if upper_threshold is not None:
                before = cleaned.size
                cleaned = cleaned[cleaned <= upper_threshold]
                dropped_non_numeric += before - cleaned.size
            if lower_threshold:
                before = cleaned.size
                cleaned = cleaned[cleaned >= lower_threshold]
                dropped_negative += before - cleaned.size

            arrays.append(cleaned)
            dropped_non_numeric += nn_count
            dropped_negative += neg_count

            metadata = _summarise_group(cleaned, file_path.name, (nn_count, neg_count))
            file_entries.append(metadata)
            cleaned_path = self.job_paths.output_dir / f"{group_name}_{file_path.stem}_cleaned.csv"
            pd.Series(cleaned, name="value").to_csv(cleaned_path, index=False, header=False)
            self.guard_cb()

        combined = np.concatenate(arrays)
        group_metadata = _summarise_group(combined, group_name, (dropped_non_numeric, dropped_negative))
        return arrays, file_entries, group_metadata

    def _permutation_with_guard(
        self,
        groups: Sequence[np.ndarray],
        iterations: int,
    ) -> dict[str, object]:
        from smart_comp.stats.kruskal import _compute_h_from_ranks, _prepare_groups

        pooled, sizes, boundaries, tie_correction = _prepare_groups(groups)
        observed_ranks = rankdata(pooled, method="average")
        observed_h = _compute_h_from_ranks(observed_ranks, sizes, boundaries, tie_correction)

        shuffled = pooled.copy()
        permutations = np.empty(iterations, dtype=float)
        rng = np.random.default_rng(self.random_seed)

        for idx in range(iterations):
            self.guard_cb()
            rng.shuffle(shuffled)
            ranks = rankdata(shuffled, method="average")
            permutations[idx] = _compute_h_from_ranks(ranks, sizes, boundaries, tie_correction)
            self._update_loop_progress("permutation", idx + 1, iterations, start=30, span=50)

        p_value = float(np.mean(permutations >= observed_h))
        return {
            "observed": {
                "h_statistic": observed_h,
                "tie_correction": tie_correction,
                "n_total": pooled.size,
                "group_sizes": sizes.tolist(),
            },
            "permutation_distribution": permutations.tolist(),
            "p_value": p_value,
            "iterations": iterations,
        }

    def _normalize_bootstrap(
        self,
        bootstrap_result: dict[str, Any],
        descriptive_results: dict[str, Any],
        plots_requested: bool,
    ) -> dict[str, Any]:
        decision = {
            "alpha": bootstrap_result.get("alpha"),
            "pValue": bootstrap_result.get("p-value"),
            "significant": bootstrap_result.get("significant difference"),
        }
        metrics = {
            "sampleSize": bootstrap_result.get("sample size"),
            "p95": bootstrap_result.get("p95_1"),
            "p95_2": bootstrap_result.get("p95_2"),
            "ciLower": bootstrap_result.get("ci lower p95_1"),
            "ciUpper": bootstrap_result.get("ci upper p95_1"),
            "ciLower2": bootstrap_result.get("ci lower p95_2"),
            "ciUpper2": bootstrap_result.get("ci upper p95_2"),
            "marginOfErrorPct": bootstrap_result.get("p95_1_moe"),
            "marginOfErrorPct2": bootstrap_result.get("p95_2_moe"),
            "threshold": bootstrap_result.get("threshold"),
        }
        interpretation_text = self._local_interpretation({"result": bootstrap_result})

        plots = []
        if plots_requested:
            plots = self._plot_references()

        descriptive_section: dict[str, Any] = {}
        if descriptive_results:
            descriptive_section = next(iter(descriptive_results.values()))
            descriptive_section["sampleSize"] = descriptive_section.get("sample size")

        normalized: dict[str, Any] = {
            "jobId": self.job_id,
            "jobType": self.job_type,
            "decision": decision,
            "metrics": {k: v for k, v in metrics.items() if v is not None},
            "descriptive": descriptive_section,
            "plots": plots,
        }
        if interpretation_text:
            normalized["interpretation"] = {"text": interpretation_text}
        if self.warnings:
            normalized["warnings"] = self.warnings
        return sanitize_for_json(normalized)

    def _normalize_descriptive(self, descriptive_results: dict[str, Any], plots_requested: bool) -> dict[str, Any]:
        descriptive_section = next(iter(descriptive_results.values())) if descriptive_results else {}
        plots = self._plot_references() if plots_requested else []
        payload = {
            "jobId": self.job_id,
            "jobType": self.job_type,
            "descriptive": descriptive_section,
            "plots": plots,
        }
        if self.warnings:
            payload["warnings"] = self.warnings
        return sanitize_for_json(payload)

    def _normalize_kw(
        self,
        permutation_result: dict[str, Any],
        file_metadata: dict[str, list[GroupMetadata]],
    ) -> dict[str, Any]:
        observed = permutation_result.get("observed", {})
        groups_payload = self.payload.get("kwGroups") or []
        groups: list[dict[str, Any]] = []

        for name in groups_payload:
            entries = []
            for meta in file_metadata.get(name, []):
                entries.append(
                    {
                        "fileName": meta.file_name,
                        "n": meta.n,
                        "p95": meta.p95,
                        "median": meta.median,
                    },
                )
            groups.append({"groupName": name, "files": entries})

        decision = {
            "alpha": float(self.payload.get("alpha") or self.config.getfloat("test", "alpha")),
            "pValue": permutation_result.get("p_value"),
        }
        omnibus = {
            "hStatistic": observed.get("h_statistic"),
            "permutations": permutation_result.get("iterations"),
            "totalN": observed.get("n_total"),
            "tieCorrection": observed.get("tie_correction"),
            "groupSizes": observed.get("group_sizes"),
        }

        payload = {
            "jobId": self.job_id,
            "jobType": self.job_type,
            "decision": decision,
            "omnibus": omnibus,
            "groups": groups,
            "plots": [],
        }
        if self.warnings:
            payload["warnings"] = self.warnings
        return sanitize_for_json(payload)

    def _write_results(self, result: ExecutionResult) -> None:
        output_path = self.job_paths.output_dir / "results.json"
        output_path.write_text(json.dumps(result.normalized, indent=2), encoding="utf-8")

        # Ensure output flags for textual rendering
        if not self.config.has_section("output"):
            self.config.add_section("output")
        for section in result.raw.values():
            if isinstance(section, dict):
                for key in section:
                    self.config.set("output", str(key), "true")

        text_path = self.job_paths.output_dir / "results.txt"
        save_results(result.raw, output_path=str(text_path), config=self.config)

    def _move_plots(self) -> None:
        for path in list(self.job_paths.output_dir.glob("*.png")):
            target = self.job_paths.plots_dir / path.name
            if target.exists():
                target.unlink()
            path.replace(target)

    def _plot_flags(self) -> dict[str, bool]:
        plots = self.payload.get("plots") or {}
        return {
            "histogram": bool(plots.get("histogram", False)),
            "boxplot": bool(plots.get("boxplot", False)),
            "kde": bool(plots.get("kde", False)),
        }

    def _flag_plot_outputs(self) -> None:
        if not self.config.has_section("output"):
            self.config.add_section("output")
        for key, enabled in self._plot_flags().items():
            self.config.set("output", key, str(enabled))
        self.config.set("output", "kde_plot", str(self._plot_flags().get("kde")))
        self.config.set("descriptive analysis", "diagraming", str(any(self._plot_flags().values())))

    def _plot_references(self) -> list[dict[str, str]]:
        refs: list[dict[str, str]] = []
        for file in self.job_paths.plots_dir.glob("*.png"):
            kind = "histogram" if "histogram" in file.name else "boxplot" if "boxplot" in file.name else "kde"
            refs.append({"kind": kind, "artifactName": f"plots/{file.name}"})
        return sorted(refs, key=lambda entry: entry["artifactName"])

    def _count_rows(self, path: Path) -> int:
        try:
            return pd.read_csv(path, header=None).shape[0]
        except Exception:
            return 0

    def _local_interpretation(self, raw: dict[str, Any]) -> str | None:
        try:
            from smart_comp.interpretation import simple_local_interpretation
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Interpretation unavailable: %s", exc)
            return None
        return simple_local_interpretation(raw)

    def _ensure_log_placeholder(self) -> None:
        if not self.job_paths.log_file.exists():
            self.job_paths.log_file.write_text("Logging disabled.\n", encoding="utf-8")

    def _update_progress(self, percent: float, step: str, message: str | None = None) -> None:
        self.progress_cb(percent, step, message)

    def _update_loop_progress(self, step: str, current: int, total: int, *, start: float, span: float) -> None:
        progress = start + (current / max(total, 1)) * span
        self._update_progress(progress, step, f"{current}/{total}")

    def _set_seed(self) -> None:
        np.random.seed(self.random_seed)

    def _build_config(self) -> configparser.ConfigParser:
        cfg = configparser.ConfigParser()
        cfg.optionxform = str.lower

        alpha = self.payload.get("alpha") or 0.05
        bootstrap_iterations = self.payload.get("bootstrapIterations") or 5
        permutation_count = self.payload.get("permutationCount") or 5
        threshold = self.payload.get("threshold")
        sample_size = self.payload.get("sampleSize") or 1000

        cfg["test"] = {
            "alpha": str(alpha),
            "bootstrapping iterations": str(bootstrap_iterations),
            "permutation count": str(permutation_count),
            "sample": str(sample_size),
        }
        if threshold is not None:
            cfg.set("test", "threshold", str(threshold))

        lower_bound = self.payload.get("outlierLowerBound") or 0
        upper_bound = self.payload.get("outlierUpperBound") or 20000
        cfg["input"] = {
            "minimum sample size": "1",
            "outlier threshold": str(upper_bound),
            "lower threshold": str(lower_bound),
            "validate_ratio_scale": "true",
        }

        plots = self._plot_flags()
        cfg["output"] = {
            "create_log": str(self.payload.get("createLog", False)),
            "histogram": str(plots.get("histogram", False)),
            "boxplot": str(plots.get("boxplot", False)),
            "kde_plot": str(plots.get("kde", False)),
            "histogram_log_scale": "false",
        }

        cfg["descriptive analysis"] = {
            "required": str(self.payload.get("descriptiveEnabled", True)),
            "descriptive only": str(self.job_type == "DESCRIPTIVE_ONLY"),
            "diagraming": str(any(plots.values())),
            "bandwidth": "scott",
            "mean": "true",
            "median": "true",
            "min": "true",
            "max": "true",
            "sample size": "true",
            "standard deviation": "true",
            "skewness": "true",
            "mode": "true",
            "p95_empirical": "true",
            "get extended report": "false",
            "unimodality_test_enabled": "true",
        }

        cfg["interpretation"] = {
            "use_chatgpt_api": "false",
            "save the results into file": "false",
            "explain the result": "false",
        }
        cfg["clean"] = {"clean_all": str(self.payload.get("cleanAll", False))}
        return cfg

    @contextmanager
    def _working_directory(self, target: Path):
        previous = Path.cwd()
        os.chdir(target)
        try:
            yield
        finally:
            os.chdir(previous)
