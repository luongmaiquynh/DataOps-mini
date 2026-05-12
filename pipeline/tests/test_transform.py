import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest  # noqa: E402
import pandas as pd  # noqa: E402
from etl.transform import (  # noqa: E402
    clean_data, normalize_columns, fill_missing, cast_types
)


# ─── Fixtures ────────────────────────────────────────────────

@pytest.fixture
def sample_df():
    """DataFrame mẫu có duplicate và null."""
    return pd.DataFrame({
        'ID': [1, 2, 3, 1, 4],
        'Name': ['An', 'Binh', 'Cuong', 'An', None],
        'Age': [25, 30, None, 25, 28],
        'Salary': [1000.0, 2000.0, 1500.0, 1000.0, None],
    })


# ─── clean_data ───────────────────────────────────────────────

def test_clean_data_removes_duplicate_rows(sample_df):
    """Hàm clean_data phải xóa dòng trùng lặp hoàn toàn."""
    result = clean_data(sample_df)
    assert len(result) == 4  # dòng ID=1 trùng bị xóa


def test_clean_data_removes_all_null_rows():
    """Hàm clean_data phải xóa dòng toàn null."""
    df = pd.DataFrame({
        'A': [1, None, 3],
        'B': [4, None, 6],
    })
    result = clean_data(df)
    assert len(result) == 2


def test_clean_data_keeps_partial_null_rows(sample_df):
    """Dòng có một số null vẫn được giữ lại (chỉ xóa dòng TOÀN null)."""
    result = clean_data(sample_df)
    # Dòng có Age=None hoặc Salary=None vẫn còn
    assert result['Age'].isnull().sum() + result['Salary'].isnull().sum() > 0


def test_clean_data_returns_reset_index(sample_df):
    """Index sau khi clean phải liên tục từ 0."""
    result = clean_data(sample_df)
    assert list(result.index) == list(range(len(result)))


def test_clean_data_empty_dataframe():
    """clean_data không crash với DataFrame rỗng."""
    df = pd.DataFrame(columns=['A', 'B'])
    result = clean_data(df)
    assert len(result) == 0


# ─── normalize_columns ────────────────────────────────────────

def test_normalize_columns_lowercase():
    """Tên cột phải được chuyển sang chữ thường."""
    df = pd.DataFrame(columns=['ID', 'FullName', 'Date'])
    result = normalize_columns(df)
    assert list(result.columns) == ['id', 'fullname', 'date']


def test_normalize_columns_replaces_spaces():
    """Dấu cách trong tên cột phải được thay bằng underscore."""
    df = pd.DataFrame(columns=['Full Name', 'Birth Date', 'Home City'])
    result = normalize_columns(df)
    assert list(result.columns) == ['full_name', 'birth_date', 'home_city']


def test_normalize_columns_strips_whitespace():
    """Khoảng trắng đầu/cuối tên cột phải được xóa."""
    df = pd.DataFrame(columns=['  Name  ', ' Age '])
    result = normalize_columns(df)
    assert list(result.columns) == ['name', 'age']


# ─── fill_missing ─────────────────────────────────────────────

def test_fill_missing_fills_correct_column(sample_df):
    """Hàm fill_missing chỉ fill đúng cột được chỉ định."""
    result = fill_missing(sample_df, {'Age': 0})
    assert result['Age'].isnull().sum() == 0


def test_fill_missing_does_not_affect_other_columns(sample_df):
    """Các cột không được chỉ định không bị thay đổi."""
    null_before = sample_df['Salary'].isnull().sum()
    result = fill_missing(sample_df, {'Age': 0})
    assert result['Salary'].isnull().sum() == null_before


def test_fill_missing_ignores_nonexistent_column(sample_df):
    """fill_missing không crash nếu tên cột không tồn tại."""
    result = fill_missing(sample_df, {'NonExistentCol': 99})
    assert result is not None


# ─── cast_types ───────────────────────────────────────────────

def test_cast_types_converts_to_int():
    """Cột float phải được convert sang int đúng."""
    df = pd.DataFrame({'score': [1.0, 2.0, 3.0]})
    result = cast_types(df, {'score': int})
    assert result['score'].dtype == int


def test_cast_types_converts_to_float():
    """Cột int phải được convert sang float đúng."""
    df = pd.DataFrame({'price': [100, 200, 300]})
    result = cast_types(df, {'price': float})
    assert result['price'].dtype == float


def test_cast_types_skips_invalid_cast():
    """cast_types không crash khi không thể convert (ví dụ text sang int)."""
    df = pd.DataFrame({'name': ['An', 'Binh', 'Cuong']})
    result = cast_types(df, {'name': int})  # không thể convert
    assert result is not None  # không raise exception


def test_cast_types_ignores_nonexistent_column():
    """cast_types không crash nếu tên cột không tồn tại."""
    df = pd.DataFrame({'age': [25, 30]})
    result = cast_types(df, {'nonexistent': int})
    assert list(result.columns) == ['age']
