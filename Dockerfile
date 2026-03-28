FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY toolops/ toolops/

RUN pip install --no-cache-dir .

EXPOSE 9000

CMD ["uvicorn", "toolops.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "9000"]
