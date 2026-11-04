# DONPROFESOR — Plataforma de Analítica Educativa Acompañada (#Hack4Edu)

Solución integral desarrollada para el reto de **#Hack4Edu** (ProFuturo) que transforma los datos escolares sobre **asistencia, aprendizaje, formación docente, utilización de recursos y participación** en información comprensible y recomendaciones útiles para **docentes, directores y responsables educativos (delegados territoriales)**, evitando decisiones automáticas sobre estudiantes y garantizando la privacidad de la información desde el motor de base de datos.

---

## Arquitectura del Sistema (Persona 3 y Persona 4)

El sistema se divide en **dos grandes flujos** conectados a una única Base de Datos con control de acceso por rol:

1. **Dashboard alimentado por el Modelo Predictivo (`GET /api/panel`):**
   - Muestra los **5 indicadores clave del reto**, la **bandeja de observaciones del modelo predictivo** (con los 3 factores explicativos que más pesan en lenguaje humano y el botón para registrar la decisión humana) y las **visualizaciones específicas de cada rol**:
     - **Panel Docente:** Su clase (`2º Secundaria B`), seguimiento contextual de alumnos sin rankings ni colores de semáforo individuales y registro de acciones pedagógicas.
     - **Panel Dirección de Centro:** La **gráfica estrella** que superpone la asistencia semanal con los milímetros de lluvia, las semanas de cosecha comarcal y la utilización de recursos, más la comparativa entre grupos y horas de formación docente.
     - **Panel Delegado Territorial:** Mapa de escuelas de la red con brechas de conectividad/uso de recursos y un **simulador interactivo de reparto de subvenciones** (becas de transporte rural vs. formación docente vs. servidores offline).
   - Incluye en todos los paneles el aviso permanente: *«La decisión es tuya; el modelo puede equivocarse»*.

2. **Chat con Modelo de Lenguaje (LLM) conectado a la Base de Datos vía MCP (`POST /api/chat-mcp`):**
   - Un servidor **MCP (`Model Context Protocol`)** en `mcp_server/db_mcp_server.py` que expone las 3 herramientas estándar de base de datos:
     - `list_tables(rol)`
     - `describe_table(rol, table_name)`
     - `read_query(rol, ambito_id, sql_query)`
   - Cada consulta ejecutada por el Chat respeta estrictamente el rol del token JWT (`role_docente`, `role_director`, `role_delegado`) y solo tiene permiso `GRANT SELECT` sobre las vistas autorizadas de ese rol (`vista_docente`, `vista_director`, `vista_director_clima`, `vista_delegado`, `vista_avisos_predictivos`).

---

## Estructura del Repositorio

```text
hack4edu/
├── db/
│   ├── schema.sql              # Esquema relacional de las 5 dimensiones + tabla prediccion
│   ├── views_and_grants.sql    # Vistas SQL por rol (k-anonimato) y GRANT SELECT
│   └── seed_db.py              # Semilla de datos lista desde el minuto uno
├── mcp_server/
│   ├── db_mcp_server.py        # Servidor MCP de Base de Datos (list_tables, describe_table, read_query)
│   └── chat_agent.py           # Agente de Chat conectado al Servidor MCP (+ soporte Gemini API)
├── api/
│   └── main.py                 # FastAPI con JWT, Middleware de rol/ámbito y Endpoints del contrato
├── web/
│   ├── app.py                  # Punto de entrada de la aplicación web
│   └── templates/
│       └── index.html          # Interfaz DONPROFESOR (3 paneles, 0 emoticonos, lenguaje humano)
├── tests/
│   └── test_donprofesor.py     # Pruebas automatizadas de JWT, Vistas SQL, MCP y Registro de Acciones
├── Dockerfile
└── docker-compose.yml          # Despliegue completo con PostgreSQL + Aplicación
```

---

## Ejecución Rápida

### Opción A: Ejecución directa con `uv` / Python (sin necesidad de Docker)
```bash
uv sync
uv run python web/app.py
```
Abre en el navegador: `http://localhost:8000`

### Opción B: Con Docker Compose (PostgreSQL + Backend/Frontend)
```bash
docker compose up --build
```

### Ejecutar las pruebas automatizadas
```bash
uv run pytest -v
```
