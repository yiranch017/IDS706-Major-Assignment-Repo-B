FROM python:3.12-slim

# Headless plotting: figures are saved to files, never shown.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MPLBACKEND=Agg \
    MPLCONFIGDIR=/tmp/matplotlib

WORKDIR /app

COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

# Code, tests and tiny synthetic fixtures only. Real raw data and outputs are
# excluded by .dockerignore and mounted at runtime:
#   /app/data/raw  (read-only)    /app/outputs  (writable)
COPY main.py pytest.ini ./
COPY src/ src/
COPY tests/ tests/
COPY data/fixtures/ data/fixtures/
RUN mkdir -p data/raw outputs/data outputs/tables outputs/figures

# Default command runs the real Stage 1 pipeline.
CMD ["python", "main.py"]
