FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Use Railway's PORT (default 8000 if not set)
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}