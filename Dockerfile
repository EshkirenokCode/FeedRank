FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OMP_NUM_THREADS=2
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.lock
RUN useradd --uid 10001 --create-home feedrank \
    && mkdir -p /app/runtime && chown 10001:10001 /app/runtime
COPY feedrank/ ./feedrank/
COPY catalog/ ./catalog/
COPY artifacts/ ./artifacts/
COPY reports/ ./reports/
COPY --from=web /web/dist ./frontend/dist
USER 10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=30s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"
CMD ["uvicorn", "feedrank.api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*"]
