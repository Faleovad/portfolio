FROM python:3.12-slim
WORKDIR /srv
COPY backend/requirements-dev.lock ./requirements-dev.lock
RUN pip install --no-cache-dir -r requirements-dev.lock
COPY backend/app ./app
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
