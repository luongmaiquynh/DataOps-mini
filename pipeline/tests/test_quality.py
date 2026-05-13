import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest  # noqa: E402
import pandas as pd  # noqa: E402
from etl.quality_check import (  # noqa: E402
    run_quality_check, assert_quality, QualityReport
)


# ─── run_quality_check ───────────────────────────────────────

def test_run_quality_check_detects_nulls():
    df = pd.DataFrame({'a': [1, None], 'b': [2, 3]})
    report = run_quality_check(df)
    assert report.null_count['a'] == 1
    assert report.passed is False


def test_run_quality_check_detects_duplicates():
    df = pd.DataFrame({'a': [1, 1], 'b': [2, 2]})
    report = run_quality_check(df)
    assert report.duplicate_count == 1
    assert report.passed is False


def test_run_quality_check_detects_schema_errors():
    df = pd.DataFrame({'a': [1, 2]})
    report = run_quality_check(df, expected_columns=['a', 'b'])
    assert 'b' in report.schema_errors
    assert report.passed is False


def test_run_quality_check_passed_when_clean():
    df = pd.DataFrame({'a': [1, 2], 'b': [3, 4]})
    report = run_quality_check(df, expected_columns=['a', 'b'])
    assert report.passed is True


# ─── assert_quality ──────────────────────────────────────────

def test_assert_quality_raises_on_nulls():
    df = pd.DataFrame({'a': [1, None]})
    with pytest.raises(ValueError):
        assert_quality(df)


def test_assert_quality_raises_on_duplicates():
    df = pd.DataFrame({'a': [1, 1], 'b': [2, 2]})
    with pytest.raises(ValueError):
        assert_quality(df)


def test_assert_quality_raises_on_missing_columns():
    df = pd.DataFrame({'a': [1, 2]})
    with pytest.raises(ValueError):
        assert_quality(df, expected_columns=['a', 'b'])


def test_assert_quality_does_not_raise_when_clean():
    df = pd.DataFrame({'a': [1, 2], 'b': [3, 4]})
    assert_quality(df, expected_columns=['a', 'b'])  # không raise


# ─── QualityReport.summary ───────────────────────────────────

def test_quality_report_summary_contains_passed():
    report = QualityReport(passed=True)
    assert 'passed=True' in report.summary()


def test_quality_report_summary_contains_duplicates():
    report = QualityReport(duplicate_count=3)
    assert 'duplicates=3' in report.summary()


def test_quality_report_summary_contains_schema_errors():
    report = QualityReport(schema_errors=['col_x'])
    assert 'col_x' in report.summary()


def test_quality_report_summary_is_string():
    report = QualityReport()
    assert isinstance(report.summary(), str)
