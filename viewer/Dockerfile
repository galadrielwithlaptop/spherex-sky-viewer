FROM python:3.13-slim
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV SPHEREX_BIND=0.0.0.0 SPHEREX_PORT=8765 SPHEREX_CACHE_DIR=/data
VOLUME /data
EXPOSE 8765
CMD ["python", "server.py"]
