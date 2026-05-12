import pandas as pd
import logging

logger = logging.getLogger(__name__)


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """Xóa dòng duplicate và dòng toàn null."""
    initial = len(df)
    df = df.drop_duplicates()
    df = df.dropna(how='all')
    removed = initial - len(df)
    if removed > 0:
        logger.info(f"Removed {removed} duplicate/empty rows. Remaining: {len(df)}")
    return df.reset_index(drop=True)


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Chuẩn hóa tên cột: lowercase, thay space bằng underscore."""
    df.columns = [col.strip().lower().replace(' ', '_') for col in df.columns]
    return df


def fill_missing(df: pd.DataFrame, fill_values: dict) -> pd.DataFrame:
    """Điền giá trị mặc định cho các cột bị thiếu.

    Ví dụ: fill_values = {'age': 0, 'salary': 0.0}
    """
    for col, value in fill_values.items():
        if col in df.columns:
            before = df[col].isnull().sum()
            df[col] = df[col].fillna(value)
            if before > 0:
                logger.info(f"Filled {before} missing values in '{col}' with {value}")
    return df


def cast_types(df: pd.DataFrame, schema: dict) -> pd.DataFrame:
    """Ép kiểu dữ liệu cho từng cột theo schema.

    Ví dụ: schema = {'age': int, 'salary': float, 'created_at': 'datetime64[ns]'}
    """
    for col, dtype in schema.items():
        if col in df.columns:
            try:
                df[col] = df[col].astype(dtype)
            except Exception as e:
                logger.warning(f"Cannot cast column '{col}' to {dtype}: {e}")
    return df
