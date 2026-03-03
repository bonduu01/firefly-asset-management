import json
import pytest
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).parent

# @pytest.fixture(scope="session")
# def cloud_resources():
#     path = Path("data/cloud_resources.json")
#     with open(path) as f:
#         return json.load(f)

@pytest.fixture(scope="session")
def cloud_resources():
    path = BASE_DIR / "data" / "cloud_resources.json"
    with open(path) as f:
        return json.load(f)


# @pytest.fixture(scope="session")
# def iac_resources():
#     path = Path("data/iac_resources.json")
#     with open(path) as f:
#         return json.load(f)

@pytest.fixture(scope="session")
def iac_resources():
    path = BASE_DIR / "data" / "iac_resources.json"
    with open(path) as f:
        return json.load(f)


@pytest.fixture(scope="session")
def browser_context():
    """Headless browser context (Playwright) — used if UI validation is needed."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        yield context
        browser.close()