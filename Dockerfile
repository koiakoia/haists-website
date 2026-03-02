FROM python:3.12-slim AS builder
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim
RUN useradd -r -u 1001 -g root appuser
WORKDIR /app
COPY --from=builder /install /usr/local
COPY backend/ /app/backend/
COPY frontend/ /app/frontend/
USER 1001
EXPOSE 8080
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
