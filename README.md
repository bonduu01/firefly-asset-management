# 🔥 Firefly Asset Management Solution

> A Python automation framework that detects infrastructure drift by comparing **live cloud resources** against **Infrastructure-as-Code (IaC) definitions** — and produces a structured JSON comparison report.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Project Structure](#project-structure)
- [How It Works](#how-it-works)
- [State Definitions](#state-definitions)
- [Report Format Specification](#report-format-specification)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Tests](#running-the-tests)
- [Test Suite Reference](#test-suite-reference)
- [Docker & LocalStack S3](#docker--localstack-s3)
- [CI/CD with GitHub Actions & Allure](#cicd-with-github-actions--allure)
- [Changelog Field Reference](#changelog-field-reference)

---

## Overview

Cloud resources often diverge from what is declared in IaC tools like Terraform or CloudFormation — this is called **infrastructure drift**. The Firefly Asset Management Solution automates drift detection by:

1. Loading **live cloud resource** definitions from a JSON file
2. Loading **IaC-declared resource** definitions from a JSON file
3. **Matching** each cloud resource to its IaC counterpart by `id`
4. **Diffing** matched pairs field-by-field — including nested objects and arrays
5. Assigning a **State** to each resource: `Match`, `Modified`, or `Missing`
6. Writing a **flat JSON array report** with full changelogs for drifted resources
7. **Uploading** the report to an S3 bucket (real AWS or LocalStack)

---

## Project Structure

```
firefly-asset-management/
│
├── core/
│   ├── __init__.py
│   ├── comparator.py        # Diff engine: nested objects + arrays
│   ├── models.py            # AssetComparisonItem, ChangeLogEntry dataclasses
│   ├── reporter.py          # Serialises results to flat JSON array
│   └── s3_uploader.py       # Uploads report to S3 / LocalStack
│
├── data/
│   ├── cloud_resources.json # INPUT  — live cloud resource definitions
│   └── iac_resources.json   # INPUT  — IaC declared resource definitions
│
├── reports/
│   └── comparison_report.json  # OUTPUT — generated after test run
│
├── tests/
│   └── test_asset_comparison.py  # Full pytest test suite (15 tests)
│
├── conftest.py              # Pytest fixtures (JSON loaders, path helpers)
├── requirements.txt         # Python dependencies
│
├── Dockerfile               # Application container
├── Dockerfile.localstack    # LocalStack S3 container
├── docker-compose.yml       # Orchestrates analyzer + LocalStack
├── init-s3.sh               # Auto-creates S3 bucket on LocalStack startup
│
├── .github/
│   └── workflows/
│       └── test-and-report.yml  # GitHub Actions CI/CD + Allure Pages
│
├── .gitignore
└── README.md
```

---

## How It Works

### Step 1 — Load Inputs (`conftest.py`)

Pytest fixtures load both JSON files at session start. Paths are anchored to the project root using `Path(__file__).parent`, so tests run correctly regardless of working directory.

```
data/cloud_resources.json  →  List of live cloud resource dicts
data/iac_resources.json    →  List of IaC-declared resource dicts
```

---

### Step 2 — Compare Resources (`core/comparator.py`)

`compare_resources()` is the entry point:

```
cloud_resources  ──┐
                   ├──▶  compare_resources()  ──▶  List[AssetComparisonItem]
iac_resources    ──┘
```

Internally it:

- **Indexes** IaC resources by `id` for O(1) lookup
- **Iterates** every cloud resource and looks up its IaC match
- **Calls `_diff_resources()`** on matched pairs to find field-level changes
- **Calls `_diff_arrays()`** when either side contains a list value

#### Diff Engine Capabilities

| Input type | Behaviour | Key format |
|---|---|---|
| Flat scalar field | Direct equality check | `size` |
| Nested object | Recursive diff | `tags.env` |
| Array of scalars | Element-by-element comparison | `ports[0]`, `ports[1]` |
| Array length difference | Extra elements logged with `None` on missing side | `tags[2]` |
| Array of objects | Recurse into each element | `rules[0].action` |
| Nested array in array | Chained bracket notation | `matrix[1][1]` |
| Mixed objects and arrays | Combined dot + bracket notation | `config.listeners[0].port` |

---

### Step 3 — Data Models (`core/models.py`)

Each comparison result is an `AssetComparisonItem`:

| Field | Type | Description |
|---|---|---|
| `CloudResourceItem` | `dict` | The original live cloud resource |
| `IacResourceItem` | `dict \| None` | The matched IaC resource (`None` if missing) |
| `State` | `str` | `Match`, `Modified`, or `Missing` |
| `ChangeLog` | `List[ChangeLogEntry]` | Field-level diffs (empty unless `Modified`) |

Each `ChangeLogEntry` uses the spec-required field names:

| Field | Description |
|---|---|
| `KeyName` | Dot/bracket-notation path to the changed field |
| `CloudValue` | Value in the live cloud resource |
| `IacValue` | Value declared in IaC |

---

### Step 4 — Generate Report (`core/reporter.py`)

`generate_report()` serialises all results as a **flat JSON array** — no wrapper object — and writes it to `reports/comparison_report.json`.

A human-readable summary is printed to console but **not included in the JSON output**, keeping the report clean for downstream consumers.

---

### Step 5 — Upload to S3 (`core/s3_uploader.py`)

After the report is generated, `s3_uploader.py` uploads it to an S3 bucket. It supports both real AWS and LocalStack via the `S3_ENDPOINT_URL` environment variable.

---

## State Definitions

| State | Meaning |
|---|---|
| ✅ `Match` | Resource exists in IaC and every field is identical |
| ⚠️ `Modified` | Resource exists in IaC but one or more fields differ (drift detected) |
| ❌ `Missing` | Resource has no corresponding IaC definition |

---

## Report Format Specification

The output is a **flat JSON array** — each element is one `AssetComparisonItem`.

```json
[
  {
    "CloudResourceItem": { "id": "res-001", "type": "s3", "region": "us-east-1" },
    "IacResourceItem":   { "id": "res-001", "type": "s3", "region": "us-east-1" },
    "State": "Match",
    "ChangeLog": []
  },
  {
    "CloudResourceItem": { "id": "res-002", "type": "ec2", "size": "t3.large" },
    "IacResourceItem":   { "id": "res-002", "type": "ec2", "size": "t3.small" },
    "State": "Modified",
    "ChangeLog": [
      { "KeyName": "size", "CloudValue": "t3.large", "IacValue": "t3.small" }
    ]
  },
  {
    "CloudResourceItem": { "id": "res-003", "type": "rds", "engine": "postgres" },
    "IacResourceItem": null,
    "State": "Missing",
    "ChangeLog": []
  }
]
```

### Array Drift Example

For a resource where a security group's port list has changed:

```json
{
  "CloudResourceItem": { "id": "sg-001", "ports": [80, 443] },
  "IacResourceItem":   { "id": "sg-001", "ports": [80, 8080] },
  "State": "Modified",
  "ChangeLog": [
    { "KeyName": "ports[1]", "CloudValue": 443, "IacValue": 8080 }
  ]
}
```

---

## Prerequisites

- Python **3.9+**
- pip
- Docker + Docker Compose (for LocalStack S3 bonus)

---

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/your-org/firefly-asset-management.git
cd firefly-asset-management

# 2. Create and activate a virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

# 3. Install Python dependencies
pip install -r requirements.txt
```

---

## Configuration

Place your input JSON files in the `data/` directory before running tests.

**`data/cloud_resources.json`**
```json
[
  { "id": "res-001", "type": "s3",  "region": "us-east-1", "tags": { "env": "prod" } },
  { "id": "res-002", "type": "ec2", "size": "t3.large", "region": "us-west-2" },
  { "id": "res-003", "type": "rds", "engine": "postgres", "region": "us-east-1" }
]
```

**`data/iac_resources.json`**
```json
[
  { "id": "res-001", "type": "s3",  "region": "us-east-1", "tags": { "env": "prod" } },
  { "id": "res-002", "type": "ec2", "size": "t3.small",  "region": "us-west-2" }
]
```

With the above data the framework will produce:

| Resource | State | Reason |
|---|---|---|
| `res-001` | `Match` | All fields identical |
| `res-002` | `Modified` | `size` differs: `t3.large` vs `t3.small` |
| `res-003` | `Missing` | Not present in IaC |

---

## Running the Tests

```bash
# Run full suite with verbose output
pytest tests/ -v

# Run a specific test
pytest tests/test_asset_comparison.py::TestFireflyAssetManagement::test_generate_persistent_report -v

# Run with Allure result collection (for report publishing)
pytest tests/ -v --alluredir=allure-results

# Generate and open Allure HTML report locally
allure serve allure-results
```

The persistent JSON report is written to:
```
reports/comparison_report.json
```

---

## Test Suite Reference

### Core Comparison Tests

| Test | Validates |
|---|---|
| `test_comparison_runs_without_error` | Framework completes without exceptions |
| `test_all_cloud_resources_are_analyzed` | Every cloud resource produces exactly one result |
| `test_state_values_are_valid` | All states are one of `Match` / `Modified` / `Missing` |
| `test_missing_resources_have_no_iac_item` | `Missing` items have `IacResourceItem = null` |
| `test_modified_resources_have_changelog` | `Modified` items have at least one changelog entry |
| `test_match_resources_have_empty_changelog` | `Match` items have an empty changelog |

### Report Structure Tests

| Test | Validates |
|---|---|
| `test_report_is_generated` | Report file exists and is a flat JSON array |
| `test_report_items_have_required_keys` | Every item has all four required top-level keys |
| `test_changelog_entries_use_spec_field_names` | Entries use `KeyName` / `CloudValue` / `IacValue` |
| `test_generate_persistent_report` | Report written to `reports/` is non-empty and spec-compliant |

### Array Comparison Tests

| Test | Validates |
|---|---|
| `test_array_element_difference_detected` | Differing element produces `key[i]` notation entry |
| `test_array_length_difference_detected` | Extra cloud elements appear with `IacValue = null` |
| `test_iac_array_longer_than_cloud` | Extra IaC elements appear with `CloudValue = null` |
| `test_nested_objects_inside_array` | Object inside array uses `key[i].field` notation |
| `test_nested_array_inside_array` | Nested array uses `key[i][j]` chained notation |
| `test_mixed_nested_objects_and_arrays` | Mixed structures produce `obj.arr[i].field` keys |
| `test_identical_arrays_produce_no_changelog` | Matching arrays yield `State: Match` with empty changelog |

---

## Docker & LocalStack S3

The Docker setup runs the full analyzer pipeline in containers and uploads the report to a local S3 bucket — no real AWS account needed.

### Quick Start

```bash
# Build and start both services
docker-compose up --build
```

This will:

1. Start **LocalStack** and auto-create the `firefly-reports` S3 bucket via `init-s3.sh`
2. Build and start the **analyzer** container once LocalStack is healthy
3. Run all pytest tests inside the container
4. Upload `comparison_report.json` to `s3://firefly-reports/`
5. Mount `reports/` to your host machine so you can open the file directly

### Verify the Upload

```bash
# List objects in the bucket
aws --endpoint-url=http://localhost:4566 \
    s3 ls s3://firefly-reports/

# Download and inspect the report
aws --endpoint-url=http://localhost:4566 \
    s3 cp s3://firefly-reports/comparison_report.json ./downloaded_report.json
```

### Run the Uploader Standalone

```bash
# Upload an already-generated report without re-running tests
export S3_ENDPOINT_URL=http://localhost:4566
export S3_BUCKET=firefly-reports
python -m core.s3_uploader
```

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `S3_ENDPOINT_URL` | _(unset = real AWS)_ | LocalStack endpoint, e.g. `http://localhost:4566` |
| `S3_BUCKET` | `firefly-reports` | Target S3 bucket name |
| `AWS_ACCESS_KEY_ID` | `test` | Access key (any value works for LocalStack) |
| `AWS_SECRET_ACCESS_KEY` | `test` | Secret key (any value works for LocalStack) |
| `AWS_DEFAULT_REGION` | `us-east-1` | AWS region |

---

## CI/CD with GitHub Actions & Allure

On every push or pull request to `main`, the pipeline automatically:

1. Sets up Python 3.11 and installs all dependencies
2. Runs the full pytest suite with Allure result collection
3. Restores previous Allure history (enables trend charts across runs)
4. Generates an Allure HTML report
5. Injects `.nojekyll` so GitHub Pages serves Allure's `_` prefixed folders correctly
6. Publishes the report to **GitHub Pages**
7. Uploads both the Allure HTML report and `comparison_report.json` as downloadable build artifacts

### One-Time GitHub Setup

**1. Enable GitHub Pages:**
- Go to `Settings` → `Pages`
- Source: `Deploy from a branch`
- Branch: `gh-pages` / `/ (root)`
- Click **Save**

**2. Set workflow permissions:**
- Go to `Settings` → `Actions` → `General`
- Select **Read and write permissions**
- Click **Save**

### Live Report URL

```
https://<your-github-username>.github.io/<your-repo-name>/
```

### Downloadable Artifacts

After each run, two artifacts are available under **Actions → your workflow run → Artifacts**:

| Artifact | Contents |
|---|---|
| `allure-report` | Full interactive HTML test report |
| `comparison-report-json` | The raw `comparison_report.json` output file |

---

## Changelog Field Reference

All `ChangeLog` entries in the JSON report use these exact field names as required by the specification:

| JSON Key | Type | Example values |
|---|---|---|
| `KeyName` | `string` | `"size"`, `"tags.env"`, `"ports[1]"`, `"rules[0].action"`, `"matrix[1][1]"` |
| `CloudValue` | `any \| null` | `"t3.large"`, `443`, `["prod"]`, `null` |
| `IacValue` | `any \| null` | `"t3.small"`, `8080`, `["prod", "web"]`, `null` |

`null` for `CloudValue` means the field exists in IaC but is absent from the live cloud resource.
`null` for `IacValue` means the field exists in the live cloud resource but is absent from IaC.

---
