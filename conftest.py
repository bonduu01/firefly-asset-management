import json
import pytest
from pathlib import Path

# Anchor all paths to the project root (directory containing conftest.py)
BASE_DIR = Path(__file__).parent


@pytest.fixture(scope="session")
def cloud_resources():
    path = BASE_DIR / "data" / "cloud_resources.json"
    with open(path) as f:
        return json.load(f)


@pytest.fixture(scope="session")
def iac_resources():
    path = BASE_DIR / "data" / "iac_resources.json"
    with open(path) as f:
        return json.load(f)


@pytest.fixture(scope="session")
def output_path(tmp_path_factory):
    """Provides a persistent temp path for report output during the test session."""
    return tmp_path_factory.mktemp("reports") / "comparison_report.json"