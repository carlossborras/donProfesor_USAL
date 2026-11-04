# DONPROFESOR — Plataforma de Analítica Educativa Acompañada (#Hack4Edu 2026, Reto 13)

Solución integral desarrollada para el reto de **#Hack4Edu** (ProFuturo) que transforma los datos escolares sobre **asistencia, aprendizaje, formación docente, utilización de recursos y participación** en información comprensible y recomendaciones útiles para **docentes, directores y responsables educativos (delegados territoriales)**, evitando decisiones automáticas sobre estudiantes y garantizando la privacidad de la información desde el motor de base de datos.

Diseño e interfaz inspirados en **EduSight Faro Educativo** (Figma Oficial).

---

## Inicio Rápido para Compañeros de Equipo

Si acabas de clonar el repositorio, sigue estos pasos:

```bash
# 1. Clonar el repositorio
git clone https://github.com/carlossborras/hack4edu.git
cd hack4edu

# 2. Configurar variables de entorno (apuntando a tu vLLM local o remoto)
cp .env.example .env
# Si ejecutas vLLM en esta misma máquina, edita .env con QWEN_BASE_URL=http://localhost:8001/v1

# 3. Arrancar el sistema (backend FastAPI + frontend React compilado)
pixi run start
```

Abre tu navegador en `http://localhost:8000` (o `http://127.0.0.1:8000`).

---

## Arquitectura de 3 Componentes Integrados

### 1. Base de Datos Relacional y API (FastAPI + SQLite / PostgreSQL)
- Esquema de 37 variables oficiales del Reto 13 (30 de entrada + 7 calculadas/predichas).
- Vistas SQL por rol con filtrado ético y minimización de datos:
  - `vista_docente`: Visión de aula y acompañamiento pedagógico.
  - `vista_director`: Agregados por grado, alertas tempranas y gestión del centro.
  - `vista_delegado`: Comparativas territoriales anónimas entre escuelas/UGEL.
  - `vista_avisos_predictivos`: Estudiantes con indicadores prioritarios.
- Registro inmutable de trazabilidad ética: `registro_accion_humana`.

### 2. Modelo Predictivo Explicable (Persona 2 - Machine Learning)
- Pipeline en Python con `scikit-learn` en `model/train_predict.py`.
- Entrena modelos Random Forest para predecir las 7 variables objetivo:
  - `prob_abandono_pct`, `prediccion_nota_t3`, `prediccion_faltas_t3`, `prob_perdida_beca_pct`, `prob_repeticion_pct`, `necesidad_intervencion`, `indice_desanimo`.
- Extrae el factor principal de riesgo y genera recomendaciones pedagógicas contextualizadas.
- Incluye checkpoint preentrenado en `model/checkpoints/donprofesor_rf_models.pkl` y dataset sintético completo en `data/ejemplo_50_alumnos_con_predicciones.csv`.

Comandos del modelo:
```bash
# Entrenar con dataset
pixi run train
# o: pixi run python -m model.train_predict --action train --dataset data/tu_dataset.csv

# Predecir sobre nuevos alumnos sin notas de T3
pixi run predict
# o: pixi run python -m model.train_predict --action predict --input nuevos_alumnos.csv --output con_predicciones.csv
```

### 3. Agente ReAct con LangGraph y LLM Qwen (Bloque Chat MCP)
- Agente ReAct implementado con `langgraph.prebuilt.create_react_agent`.
- Herramientas MCP integradas: `list_authorized_views`, `describe_view`, `execute_sql_query`.
- Conectado al servidor vLLM de Qwen (vLLM en puerto `8001`).
- Estilo pedagógico humano, empático, sin emojis y con trazabilidad de consultas SQL ejecutadas.

---

## Carga e Importación de Datos

### Importar el CSV con datos reales del Reto 13
```bash
pixi run python db/import_csv.py --csv data/ejemplo_50_alumnos_con_predicciones.csv
```
*(También se puede cargar arrastrando el archivo en el botón "Subir CSV" de la barra superior de la web)*.

### Cargar 30 alumnos de prueba para demostración instantánea
Haz clic en el botón **"Cargar 30 alumnos de prueba"** en la barra superior de la interfaz web, o ejecuta:
```bash
pixi run python db/import_csv.py --sample 30
```

### Vaciar la base de datos (volver a estado limpio)
Haz clic en **"Vaciar BD"** en la interfaz web, o ejecuta:
```bash
pixi run python db/import_csv.py --clear
```

---

## Scripts Disponibles en Pixi

```bash
# Iniciar servidor y frontend React en http://localhost:8000
pixi run start

# Ejecutar pruebas automatizadas de integración
pixi run test

# Reconstruir el bundle de React
pixi run build

# Entrenar modelos de Machine Learning
pixi run train

# Generar predicciones con el modelo
pixi run predict
```

---

## Conexión con PostgreSQL Externa (Producción)
Para conectar a la base de datos PostgreSQL definitiva del equipo:
```bash
# En PowerShell:
$env:DATABASE_URL="postgresql://usuario:clave@host:5432/donprofesor"
pixi run start

# En Bash:
export DATABASE_URL="postgresql://usuario:clave@host:5432/donprofesor"
pixi run start
```
