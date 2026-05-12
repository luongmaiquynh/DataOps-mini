import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest  # noqa: E402
import pandas as pd  # noqa: E402
from etl.quality_check import run_quality_check, assert_quality, QualityReport  # noqa: E402


# ─── Fixtures ────────────────────────────────────────────────

@pytest.fixture
def clean_df():
    """DataFrame sạch, không lỗi."""
    return pd.DataFrame({
        'id': [1, 2, 3],
        'name': ['An', 'Binh', 'Cuong'],
        'age': [25, 30, 28],
    })


@pytest.fixture
def dirty_df():
    """DataFrame có null và duplicate."""
    return pd.DataFrame({
        'id': [1, 2, 2],
        'name': ['An', 'Binh', 'Binh'],
        'age': [25, None, None],
    })


# ─── run_quality_check ────────────────────────────────────────

def test_run_quality_check_returns_report(clean_df):
    """Hàm phải trả về đối tượng QualityReport."""
    report = run_quality_check(clean_df)
    assert isinstance(report, QualityReport)


def test_run_quality_check_passes_on_clean_data(clean_df):
    """DataFrame sạch phải cho kết quả passed=True."""
    report = run_quality_check(clean_df)
    assert report.passed is True


def test_run_quality_check_fails_on_null(dirty_df):
    """DataFrame có null phải cho kết quả passed=False."""
    report = run_quality_check(dirty_df)
    assert report.passed is False


def test_run_quality_check_fails_on_duplicate(dirty_df):
    """DataFrame có duplicate phải cho kết quả passed=False."""
    report = run_quality_check(dirty_df)
    assert report.passed is False


def test_run_quality_check_counts_duplicates(dirty_df):
    """duplicate_count phải đếm đúng số dòng trùng."""
    report = run_quality_check(dirty_df)
    assert report.duplicate_count == 1  # 1 dòng trùng (row index 2)


def test_run_quality_check_counts_nulls(dirty_df):
    """null_count phải ghi nhận đúng cột có null."""
    report = run_quality_check(dirty_df)
    assert report.null_count['age'] == 2


def test_run_quality_check_row_count(clean_df):
    """row_count phải bằng số dòng thực tế."""
    report = run_quality_check(clean_df)
    assert report.row_count == 3


def test_run_quality_check_detects_missing_columns(clean_df):
    """Nếu truyền expected_columns có cột không tồn tại, phải báo missing."""
    report = run_quality_check(clean_df, expected_columns=['id', 'name', 'age', 'salary'])
    assert 'salary' in report.missing_columns
    assert report.passed is False


def test_run_quality_check_no_missing_columns(clean_df):
    """Nếu tất cả expected_columns đều có, missing_columns phải rỗng."""
    report = run_quality_check(clean_df, expected_columns=['id', 'name', 'age'])
    assert report.missing_columns == []


# ─── assert_quality ───────────────────────────────────────────

def test_assert_quality_passes_on_clean_data(clean_df):
    """assert_quality không raise exception với dữ liệu sạch."""
    try:
        assert_quality(clean_df)
    except Exception:
        pytest.fail("assert_quality raised exception trên dữ liệu sạch")


def test_assert_quality_raises_on_dirty_data(dirty_df):
    """assert_quality phải raise exception với dữ liệu có lỗi."""
    with pytest.raises(Exception):
        assert_quality(dirty_df)


# ─── QualityReport.summary ────────────────────────────────────

def test_quality_report_summary_passed(clean_df):
    """summary() phải chứa chữ PASSED với dữ liệu sạch."""
    report = run_quality_check(clean_df)
    assert 'PASSED' in report.summary()


def test_quality_report_summary_failed(dirty_df):
    """summary() phải chứa chữ FAILED với dữ liệu lỗi."""
    report = run_quality_check(dirty_df)
    assert 'FAILED' in report.summary()
