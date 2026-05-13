import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest  # noqa: E402
import pandas as pd  # noqa: E402
from unittest.mock import patch, MagicMock  # noqa: E402
from etl.extract import extract_from_csv, extract_from_api  # noqa: E402

SAMPLE_CSV = os.path.join(
    os.path.dirname(__file__), '..', '..', 'sample_data', 'sample.csv'
)


# ─── extract_from_csv ────────────────────────────────────────

def test_extract_from_csv_returns_dataframe():
    """Hàm phải trả về DataFrame."""
    result = extract_from_csv(SAMPLE_CSV)
    assert isinstance(result, pd.DataFrame)


def test_extract_from_csv_correct_columns():
    """Phải có đúng các cột từ file CSV."""
    result = extract_from_csv(SAMPLE_CSV)
    expected_cols = {'id', 'name', 'age', 'city', 'salary', 'created_at'}
    assert expected_cols.issubset(set(result.columns))


def test_extract_from_csv_correct_row_count():
    """Sample CSV có 6 dòng dữ liệu (gồm 1 duplicate, 2 dòng có null)."""
    result = extract_from_csv(SAMPLE_CSV)
    assert len(result) == 6


def test_extract_from_csv_has_duplicate():
    """Sample CSV có 1 dòng duplicate (id=1)."""
    result = extract_from_csv(SAMPLE_CSV)
    assert result.duplicated().sum() == 1


def test_extract_from_csv_has_nulls():
    """Sample CSV có null trong cột age và salary."""
    result = extract_from_csv(SAMPLE_CSV)
    assert result['age'].isnull().sum() >= 1
    assert result['salary'].isnull().sum() >= 1


def test_extract_from_csv_file_not_found():
    """Phải raise FileNotFoundError nếu file không tồn tại."""
    with pytest.raises(FileNotFoundError):
        extract_from_csv('/tmp/nonexistent_file_xyz.csv')


# ─── extract_from_api ────────────────────────────────────────

def test_extract_from_api_with_list_response():
    """API trả về list → phải convert sang DataFrame đúng."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = [
        {'id': 1, 'temp': 25.0},
        {'id': 2, 'temp': 27.5},
    ]
    mock_resp.raise_for_status = MagicMock()

    with patch('etl.extract.requests.get', return_value=mock_resp):
        result = extract_from_api('http://fake-api.test/data')

    assert isinstance(result, pd.DataFrame)
    assert len(result) == 2
    assert 'temp' in result.columns


def test_extract_from_api_with_dict_response():
    """API trả về dict chứa list → phải lấy đúng list bên trong."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        'status': 'ok',
        'results': [{'city': 'Hanoi', 'temp': 32}]
    }
    mock_resp.raise_for_status = MagicMock()

    with patch('etl.extract.requests.get', return_value=mock_resp):
        result = extract_from_api('http://fake-api.test/weather')

    assert isinstance(result, pd.DataFrame)
    assert len(result) == 1
    assert 'city' in result.columns


def test_extract_from_api_raises_on_http_error():
    """Phải raise exception khi API trả về HTTP error."""
    import requests as req
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = req.exceptions.HTTPError('404')

    with patch('etl.extract.requests.get', return_value=mock_resp):
        with pytest.raises(req.exceptions.HTTPError):
            extract_from_api('http://fake-api.test/notfound')


def test_extract_from_api_raises_on_connection_error():
    """Phải raise exception khi không kết nối được API."""
    import requests as req
    with patch('etl.extract.requests.get',
               side_effect=req.exceptions.ConnectionError('refused')):
        with pytest.raises(req.exceptions.ConnectionError):
            extract_from_api('http://unreachable.test')
