import json
import pytest
from pathlib import Path

# Project root — same directory as this conftest.py
BASE_DIR = Path(__file__).parent


@pytest.fixture(scope="session")
def cloud_resources():
    """Load live cloud resource definitions from data/cloud_resources.json."""
    path = BASE_DIR / "data" / "cloud_resources.json"
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="session")
def iac_resources():
    """Load IaC resource definitions from data/iac_resources.json."""
    path = BASE_DIR / "data" / "iac_resources.json"
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="session")
def output_path(tmp_path_factory):
    """
    Provide a temporary directory path for report output during the test
    session.  Used by tests that need to write a report without touching
    the persistent reports/ directory.
    """
    return tmp_path_factory.mktemp("reports") / "comparison_report.json"