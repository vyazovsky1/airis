FROM python:3.11-slim

WORKDIR /app

# System deps: curl for healthchecks; no kubectl needed until kubernetes_utils
# switches from mocks to real cluster calls
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (layer cache friendly)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application source
COPY src/      ./src/
COPY prompts/  ./prompts/
COPY examples/ ./examples/

# Runtime cache directory for intent files and run_findings.csv
RUN mkdir -p .data

ENTRYPOINT ["python", "src/main.py"]
