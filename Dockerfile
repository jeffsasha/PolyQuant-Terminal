FROM python:3.13-slim
WORKDIR /app
RUN useradd --create-home --uid 10001 polyquant
COPY pyproject.toml README.md ./
COPY services ./services
RUN pip install --no-cache-dir .
USER polyquant
EXPOSE 8787
CMD ["polyquant", "run"]
