FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl unzip ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY mcp_servers ./mcp_servers
COPY tests ./tests
COPY .env.example ./.env.example

EXPOSE 8080 8001 8002 8003

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
