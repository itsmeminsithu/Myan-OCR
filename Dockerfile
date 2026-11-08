FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OMP_THREAD_LIMIT=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-mya tesseract-ocr-eng libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
COPY web/ ./web/
RUN useradd -m -u 10001 myanocr
USER myanocr
EXPOSE 8388
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8388", "--workers", "1"]
