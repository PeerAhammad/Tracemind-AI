FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
# backend/ and benchmarks/ must stay siblings: the app reads ../benchmarks relative to backend/
COPY backend backend
COPY benchmarks benchmarks
WORKDIR /app/backend
# Free hosts have an ephemeral disk: the SQLite file resets on restart (example data can be reloaded from the API).
ENV TRACEMIND_DB=/tmp/tracemind.db
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
