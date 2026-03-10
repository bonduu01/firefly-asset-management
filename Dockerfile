# ── Firefly Asset Analyzer — Application Container ───────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY core/       ./core/
COPY data/       ./data/
COPY tests/      ./tests/
COPY conftest.py .

# Create the output directory for reports
RUN mkdir -p reports

# Default command: run tests then upload report to S3
CMD ["sh", "-c", "pytest tests/ -v --tb=short && python -m core.s3_uploader"]