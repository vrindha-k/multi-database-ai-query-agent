FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY app ./app
COPY tests ./tests
COPY examples ./examples
RUN pip install --no-cache-dir uv && uv sync --frozen --extra dev --no-editable \
    && useradd --create-home agent
ENV PATH="/app/.venv/bin:$PATH"
USER agent
CMD ["python", "-m", "app.cli"]
