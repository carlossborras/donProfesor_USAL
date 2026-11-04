FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir fastapi uvicorn pyjwt sqlalchemy psycopg2-binary httpx pydantic python-multipart mcp google-genai plotly pandas numpy

COPY db/ ./db/
COPY mcp_server/ ./mcp_server/
COPY api/ ./api/
COPY web/ ./web/

RUN python -m db.seed_db

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
