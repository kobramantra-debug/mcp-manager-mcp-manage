FROM python:3.13-slim

WORKDIR /app

COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir .

COPY src/ ./src/

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

ENTRYPOINT ["python", "-m", "src"]
