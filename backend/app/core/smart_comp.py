from __future__ import annotations

import configparser
import logging
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_NAME = "config.txt"


class SmartCompConfigError(RuntimeError):
    """Raised when Smart-Comp configuration cannot be loaded or parsed."""


@dataclass(frozen=True)
class PlotDefaults:
    histogram: bool
    boxplot: bool
    kde: bool


@dataclass(frozen=True)
class ConfigDefaults:
    alpha: float | None
    threshold: float | None
    bootstrap_iterations: int | None
    permutation_count: int | None
    sample_size: int | None
    descriptive_enabled: bool
    plots: PlotDefaults
    create_log: bool
    clean_all: bool


def _load_config_text_from_package() -> str:
    try:
        config_resource = resources.files("smart_comp").joinpath(DEFAULT_CONFIG_NAME)
    except ModuleNotFoundError:
        logger.warning("Smart-Comp library missing; using bundled fallback defaults.")
        return (
            "[test]\n"
            "alpha = 0.05\n"
            "bootstrap iterations = 5\n"
            "permutation count = 5\n"
            "[descriptive analysis]\n"
            "required = true\n"
            "[output]\n"
            "create_log = false\n"
            "[clean]\n"
            "clean_all = false\n"
        )

    if not config_resource.is_file():
        raise SmartCompConfigError(
            f"Smart-Comp default configuration '{DEFAULT_CONFIG_NAME}' is missing.",
        )
    return config_resource.read_text(encoding="utf-8")


def read_config(config_path: Path | str | None = None) -> configparser.ConfigParser:
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str.lower

    if config_path is not None:
        path = Path(config_path)
        if not path.exists():
            raise SmartCompConfigError(f"Smart-Comp configuration not found: {path}")
        parser.read(path)
        logger.debug("Loaded Smart-Comp configuration from %s", path)
        return parser

    parser.read_string(_load_config_text_from_package())
    logger.debug("Loaded Smart-Comp configuration bundled with the library.")
    return parser


def _get_first_valid_number(
    parser: configparser.ConfigParser,
    sections: Iterable[str],
    options: Iterable[str],
    cast_fn,
) -> float | int | None:
    for section in sections:
        if not parser.has_section(section):
            continue
        for option in options:
            if not parser.has_option(section, option):
                continue
            try:
                return cast_fn(section, option)
            except ValueError:
                logger.warning("Invalid numeric value for %s.%s", section, option)
                return None
    return None


def _get_first_valid_bool(
    parser: configparser.ConfigParser,
    sections: Iterable[str],
    options: Iterable[str],
    fallback: bool,
) -> bool:
    for section in sections:
        if not parser.has_section(section):
            continue
        for option in options:
            if not parser.has_option(section, option):
                continue
            try:
                return parser.getboolean(section, option)
            except ValueError:
                logger.warning("Invalid boolean value for %s.%s", section, option)
                return fallback
    return fallback


def map_config_to_defaults(parser: configparser.ConfigParser) -> ConfigDefaults:
    alpha = _get_first_valid_number(parser, ["test"], ["alpha"], parser.getfloat)
    threshold = _get_first_valid_number(parser, ["test"], ["threshold"], parser.getfloat)
    bootstrap_iterations = _get_first_valid_number(
        parser,
        ["test"],
        ["bootstrap iterations", "bootstrap_iterations", "bootstrapping iterations"],
        parser.getint,
    )
    permutation_count = _get_first_valid_number(
        parser,
        ["test"],
        ["permutation count", "permutation_count", "permutations"],
        parser.getint,
    )
    sample_size = _get_first_valid_number(
        parser,
        ["test"],
        ["sample size", "sample_size", "sample"],
        parser.getint,
    )

    descriptive_enabled = _get_first_valid_bool(
        parser,
        ["descriptive analysis"],
        ["required", "enabled"],
        fallback=True,
    )
    create_log = _get_first_valid_bool(
        parser,
        ["output"],
        ["create_log", "create log", "log"],
        fallback=False,
    )
    clean_all = _get_first_valid_bool(
        parser,
        ["clean"],
        ["clean_all", "clean all"],
        fallback=False,
    )

    plots_section = ["output", "plots"]
    plots = PlotDefaults(
        histogram=_get_first_valid_bool(parser, plots_section, ["histogram"], fallback=True),
        boxplot=_get_first_valid_bool(parser, plots_section, ["boxplot", "box plot"], fallback=True),
        kde=_get_first_valid_bool(parser, plots_section, ["kde", "density"], fallback=True),
    )

    return ConfigDefaults(
        alpha=alpha,
        threshold=threshold,
        bootstrap_iterations=bootstrap_iterations,
        permutation_count=permutation_count,
        sample_size=sample_size,
        descriptive_enabled=descriptive_enabled,
        plots=plots,
        create_log=create_log,
        clean_all=clean_all,
    )


def load_config_defaults(config_path: Path | str | None = None) -> ConfigDefaults:
    parser = read_config(config_path)
    return map_config_to_defaults(parser)


def defaults_to_overrides(defaults: ConfigDefaults) -> dict[str, object]:
    """Convert defaults to the web-facing ConfigOverrides JSON shape."""
    return {
        "alpha": defaults.alpha,
        "threshold": defaults.threshold,
        "bootstrapIterations": defaults.bootstrap_iterations,
        "permutationCount": defaults.permutation_count,
        "sampleSize": defaults.sample_size,
        "descriptiveEnabled": defaults.descriptive_enabled,
        "plots": {
            "histogram": defaults.plots.histogram,
            "boxplot": defaults.plots.boxplot,
            "kde": defaults.plots.kde,
        },
        "createLog": defaults.create_log,
        "cleanAll": defaults.clean_all,
    }
