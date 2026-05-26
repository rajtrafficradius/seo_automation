FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir uv
RUN uv sync --all-packages

EXPOSE 8000

CMD ["uv", "run", "--package", "tr-seo-api", "uvicorn", "tr_seo_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
