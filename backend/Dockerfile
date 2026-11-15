FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
COPY pyproject.toml requirements.lock ./
COPY app ./app
RUN pip install --no-cache-dir -r requirements.lock && pip install --no-cache-dir --no-deps . && useradd --create-home cci
RUN python -m playwright install --with-deps --no-shell chromium && chmod -R a+rX /ms-playwright
COPY alembic.ini ./
COPY alembic ./alembic
RUN mkdir -p /app/var/capital-markets && chown -R cci:cci /app/var
USER cci
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
