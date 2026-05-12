import requests
import pandas as pd
import logging

logger = logging.getLogger(__name__)


def extract_from_api(url: str, params: dict = None) -> pd.DataFrame:
    """Lấy dữ liệu từ REST API, trả về DataFrame."""
    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        # Nếu data là list thì chuyển thẳng sang DataFrame
        # Nếu là dict thì lấy value đầu tiên là list
        if isinstance(data, list):
            df = pd.DataFrame(data)
        elif isinstance(data, dict):
            # Tìm key đầu tiên có value là list
            for key, value in data.items():
                if isinstance(value, list):
                    df = pd.DataFrame(value)
                    break
            else:
                df = pd.DataFrame([data])
        else:
            raise ValueError(f"Unexpected data format: {type(data)}")
        logger.info(f"Extracted {len(df)} rows from {url}")
        return df
    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Extract failed: {e}")
        raise


def extract_from_csv(filepath: str) -> pd.DataFrame:
    """Đọc dữ liệu từ file CSV, trả về DataFrame."""
    try:
        df = pd.read_csv(filepath)
        logger.info(f"Loaded {len(df)} rows from {filepath}")
        return df
    except FileNotFoundError:
        logger.error(f"File not found: {filepath}")
        raise
    except Exception as e:
        logger.error(f"CSV read failed: {e}")
        raise
