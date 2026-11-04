-- =============================================================================
-- DONPROFESOR (#Hack4Edu 2026, Reto 13) · Esquema de Base de Datos Real
-- Variables de entrada (A-H) y salidas del modelo predictivo de Carlos (I)
-- =============================================================================

DROP VIEW IF EXISTS vista_docente;
DROP VIEW IF EXISTS vista_director;
DROP VIEW IF EXISTS vista_delegado;
DROP VIEW IF EXISTS vista_avisos_predictivos;

CREATE TABLE IF NOT EXISTS alumnos_hack4edu (
    -- A. Identificación y ámbito (obligatorios: definen quién puede ver al estudiante)
    alumno_id VARCHAR(32) PRIMARY KEY,
    escuela_id VARCHAR(32) NOT NULL,
    ugel VARCHAR(80),
    distrito VARCHAR(80),
    zona_escuela VARCHAR(20), -- 'Rural' / 'Urbana'

    -- B-E. Variables de entrada del modelo (las que se conocen al matricular).
    -- Pueden faltar: el modelo imputa los huecos y la interfaz avisa de los datos incompletos.
    sexo VARCHAR(10),
    edad INTEGER,
    grado_secundaria INTEGER NOT NULL, -- 1 a 5
    tamano_familia VARCHAR(20), -- '3 o menos' / 'Mas de 3'
    educacion_madre_0_4 INTEGER, -- 0 sin estudios ... 4 universitaria
    educacion_padre_0_4 INTEGER,
    ocupacion_madre VARCHAR(80),
    ocupacion_padre VARCHAR(80),
    internet_hogar INTEGER, -- 1 sí / 0 no
    tiempo_estudio_semanal VARCHAR(20), -- 'Menos de 2 h', '2-5 h', '5-10 h', 'Mas de 10 h'
    tiempo_desplazamiento VARCHAR(20), -- 'Menos de 15 min', '15-30 min', '30-60 min', 'Mas de 60 min'
    distancia_hogar_escuela_km NUMERIC(5,2),
    repeticiones_previas INTEGER,
    apoyo_escolar INTEGER,
    apoyo_familiar INTEGER,
    beneficiario_juntos INTEGER, -- Programa Nacional de Apoyo Directo a los Más Pobres
    horas_trabajo_semanal NUMERIC(4,1),
    dias_lectivos_previstos INTEGER,

    -- F-G. Datos observados durante el curso (vacíos hasta que se conocen)
    faltas_trimestre_1 INTEGER,
    faltas_trimestre_2 INTEGER,
    nota_trimestre_1_0_20 NUMERIC(4,2), -- escala vigesimal, aprobatorio >= 11
    nota_trimestre_2_0_20 NUMERIC(4,2),

    -- H. Calculadas a partir de los datos observados
    faltas_totales_calculadas INTEGER,
    asistencia_pct_calculada NUMERIC(5,2),
    promedio_notas_calculado NUMERIC(4,2),

    -- I. Salidas del modelo predictivo (modelo.joblib). NULL = pendiente de predecir
    prob_abandono_pct NUMERIC(5,2),
    prob_perdida_beca_pct NUMERIC(5,2), -- solo familias en Juntos
    prob_repeticion_pct NUMERIC(5,2),
    necesidad_intervencion VARCHAR(20), -- 'Alta', 'Media', 'Baja'
    prob_necesidad_alta_pct NUMERIC(5,2),
    prediccion_nota_t1 NUMERIC(4,2),
    prediccion_nota_t2 NUMERIC(4,2),
    prediccion_nota_t3 NUMERIC(4,2),
    prediccion_faltas_t1 INTEGER,
    prediccion_faltas_t2 INTEGER,
    prediccion_faltas_t3 INTEGER,
    indice_desanimo NUMERIC(5,2), -- escala 0-10
    factor_principal_riesgo VARCHAR(200),
    factores_json TEXT, -- [{variable, texto, peso_relativo, sugerencia}]
    recomendacion_pedagogica TEXT,
    modelo_version VARCHAR(120),
    fecha_prediccion TIMESTAMP,
    docente_tutor VARCHAR(60),
    fecha_alta TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
