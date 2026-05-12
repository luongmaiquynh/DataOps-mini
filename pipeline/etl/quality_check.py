import pandas as pd
import logging
from dataclasses import dataclass
from typing import List, Dict

logger = logging.getLogger(__name__)


@dataclass
class QualityReport:
    null_count: Dict[str, int]
    duplicate_count: int
    missing_columns: List[str]
    row_count: int
    passed: bool

    def summary(self) -> str:
        status = "PASSED" if self.passed else "FAILED"
        return (
            f"[Quality Check {status}] "
            f"rows={self.row_count}, "
            f"duplicates={self.duplicate_count}, "
            f"nulls={self.null_count}, "
            f"missing_cols={self.missing_columns}"
        )


def run_quality_check(df: pd.DataFrame, expected_columns: List[str] = None) -> QualityReport:
    """Kiểm tra chất lượng dữ liệu và trả về QualityReport.

    Kiểm tra:
    - Số lượng null từng cột
    - Số dòng duplicate
    - Các cột bị thiếu so với expected_columns
    """
    null_count = {col: int(df[col].isnull().sum()) for col in df.columns}
    duplicate_count = int(df.duplicated().sum())
    missing_columns = []
    if expected_columns:
        missing_columns = [c for c in expected_columns if c not in df.columns]

    has_nulls = any(v > 0 for v in null_count.values())
    passed = (
        not has_nulls and
        duplicate_count == 0 and
        len(missing_columns) == 0
    )

    report = QualityReport(
        null_count=null_count,
        duplicate_count=duplicate_count,
        missing_columns=missing_columns,
        row_count=len(df),
        passed=passed,
    )
    logger.info(report.summary())
    return report


def assert_quality(df: pd.DataFrame, expected_columns: List[str] = None) -> QualityReport:
    """Chạy kiểm tra chất lượng và raise Exception nếu không đạt.

    Dùng trong Airflow DAG để dừng pipeline khi dữ liệu xấu.
    """
    report = run_quality_check(df, expected_columns)
    if not report.passed:
        raise ValueError(f"Data quality check failed: {report.summary()}")
    return report
