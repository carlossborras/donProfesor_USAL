-- =============================================================================
-- DONPROFESOR (#Hack4Edu 2026, Reto 13) · Esquema de Base de Datos Real
-- Contiene las 30 variables de entrada (Bloques A-H) + 7 variables del Modelo Predictivo (Bloque I)
-- =============================================================================

DROP VIEW IF EXISTS vista_docente;
DROP VIEW IF EXISTS vista_director;
DROP VIEW IF EXISTS vista_delegado;
DROP VIEW IF EXISTS vista_avisos_predictivos;

CREATE TABLE IF NOT EXISTS alumnos_hack4edu (
    -- A. Identificación y ubicación
    alumno_id VARCHAR(32) PRIMARY KEY,
    escuela_id VARCHAR(32) NOT NULL,
    ugel VARCHAR(80) NOT NULL,
    distrito VARCHAR(80) NOT NULL,
    zona_escuela VARCHAR(20) NOT NULL, -- 'Rural' / 'Urbana'

    -- B. Datos demográficos
    sexo VARCHAR(10) NOT NULL, -- 'M' / 'F'
    edad INTEGER NOT NULL,
    grado_secundaria INTEGER NOT NULL, -- 1 a 5
    tamano_familia INTEGER NOT NULL,

    -- C. Contexto educativo familiar
    educacion_madre_0_4 INTEGER NOT NULL, -- 0: Sin educ, 1: Primaria, 2: Secundaria, 3: Sup. no univ, 4: Universitaria
    educacion_padre_0_4 INTEGER NOT NULL,
    ocupacion_madre VARCHAR(80) NOT NULL,
    ocupacion_padre VARCHAR(80) NOT NULL,
    internet_hogar INTEGER NOT NULL, -- 1: Sí, 0: No
    tiempo_estudio_semanal NUMERIC(4,1) NOT NULL, -- horas semanales

    -- D. Accesibilidad y trayectoria académica
    tiempo_desplazamiento INTEGER NOT NULL, -- minutos al colegio
    distancia_hogar_escuela_km NUMERIC(5,2) NOT NULL,
    repeticiones_previas INTEGER NOT NULL,
    apoyo_escolar INTEGER NOT NULL, -- 1: Sí, 0: No
    apoyo_familiar INTEGER NOT NULL, -- 1: Sí, 0: No

    -- E. Situación económica
    beneficiario_juntos INTEGER NOT NULL, -- 1: Sí, 0: No (Programa Nacional de Apoyo Directo a los Más Pobres)
    horas_trabajo_semanal NUMERIC(4,1) NOT NULL,

    -- F. Asistencia escolar
    dias_lectivos_previstos INTEGER NOT NULL,
    faltas_trimestre_1 INTEGER NOT NULL,
    faltas_trimestre_2 INTEGER NOT NULL,

    -- G. Rendimiento académico (Escala vigesimal oficial Perú 0-20, aprobatorio >= 11)
    nota_trimestre_1_0_20 NUMERIC(4,2) NOT NULL,
    nota_trimestre_2_0_20 NUMERIC(4,2) NOT NULL,

    -- H. Variables calculadas
    faltas_totales_calculadas INTEGER NOT NULL,
    asistencia_pct_calculada NUMERIC(5,2) NOT NULL,
    promedio_notas_calculado NUMERIC(4,2) NOT NULL,

    -- I. Variables objetivo calculadas por el Modelo Predictivo (Persona 2)
    -- Son NULLables para permitir cargar los datos brutos antes de ejecutar el modelo
    prob_abandono_pct NUMERIC(5,2),
    prediccion_nota_t3 NUMERIC(4,2),
    prediccion_faltas_t3 INTEGER,
    prob_perdida_beca_pct NUMERIC(5,2),
    prob_repeticion_pct NUMERIC(5,2),
    necesidad_intervencion VARCHAR(20), -- 'Alta', 'Media', 'Baja'
    indice_desanimo NUMERIC(5,2),
    factor_principal_riesgo VARCHAR(160),
    recomendacion_pedagogica TEXT,
    fecha_prediccion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    docente_tutor VARCHAR(60)
);

-- Usuarios institucionales de la plataforma para autenticación JWT
CREATE TABLE IF NOT EXISTS usuario_plataforma (
    username VARCHAR(60) PRIMARY KEY,
    password_hash VARCHAR(120) NOT NULL,
    nombre_completo VARCHAR(120) NOT NULL,
    rol VARCHAR(32) NOT NULL, -- 'docente', 'director', 'delegado'
    escuela_id VARCHAR(32),
    grado_secundaria INTEGER,
    ugel VARCHAR(80),
    titulo_cargo VARCHAR(140) NOT NULL
);

-- Registro de trazabilidad de supervisión humana (Human-in-the-loop)
CREATE TABLE IF NOT EXISTS registro_accion_humana (
    accion_id INTEGER PRIMARY KEY AUTOINCREMENT,
    alumno_id VARCHAR(32) NOT NULL,
    rol_usuario VARCHAR(32) NOT NULL,
    usuario_nombre VARCHAR(120) NOT NULL,
    ambito_id VARCHAR(80) NOT NULL,
    decision_tomada VARCHAR(200) NOT NULL,
    comentario_pedagogico TEXT,
    fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
