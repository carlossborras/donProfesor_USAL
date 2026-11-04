-- =============================================================================
-- DONPROFESOR (#Hack4Edu) · Esquema de Base de Datos Relacional (Persona 3)
-- Incluye las 5 dimensiones educativas:
--   1. Asistencia (y factores climáticos/agrícolas: lluvia, cosecha, distancia)
--   2. Aprendizaje (evolución de notas y continuidad de entregas)
--   3. Formación Docente (horas de formación práctica y metodología activa)
--   4. Utilización de Recursos (disponibilidad vs uso real en aula y conectividad)
--   5. Participación (participación en aula y tutoría/vínculo familiar)
-- =============================================================================

CREATE TABLE IF NOT EXISTS escuela (
    escuela_id VARCHAR(32) PRIMARY KEY,
    nombre VARCHAR(160) NOT NULL,
    region VARCHAR(100) NOT NULL,
    zona VARCHAR(40) NOT NULL, -- 'Rural', 'Periurbana', 'Urbana'
    conectividad_pct NUMERIC(5,2) NOT NULL,
    dispositivos_disponibles_pct NUMERIC(5,2) NOT NULL,
    tasa_uso_recursos_pct NUMERIC(5,2) NOT NULL,
    horas_formacion_docente_media NUMERIC(5,2) NOT NULL,
    participacion_familiar_media_pct NUMERIC(5,2) NOT NULL,
    asistencia_media_pct NUMERIC(5,2) NOT NULL,
    aprendizaje_medio_pts NUMERIC(5,2) NOT NULL,
    total_alumnos INTEGER NOT NULL,
    latitud NUMERIC(9,6) NOT NULL,
    longitud NUMERIC(9,6) NOT NULL
);

CREATE TABLE IF NOT EXISTS grupo_aula (
    grupo_id VARCHAR(32) PRIMARY KEY,
    escuela_id VARCHAR(32) NOT NULL REFERENCES escuela(escuela_id),
    nombre_grupo VARCHAR(80) NOT NULL,
    grado VARCHAR(60) NOT NULL,
    materia_foco VARCHAR(120) NOT NULL,
    docente_tutor VARCHAR(120) NOT NULL,
    num_estudiantes INTEGER NOT NULL, -- Garantiza k-anonimato (k >= 15)
    asistencia_media_pct NUMERIC(5,2) NOT NULL,
    participacion_aula_pct NUMERIC(5,2) NOT NULL,
    uso_recursos_aula_pct NUMERIC(5,2) NOT NULL,
    horas_formacion_docente NUMERIC(5,2) NOT NULL,
    vinculo_familiar_pct NUMERIC(5,2) NOT NULL,
    nota_media_grupo NUMERIC(5,2) NOT NULL
);

CREATE TABLE IF NOT EXISTS calendario_entorno (
    id SERIAL PRIMARY KEY,
    escuela_id VARCHAR(32) NOT NULL REFERENCES escuela(escuela_id),
    semana_num INTEGER NOT NULL,
    etiqueta_semana VARCHAR(40) NOT NULL,
    mm_lluvia NUMERIC(6,2) NOT NULL,
    es_semana_cosecha INTEGER NOT NULL, -- 1 = Sí, 0 = No
    asistencia_semanal_pct NUMERIC(5,2) NOT NULL,
    uso_recursos_semanal_pct NUMERIC(5,2) NOT NULL,
    participacion_semanal_pct NUMERIC(5,2) NOT NULL
);

CREATE TABLE IF NOT EXISTS alumno_contexto (
    codigo_seguimiento VARCHAR(32) PRIMARY KEY,
    escuela_id VARCHAR(32) NOT NULL REFERENCES escuela(escuela_id),
    grupo_id VARCHAR(32) NOT NULL REFERENCES grupo_aula(grupo_id),
    distancia_km NUMERIC(5,2) NOT NULL,
    tiene_beca INTEGER NOT NULL,
    apoyo_cosecha_familiar INTEGER NOT NULL,
    segundo_empleo_familiar INTEGER NOT NULL,
    acceso_internet_hogar INTEGER NOT NULL,
    faltas_dias_lluvia INTEGER NOT NULL,
    faltas_semanas_cosecha INTEGER NOT NULL,
    faltas_totales INTEGER NOT NULL,
    participacion_actividades_pct NUMERIC(5,2) NOT NULL,
    continuidad_entregas_pct NUMERIC(5,2) NOT NULL,
    nota_media NUMERIC(5,2) NOT NULL,
    tendencia_notas NUMERIC(5,2) NOT NULL
);

-- Tabla donde el Modelo Predictivo (Persona 2) escribe los avisos y explicaciones
CREATE TABLE IF NOT EXISTS prediccion (
    prediccion_id VARCHAR(40) PRIMARY KEY,
    rol_destino VARCHAR(32) NOT NULL, -- 'docente', 'director', 'delegado'
    escuela_id VARCHAR(32) NOT NULL,
    grupo_id VARCHAR(32),
    codigo_seguimiento VARCHAR(32),
    categoria_contexto VARCHAR(80) NOT NULL,
    titulo_humano VARCHAR(220) NOT NULL,
    descripcion_situacion TEXT NOT NULL,
    factor_1_texto VARCHAR(160) NOT NULL,
    factor_1_peso NUMERIC(5,2) NOT NULL,
    factor_2_texto VARCHAR(160) NOT NULL,
    factor_2_peso NUMERIC(5,2) NOT NULL,
    factor_3_texto VARCHAR(160) NOT NULL,
    factor_3_peso NUMERIC(5,2) NOT NULL,
    recomendacion_pedagogica TEXT NOT NULL,
    accion_sugerida_boton VARCHAR(120) NOT NULL,
    estado_revision VARCHAR(40) NOT NULL DEFAULT 'Pendiente de revisión'
);

-- Registro de acciones humanas tomadas por docentes y directores (Human-in-the-loop)
CREATE TABLE IF NOT EXISTS registro_accion_humana (
    accion_id SERIAL PRIMARY KEY,
    prediccion_id VARCHAR(40) NOT NULL,
    rol_usuario VARCHAR(32) NOT NULL,
    usuario_nombre VARCHAR(120) NOT NULL,
    ambito_id VARCHAR(40) NOT NULL,
    decision_tomada VARCHAR(200) NOT NULL,
    comentario_pedagogico TEXT,
    fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Usuarios de la plataforma para login JWT
CREATE TABLE IF NOT EXISTS usuario_plataforma (
    username VARCHAR(60) PRIMARY KEY,
    password_hash VARCHAR(120) NOT NULL,
    nombre_completo VARCHAR(120) NOT NULL,
    rol VARCHAR(32) NOT NULL, -- 'docente', 'director', 'delegado'
    escuela_id VARCHAR(32),
    grupo_id VARCHAR(32),
    titulo_cargo VARCHAR(140) NOT NULL
);
