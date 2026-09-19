import pandas as pd
import logging
from dataclasses import dataclass, field
from typing import List

logger = logging.getLogger(__name__)


@dataclass
class QualityReport:
    null_count: dict = field(default_factory=dict)
    duplicate_count: int = 0
    schema_errors: List[str] = field(default_factory=list)
    passed: bool = True

    def summary(self) -> str:
        return (
            f"QualityReport | nulls={self.null_count} | "
            f"duplicates={self.duplicate_count} | "
            f"schema_errors={self.schema_errors} | "
            f"passed={self.passed}"
        )


def run_quality_check(df: pd.DataFrame, expected_columns: List[str] = None,
                      key_columns: List[str] = None) -> QualityReport:
    """Kiểm tra chất lượng dữ liệu, trả về QualityReport (không raise exception).

    `key_columns`: đếm trùng theo khoá thay vì theo cả dòng. Cần cho dữ liệu đã
    nằm trong database, vì hai bản ghi trùng khoá thường khác nhau ở cột phụ như
    `ingested_at` — so cả dòng sẽ không bao giờ thấy chúng trùng.
    """
    null_count = df.isnull().sum().to_dict()
    duplicate_count = int(df.duplicated(subset=key_columns).sum())
    schema_errors = []
    if expected_columns:
        schema_errors = [c for c in expected_columns if c not in df.columns]

    passed = (
        all(v == 0 for v in null_count.values())
        and duplicate_count == 0
        and len(schema_errors) == 0
    )

    report = QualityReport(
        null_count=null_count,
        duplicate_count=duplicate_count,
        schema_errors=schema_errors,
        passed=passed,
    )
    logger.info(report.summary())
    return report


def assert_quality(df: pd.DataFrame, expected_columns: List[str] = None,
                   key_columns: List[str] = None) -> None:
    """Kiểm tra chất lượng và raise ValueError nếu không đạt."""
    report = run_quality_check(df, expected_columns, key_columns)
    if not report.passed:
        raise ValueError(f"Data quality check failed: {report.summary()}")
