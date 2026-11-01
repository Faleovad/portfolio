FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY backend ./backend
RUN pip install --no-cache-dir .
COPY sql ./sql
COPY tools ./tools
ENV PYTHONPATH=/app/backend
CMD ["python","-m","platform_core.worker"]
