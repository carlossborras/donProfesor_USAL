# 1) Compila el frontend React (así la imagen nunca usa un dist/ desactualizado)
FROM node:20-slim AS frontend
WORKDIR /frontend
COPY web/frontend/package.json web/frontend/package-lock.json ./
RUN npm ci
COPY web/frontend/ ./
RUN npm run build

# 2) API + modelo
FROM python:3.11-slim

WORKDIR /app

# libgomp1: la necesita LightGBM (modelo de predicción del equipo)
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir fastapi uvicorn pyjwt cryptography sqlalchemy psycopg2-binary httpx pydantic \
    python-multipart mcp plotly pandas numpy scikit-learn lightgbm joblib langgraph langchain-core langchain-openai

COPY db/ ./db/
COPY model/ ./model/
COPY scripts/ ./scripts/
COPY data/ ./data/
COPY mcp_server/ ./mcp_server/
COPY api/ ./api/
COPY web/ ./web/
COPY --from=frontend /frontend/dist ./web/frontend/dist
# Modelo entrenado por el equipo (LightGBM + Random Forest). Sin él la API arranca, pero las
# predicciones quedan «pendientes» y se avisa en la interfaz.
COPY modelo.joblib ./modelo.joblib

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
