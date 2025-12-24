from __future__ import annotations

import configparser
from pathlib import Path

import pytest

from app.core.smart_comp import (
    ConfigDefaults,
    PlotDefaults,
    defaults_to_overrides,
    load_config_defaults,
    map_config_to_defaults,
    read_config,
    SmartCompConfigError,
)


def _build_parser_from_text(config_text: str) -> configparser.ConfigParser:
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str.lower
    parser.read_string(config_text)
    return parser


def test_map_config_to_defaults_parses_expected_values() -> None:
    parser = _build_parser_from_text(
        """
[test]
alpha = 0.02
threshold = 0.1
bootstrap iterations = 250
permutation count = 400
sample size = 50

[output]
histogram = false
boxplot = true
kde = false
create_log = true

[descriptive analysis]
required = false

[clean]
clean_all = true
"""
    )

    defaults = map_config_to_defaults(parser)

    assert defaults == ConfigDefaults(
        alpha=0.02,
        threshold=0.1,
        bootstrap_iterations=250,
        permutation_count=400,
        sample_size=50,
        descriptive_enabled=False,
        plots=PlotDefaults(histogram=False, boxplot=True, kde=False),
        create_log=True,
        clean_all=True,
    )

    overrides = defaults_to_overrides(defaults)
    assert overrides["bootstrapIterations"] == 250
    assert overrides["permutationCount"] == 400
    assert overrides["plots"] == {"histogram": False, "boxplot": True, "kde": False}
    assert overrides["cleanAll"] is True


def test_defaults_loader_reads_from_custom_path(tmp_path: Path) -> None:
    config_path = tmp_path / "config.txt"
    config_path.write_text(
        """
[test]
alpha = 0.05
bootstrap_iterations = 1000
"""
    )

    defaults = load_config_defaults(config_path)
    assert defaults.alpha == 0.05
    assert defaults.bootstrap_iterations == 1000


def test_read_config_raises_for_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.txt"
    with pytest.raises(SmartCompConfigError):
        read_config(missing)
