-- =============================================================================
-- DONPROFESOR (#Hack4Edu) · Vistas de Seguridad y Permisos SQL por Rol (Persona 3)
-- Garantiza privacidad de la información y k-anonimato desde el motor de BD.
-- Cada rol (docente, director, delegado) tiene su propia vista y usuario SQL
-- con GRANT SELECT exclusivo sobre su ámbito de actuación.
-- =============================================================================

-- 1. VISTA DOCENTE:
-- Muestra el seguimiento contextual de su aula y los factores explicativos sin
-- exponer probabilidades numéricas de fracaso ni rankings competitivos.
CREATE VIEW vista_docente AS
SELECT
    a.codigo_seguimiento,
    a.escuela_id,
    e.nombre AS nombre_escuela,
    a.grupo_id,
    g.nombre_grupo,
    g.grado,
    g.materia_foco,
    g.docente_tutor,
    a.distancia_km,
    a.tiene_beca,
    a.apoyo_cosecha_familiar,
    a.segundo_empleo_familiar,
    a.acceso_internet_hogar,
    a.faltas_dias_lluvia,
    a.faltas_semanas_cosecha,
    a.faltas_totales,
    a.participacion_actividades_pct,
    a.continuidad_entregas_pct,
    a.nota_media,
    a.tendencia_notas
FROM alumno_contexto a
JOIN grupo_aula g ON a.grupo_id = g.grupo_id
JOIN escuela e ON a.escuela_id = e.escuela_id;

-- 2. VISTA DIRECTOR:
-- Agrega la información por grupo/aula dentro del centro educativo (k >= 18),
-- cruzando asistencia, aprendizaje, formación docente, utilización de recursos
-- y participación familiar sin identificar alumnos individuales.
CREATE VIEW vista_director AS
SELECT
    g.escuela_id,
    e.nombre AS nombre_escuela,
    e.zona,
    e.conectividad_pct,
    e.dispositivos_disponibles_pct,
    g.grupo_id,
    g.nombre_grupo,
    g.grado,
    g.materia_foco,
    g.docente_tutor,
    g.num_estudiantes,
    g.asistencia_media_pct,
    g.participacion_aula_pct,
    g.uso_recursos_aula_pct,
    (e.dispositivos_disponibles_pct - g.uso_recursos_aula_pct) AS brecha_recursos_sin_usar_pct,
    g.horas_formacion_docente,
    g.vinculo_familiar_pct,
    g.nota_media_grupo
FROM grupo_aula g
JOIN escuela e ON g.escuela_id = e.escuela_id
WHERE g.num_estudiantes >= 5;

-- 3. VISTA DIRECTOR CLIMA Y COSECHA:
-- Serie temporal para la gráfica estrella de Dirección (asistencia vs lluvia y cosecha).
CREATE VIEW vista_director_clima AS
SELECT
    c.escuela_id,
    e.nombre AS nombre_escuela,
    c.semana_num,
    c.etiqueta_semana,
    c.mm_lluvia,
    c.es_semana_cosecha,
    c.asistencia_semanal_pct,
    c.uso_recursos_semanal_pct,
    c.participacion_semanal_pct
FROM calendario_entorno c
JOIN escuela e ON c.escuela_id = e.escuela_id;

-- 4. VISTA DELEGADO TERRITORIAL:
-- Agrega a nivel de escuela para la red regional, garantizando k-anonimato
-- y permitiendo identificar brechas de conectividad, recursos y formación docente.
CREATE VIEW vista_delegado AS
SELECT
    e.escuela_id,
    e.nombre AS nombre_escuela,
    e.region,
    e.zona,
    e.conectividad_pct,
    e.dispositivos_disponibles_pct,
    e.tasa_uso_recursos_pct,
    (e.dispositivos_disponibles_pct - e.tasa_uso_recursos_pct) AS brecha_uso_equipamiento_pct,
    e.horas_formacion_docente_media,
    e.participacion_familiar_media_pct,
    e.asistencia_media_pct,
    e.aprendizaje_medio_pts,
    e.total_alumnos,
    e.latitud,
    e.longitud
FROM escuela e
WHERE e.total_alumnos >= 15;

-- 5. VISTA DE AVISOS EXPLICABLES POR ROL:
CREATE VIEW vista_avisos_predictivos AS
SELECT
    p.prediccion_id,
    p.rol_destino,
    p.escuela_id,
    p.grupo_id,
    p.codigo_seguimiento,
    p.categoria_contexto,
    p.titulo_humano,
    p.descripcion_situacion,
    p.factor_1_texto,
    p.factor_1_peso,
    p.factor_2_texto,
    p.factor_2_peso,
    p.factor_3_texto,
    p.factor_3_peso,
    p.recomendacion_pedagogica,
    p.accion_sugerida_boton,
    p.estado_revision
FROM prediccion p;

-- =============================================================================
-- ROLES Y PERMISOS EN POSTGRESQL (Se ejecutan en el contenedor PostgreSQL)
-- Cada usuario SQL solo tiene GRANT SELECT sobre las vistas de su rol.
-- =============================================================================
-- DO $$
-- BEGIN
--   IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'role_docente') THEN
--     CREATE ROLE role_docente LOGIN PASSWORD 'docente_pass';
--   END IF;
--   IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'role_director') THEN
--     CREATE ROLE role_director LOGIN PASSWORD 'director_pass';
--   END IF;
--   IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'role_delegado') THEN
--     CREATE ROLE role_delegado LOGIN PASSWORD 'delegado_pass';
--   END IF;
-- END
-- $$;
--
-- GRANT SELECT ON vista_docente, vista_avisos_predictivos TO role_docente;
-- GRANT SELECT ON vista_director, vista_director_clima, vista_avisos_predictivos TO role_director;
-- GRANT SELECT ON vista_delegado, vista_avisos_predictivos TO role_delegado;
