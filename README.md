# DONPROFESOR — Plataforma de Analítica Educativa Acompañada (#Hack4Edu 2026, Reto 13)

Solución integral desarrollada para el reto de **#Hack4Edu** (ProFuturo) que transforma los datos escolares sobre **asistencia, aprendizaje, formación docente, utilización de recursos y participación** en información comprensible y recomendaciones útiles para **docentes, directores y responsables educativos (delegados territoriales)**, evitando decisiones automáticas sobre estudiantes y garantizando la privacidad de la información desde el motor de base de datos.

---

## Arquitectura de 2 Bloques Conectados a 1 Única Base de Datos Real

El sistema está conectado directamente a la **Base de Datos real** (0 simulación hardcodeada), con esquema preparado para las **37 variables oficiales del Reto 13**:

1. **Las 30 variables de entrada (Bloques A–H):**
   - **Identificación:** `alumno_id`, `escuela_id`, `ugel`, `distrito`, `zona_escuela`
   - **Demografía:** `sexo`, `edad`, `grado_secundaria`, `tamano_familia`
   - **Contexto educativo familiar:** `educacion_madre_0_4`, `educacion_padre_0_4`, `ocupacion_madre`, `ocupacion_padre`, `internet_hogar`, `tiempo_estudio_semanal`
   - **Accesibilidad y trayectoria:** `tiempo_desplazamiento`, `distancia_hogar_escuela_km`, `repeticiones_previas`, `apoyo_escolar`, `apoyo_familiar`
   - **Situación económica:** `beneficiario_juntos`, `horas_trabajo_semanal`
   - **Asistencia escolar:** `dias_lectivos_previstos`, `faltas_trimestre_1`, `faltas_trimestre_2`
   - **Rendimiento académico:** `nota_trimestre_1_0_20`, `nota_trimestre_2_0_20` (escala vigesimal 0-20 oficial de Perú)
   - **Variables calculadas:** `faltas_totales_calculadas`, `asistencia_pct_calculada`, `promedio_notas_calculado`

2. **Las 7 variables de salida del Modelo Predictivo (Bloque I):**
   - `prob_abandono_pct`, `prediccion_nota_t3`, `prediccion_faltas_t3`, `prob_perdida_beca_pct`, `prob_repeticion_pct`, `necesidad_intervencion`, `indice_desanimo`.

---

## Flujos del Sistema (Persona 3 y Persona 4)

- **Bloque 1 · Dashboard Web React (`web/frontend/`):**
  - Consulta en tiempo real las vistas SQL (`vista_docente`, `vista_director`, `vista_delegado`, `vista_avisos_predictivos`).
  - Si la base de datos está vacía (0 registros), muestra el estado limpio indicando que está lista para recibir datos.
  - Al cargar los registros, calcula dinámicamente los promedios de asistencia, notas sobre 20, horas de estudio, estudiantes en Programa Juntos y alertas del modelo predictivo.
- **Bloque 2 · Chat con LLM conectado vía MCP (`mcp_server/`):**
  - El servidor MCP expone `list_tables`, `describe_table` y `read_query` con control estricto de ámbito por rol.
  - El LLM ejecuta consultas SQL reales y devuelve respuestas comprensibles en lenguaje pedagógico humano.

---

## Carga e Importación de Datos

### Importar el CSV del Reto 13
Cuando el equipo tenga listo el CSV con los datos, se importa directamente con:
```bash
pixi run python db/import_csv.py --csv ruta/al/archivo.csv
```
*(También disponible vía API mediante `POST /api/datos/importar-csv`)*

### Vaciar la base de datos (volver a estado limpio)
```bash
pixi run python db/import_csv.py --clear
```

### Generar datos de prueba realistas (opcional, para demos antes de la entrega final)
```bash
pixi run python db/import_csv.py --sample 40
```

---

## Ejecución con Pixi

```bash
# Iniciar servidor y frontend React en http://localhost:8000
pixi run start

# Ejecutar las pruebas automatizadas de integración
pixi run test

# Reconstruir el bundle de React
pixi run build
```

---

## Conexión con PostgreSQL Externa
Para conectar a la base de datos PostgreSQL definitiva del equipo, basta con configurar:
```bash
# En PowerShell:
$env:DATABASE_URL="postgresql://usuario:clave@host:5432/donprofesor"
pixi run start

# En Bash:
export DATABASE_URL="postgresql://usuario:clave@host:5432/donprofesor"
pixi run start
```
