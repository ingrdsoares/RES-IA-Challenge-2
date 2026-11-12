FROM python:3.12-slim
WORKDIR /srv

ARG APP_VERSION=0.1.0
ARG GIT_COMMIT_SHA=development
ARG BUILD_TIMESTAMP=unknown
ENV APP_VERSION=$APP_VERSION \
    GIT_COMMIT_SHA=$GIT_COMMIT_SHA \
    BUILD_TIMESTAMP=$BUILD_TIMESTAMP

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app app
COPY alembic.ini .
COPY migrations migrations
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
