# DONPROFESOR — Plataforma de Analítica Educativa Acompañada (#Hack4Edu 2026, Reto 13)

Solución integral desarrollada para el reto de **#Hack4Edu** (ProFuturo) que transforma los datos escolares sobre **asistencia, aprendizaje, formación docente, utilización de recursos y participación** en información comprensible y recomendaciones útiles para **docentes, directores y responsables educativos (delegados territoriales)**, evitando decisiones automáticas sobre estudiantes y garantizando la privacidad de la información desde el motor de base de datos.

Diseño e interfaz inspirados en **EduSight Faro Educativo** (Figma Oficial).

---

## Inicio Rápido para Compañeros de Equipo

Si acabas de clonar el repositorio, sigue estos pasos:

```bash
# 0. Requisito (una vez): instalar pixi
curl -fsSL https://pixi.sh/install.sh | sh && export PATH="$HOME/.pixi/bin:$PATH"

# 1. Clonar el repositorio
git clone https://github.com/carlossborras/hack4edu.git
cd hack4edu

# 2. Instalar el entorno (Python, scikit-learn 1.6.1, LightGBM, Node...) y las dependencias del frontend
pixi install
pixi run npm --prefix web/frontend install

# 3. Configurar variables de entorno (LLM, JWT, umbrales del modelo...)
cp .env.example .env

# 4. Comprobar el modelo y arrancar (backend FastAPI + frontend React compilado)
pixi run modelo-estado     # debe decir "disponible": true
pixi run start
```

> El modelo se entrenó con scikit-learn 1.6.1: no cambies esa versión o `modelo.joblib` no se podrá leer.

Abre tu navegador en `http://localhost:8000` (o `http://127.0.0.1:8000`).

---

## Acceso con cuenta y vistas por rol (login y registro)

Al abrir `http://localhost:8000` aparece la pantalla de **Iniciar sesión / Crear cuenta**. Cada persona ve solo la vista de su rol y los datos de su ámbito, que se fija al registrarse y viaja dentro del token:

| Rol | Ámbito que pide el registro | Qué ve en «Cómo vamos» |
|---|---|---|
| **Docente** | Escuela + grado (1.º–5.º) | Su grupo alumno a alumno (ordenado por código, sin rankings): notas por trimestre, faltas, reparto de asistencia y de notas, asistencia frente a distancia, contexto (trabajo, internet, distancia, Juntos) y «Sugerir revisión» con factores explicados. **Nunca** probabilidades ni etiquetas de riesgo. |
| **Director/a** | Escuela | Su escuela agregada por grado: asistencia, notas T1→T2, faltas T1→T2, sugerencias de revisión e internet en casa. |
| **Delegado/a UGEL** | UGEL | Sus escuelas: asistencia, internet en casa con umbral de brecha, comparativa rural/urbana, sugerencias por escuela y lista de escuelas con brechas. |

La pestaña **«Predicciones»** muestra lo que prevé el modelo, ordenado por el interés de cada rol (docente: niveles por estudiante sin porcentajes; director: por grado; delegado: por escuela y zona).

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

### 2. Modelo predictivo (LightGBM + Random Forest, Persona 2)
- Se entrena con `entrenadorModelo.py` (Carlos) y se guarda en `modelo.joblib` (ruta configurable con `DONPROFESOR_MODEL_PATH`).
- **Cada vez que se da de alta, se importa (CSV o pegado) o se carga la muestra de un estudiante, la API ejecuta el modelo al momento** (`db/students.py` -> `model/predictor.py`) y guarda:
  - probabilidades de abandono, pérdida de la beca Juntos (solo si la familia está en Juntos) y repetición;
  - necesidad de intervención (Alta / Media / Baja);
  - notas y faltas previstas de los tres trimestres e índice de desánimo (0-10);
  - los 3 factores que más empujan la sugerencia de ese estudiante (por oclusión; el sexo nunca se usa como explicación) y una recomendación pedagógica.
- Si el modelo no está disponible, el estudiante se guarda igual y sus predicciones quedan **pendientes** (nunca se inventan). Se calculan después con «Recalcular predicciones» o `pixi run recalcular`.
- Umbrales de lectura (alto / medio), k-anonimato y moneda del simulador se configuran en `.env` (ver `.env.example`).

Comandos del modelo:
```bash
pixi run train            # reentrena con entrenadorModelo.py (deja el .joblib en la raíz)
pixi run modelo-estado    # comprueba que la API puede cargar el modelo
pixi run recalcular       # recalcula las predicciones de todos los estudiantes
pixi run python -m scripts.predicciones recalcular --solo-pendientes
```

### 3. Agente ReAct con LangGraph y LLM Qwen (Bloque Chat MCP)
- Agente ReAct implementado con `langgraph.prebuilt.create_react_agent`.
- Herramientas MCP integradas: `list_authorized_views`, `describe_view`, `execute_sql_query`.
- Conectado al servidor vLLM de Qwen (vLLM en puerto `8001`).
- Estilo pedagógico humano, empático, sin emojis y con trazabilidad de consultas SQL ejecutadas.

---

## Carga e Importación de Datos

Desde la barra superior de la web (siempre dentro del ámbito de tu sesión):
- **+ Añadir estudiante**: formulario generado a partir de los campos del modelo, o pegar filas desde una hoja de cálculo.
- **Importar CSV**: CSV/TSV con cabecera; la columna `alumno_id` es obligatoria. El docente solo puede cargar en su grupo, el director en su escuela y el delegado en su UGEL (las filas de otra UGEL se rechazan).
- **Cargar datos de demostración**: copia `data/muestra_30_alumnos_peru.csv` en tu ámbito.
- **Limpiar datos**: borra solo los estudiantes de tu ámbito.

Por línea de comandos:
```bash
pixi run python -m scripts.predicciones cargar --csv data/muestra_30_alumnos_peru.csv --escuela ESC-01 --ugel "UGEL Cusco"
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

# Reentrenar el modelo (entrenadorModelo.py)
pixi run train

# Estado del modelo y recálculo de predicciones
pixi run modelo-estado
pixi run recalcular
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
