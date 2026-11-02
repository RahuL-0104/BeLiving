FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV HOST=0.0.0.0 PORT=8006 WORKERS=2 PYTHONUNBUFFERED=1
EXPOSE 8006
RUN useradd -m appuser
USER appuser
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request,os;urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/healthz')"
# Pass secrets at run time (--env-file .env or your platform's secret store); never bake them into the image.
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT} --workers ${WORKERS} --proxy-headers --forwarded-allow-ips='*'"]
