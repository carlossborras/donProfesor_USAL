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

## Acceso con cuenta y vistas por rol (login y registro)

Al abrir `http://localhost:8000` aparece la pantalla de **Iniciar sesión / Crear cuenta**. Cada persona ve solo la vista de su rol y los datos de su ámbito, que se fija al registrarse y viaja dentro del token:

| Rol | Ámbito que pide el registro | Qué ve en «Cómo vamos» |
|---|---|---|
| **Docente** | Escuela + grado (1.º–5.º) | Su grupo alumno a alumno (ordenado por código, sin rankings): notas por trimestre, faltas, reparto de asistencia y de notas, asistencia frente a distancia, contexto (trabajo, internet, distancia, Juntos) y «Sugerir revisión» con factores explicados. **Nunca** probabilidades ni etiquetas de riesgo. |
| **Director/a** | Escuela | Su escuela agregada por grado: asistencia, notas T1→T2, faltas T1→T2 (efecto cosecha), sugerencias de revisión e internet en casa. |
| **Delegado/a UGEL** | UGEL | Sus escuelas: asistencia, internet en casa con umbral de brecha, comparativa rural/urbana, sugerencias por escuela y lista de escuelas con brechas. |

Reglas de privacidad aplicadas en el servidor: consultas parametrizadas y filtradas por el ámbito del token, y **k-anonimato (k ≥ 5)** en los datos agregados (los grados o escuelas con menos de 5 estudiantes se ocultan). Con la base de datos vacía, los paneles muestran ceros y un aviso; no se inventan datos.

**Usuarios de demostración** (se siguen creando al iniciar): `docente`, `director`, `delegado` con contraseña `donprofesor2026`.

**Endpoints**

| Método y ruta | Acceso | Uso |
|---|---|---|
| `POST /api/auth/register` | público | Crea la cuenta (rol + ámbito) y devuelve la sesión (201). 409 si el usuario existe, 422 si faltan datos |
| `POST /api/auth/login` | público | `{access_token, token_type, expires_in, user}`; 401 genérico si falla |
| `GET /api/auth/me` | con sesión | Usuario actual (la web lo usa para validar la sesión al recargar) |
| `GET /api/auth/opciones-registro` | público | Roles, escuelas/UGEL conocidas y si cada rol pide código de invitación |
| `GET /api/dashboard` | con sesión | Panel con gráficos del rol de la sesión |
| `GET /api/dashboard/{rol}` | con sesión | Igual, pero **403** si `{rol}` no es el tuyo |

**Seguridad**
- Contraseñas con **PBKDF2-SHA256 (600 000 iteraciones)**, solo librería estándar. Las cuentas antiguas en texto plano se re-cifran solas al entrar.
- Tokens JWT de **8 horas** (`DONPROFESOR_JWT_EXPIRE_HOURS`). Define `DONPROFESOR_JWT_SECRET` (mín. 32 caracteres) en `.env`; si falta, la API usa uno temporal y las sesiones caducan al reiniciar.
- Registro con **código de invitación opcional por rol**: `DONPROFESOR_CODIGO_REGISTRO_DOCENTE`, `..._DIRECTOR`, `..._DELEGADO`. Recomendado para director y delegado.
- La sesión del navegador se guarda en `sessionStorage` (se borra al cerrar la pestaña).

Pruebas: `pixi run test` (incluye `tests/test_auth_dashboards.py`, que usa una base de datos temporal y no toca `db/donprofesor.db`).

> Tras cambiar el frontend hay que recompilarlo: `pixi run build` (lo hace solo `pixi run start`).

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
