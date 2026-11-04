# DONPROFESOR — Plataforma de Analítica Educativa Acompañada (#Hack4Edu)

Solución integral desarrollada para el reto de **#Hack4Edu** (ProFuturo) que transforma los datos escolares sobre **asistencia, aprendizaje, formación docente, utilización de recursos y participación** en información comprensible y recomendaciones útiles para **docentes, directores y responsables educativos (delegados territoriales)**, evitando decisiones automáticas sobre estudiantes y garantizando la privacidad de la información desde el motor de base de datos.

---

## Arquitectura del Sistema (Persona 3 y Persona 4)

El sistema se divide en **dos grandes flujos** conectados a la Base de Datos mediante un **Adaptador Desacoplado (`db/adapter.py`)** con control de acceso por rol:

1. **Adaptador de Base de Datos Provisional -> Definitiva (`db/adapter.py`):**
   - Mientras el compañero encargado de la base de datos finaliza la carga definitiva, la plataforma arranca automáticamente en **modo provisional (`PROVISIONAL_SQLITE_SEED`)** con las vistas `vista_docente`, `vista_director`, `vista_director_clima`, `vista_delegado` y `vista_avisos_predictivos` listas desde el minuto uno.
   - En cuanto esté disponible la base de datos PostgreSQL definitiva del equipo, basta con definir la variable de entorno `DATABASE_URL=postgresql://usuario:clave@host:5432/donprofesor` y el adaptador conmuta automáticamente sin tocar ni una línea de React ni de FastAPI.

2. **Aplicación React Modular con los 3 Paneles y el Modelo Predictivo (`web/frontend/` + `GET /api/panel`):**
   - Arquitectura limpia de componentes React en `web/frontend/src/components/`:
     - `EthicalBanner.jsx`: Aviso pedagógico fijo (*«La decisión es tuya; el modelo puede equivocarse»*), estado del adaptador de BD y permisos SQL activos.
     - `Navbar.jsx`: Selector de los 3 paneles por rol y sesión JWT.
     - `KpiGrid.jsx`: Indicadores de las 5 dimensiones educativas del reto.
     - `PredictiveAlertsPanel.jsx`: Tarjetas de observaciones del modelo predictivo con los **3 factores explicativos que más pesan** en texto humano y botón para registrar la decisión profesional.
     - `RainHarvestChart.jsx`: **Gráfica estrella** interactiva que superpone asistencia semanal, lluvia (mm), semanas de cosecha comarcal y utilización de recursos.
     - `RoleViews.jsx`:
       - **Panel Docente (`DocenteContextTable`):** Su clase (`2º Secundaria B`), filtros contextuales (distancia > 3 km / lluvia, cosecha, beca protectora), **sin rankings ni colores de semáforo por alumno**.
       - **Panel Dirección (`DirectorGroupsTable`):** Comparativa agregada entre grupos del centro, horas de formación docente práctica y brecha de uso de recursos.
       - **Panel Delegado Territorial (`DelegadoTerritorialView`):** Mapa espacial de escuelas con brechas de conectividad y **simulador interactivo de reparto de subvenciones**.
     - `McpChatSidebar.jsx`: Panel lateral de consulta en lenguaje natural conectado al Servidor MCP con visualización de la traza SQL ejecutada.
     - `Modals.jsx`: Modal de cambio de sesión JWT por rol y modal de registro de decisiones humanas.

3. **Chat con Modelo de Lenguaje (LLM) conectado a la Base de Datos vía MCP (`POST /api/chat-mcp`):**
   - Servidor **MCP (`Model Context Protocol`)** en `mcp_server/db_mcp_server.py` que expone las 3 herramientas estándar:
     - `list_tables(rol)`
     - `describe_table(rol, table_name)`
     - `read_query(rol, ambito_id, sql_query)`
   - Cada consulta respeta estrictamente el rol del token JWT (`role_docente`, `role_director`, `role_delegado`) y solo tiene permiso `GRANT SELECT` sobre las vistas autorizadas de ese rol.

---

## Estructura del Repositorio

```text
hack4edu/
├── db/
│   ├── adapter.py                      # Adaptador desacoplado (Semilla Provisional <-> PostgreSQL externo)
│   ├── schema.sql                      # Esquema relacional de las 5 dimensiones + tabla prediccion
│   ├── views_and_grants.sql            # Vistas SQL por rol (k-anonimato) y GRANT SELECT
│   └── seed_db.py                      # Semilla provisional lista desde el minuto uno
├── mcp_server/
│   ├── db_mcp_server.py                # Servidor MCP de Base de Datos (list_tables, describe_table, read_query)
│   └── chat_agent.py                   # Agente de Chat conectado al Servidor MCP (+ soporte Gemini API)
├── api/
│   └── main.py                         # FastAPI con JWT, Middleware de rol/ámbito y Endpoints del contrato
├── web/
│   ├── app.py                          # Lanzador directo con sys.path configurado para ejecución desde raíz
│   └── frontend/                       # Aplicación React modular (Persona 4)
│       ├── package.json
│       ├── vite.config.js
│       ├── index.html
│       └── src/
│           ├── main.jsx
│           ├── App.jsx
│           ├── services/api.js
│           ├── styles/app.css
│           └── components/
│               ├── EthicalBanner.jsx
│               ├── Navbar.jsx
│               ├── KpiGrid.jsx
│               ├── PredictiveAlertsPanel.jsx
│               ├── RainHarvestChart.jsx
│               ├── RoleViews.jsx
│               ├── McpChatSidebar.jsx
│               └── Modals.jsx
├── tests/
│   └── test_donprofesor.py             # Pruebas automatizadas de JWT, Vistas SQL, MCP, Adaptador BD y React
├── Dockerfile
└── docker-compose.yml                  # Despliegue completo con PostgreSQL + Aplicación
```

---

## Ejecución Rápida

### Opción A: Ejecución directa con `uv` (arranca Backend + Frontend React en `http://localhost:8000`)
```bash
uv sync
uv run python web/app.py
```
Abre en el navegador: `http://localhost:8000`

### Opción B: Desarrollo Frontend con Vite (opcional si tienes Node.js instalado)
```bash
cd web/frontend
npm install
npm run dev
```

### Opción C: Conectar a la Base de Datos PostgreSQL definitiva del equipo
```bash
# En PowerShell:
$env:DATABASE_URL="postgresql://postgres:postgres@localhost:5432/donprofesor"
uv run python web/app.py
```

### Ejecutar las pruebas automatizadas
```bash
uv run pytest -v
```
