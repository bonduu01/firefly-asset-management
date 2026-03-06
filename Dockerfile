FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY core/        ./core/
COPY data/        ./data/
COPY tests/       ./tests/
COPY conftest.py  .

# Create output directory for the report
RUN mkdir -p reports

# Default: run tests and generate the comparison report
CMD ["pytest", "tests/", "-v", "--tb=short"]