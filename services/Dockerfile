FROM python:3.13-slim
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir --require-hashes -r requirements.lock
COPY services ./services
COPY migrations ./migrations
ENV PYTHONPATH=/app/services
CMD ["python","-m","uvicorn","polyquant.api:app","--host","0.0.0.0","--port","8000"]
