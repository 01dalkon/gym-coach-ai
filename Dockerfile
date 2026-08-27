FROM python:3.12-slim

WORKDIR /app

# git + git-lfs (para el dataset en el repo)
RUN apt-get update && apt-get install -y --no-install-recommends git git-lfs curl \
    && git lfs install \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements primero para mejor caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Dataset de ejercicios (1,324 GIFs + metadata, vía Git LFS)
COPY exercises-dataset ./exercises-dataset

# Copiar app después (cambia más frecuentemente)
COPY app ./app
COPY static ./static
COPY data ./data

ENV DATASET_DIR=/app/exercises-dataset \
    PORT=8000

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# CMD en JSON array form (mejor para signals)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
