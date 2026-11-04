-- =============================================================================
-- DONPROFESOR (#Hack4Edu 2026, Reto 13) · Vistas SQL por Rol y Control de Ámbito
-- =============================================================================

DROP VIEW IF EXISTS vista_docente;
DROP VIEW IF EXISTS vista_director;
DROP VIEW IF EXISTS vista_delegado;
DROP VIEW IF EXISTS vista_avisos_predictivos;

-- 1. VISTA DOCENTE: Datos de seguimiento del aula sin rankings ni estigmas
CREATE VIEW vista_docente AS
SELECT
    alumno_id,
    escuela_id,
    grado_secundaria,
    sexo,
    edad,
    distancia_hogar_escuela_km,
    tiempo_desplazamiento,
    beneficiario_juntos,
    horas_trabajo_semanal,
    internet_hogar,
    tiempo_estudio_semanal,
    faltas_trimestre_1,
    faltas_trimestre_2,
    faltas_totales_calculadas,
    asistencia_pct_calculada,
    nota_trimestre_1_0_20,
    nota_trimestre_2_0_20,
    promedio_notas_calculado,
    prediccion_nota_t3,
    prediccion_faltas_t3,
    prob_perdida_beca_pct,
    prob_repeticion_pct,
    prob_abandono_pct,
    necesidad_intervencion,
    indice_desanimo,
    factor_principal_riesgo,
    recomendacion_pedagogica
FROM alumnos_hack4edu;

-- 2. VISTA DIRECTOR: Agregados por grado escolar y zona dentro del centro educativo
CREATE VIEW vista_director AS
SELECT
    escuela_id,
    grado_secundaria,
    COUNT(*) AS total_estudiantes,
    ROUND(AVG(asistencia_pct_calculada), 2) AS asistencia_media_pct,
    ROUND(AVG(promedio_notas_calculado), 2) AS promedio_notas,
    ROUND(AVG(internet_hogar) * 100.0, 1) AS conectividad_hogar_pct,
    ROUND(AVG(tiempo_estudio_semanal), 1) AS horas_estudio_media,
    SUM(CASE WHEN beneficiario_juntos = 1 THEN 1 ELSE 0 END) AS total_beneficiarios_juntos,
    SUM(CASE WHEN necesidad_intervencion = 'Alta' THEN 1 ELSE 0 END) AS casos_prioridad_alta,
    SUM(CASE WHEN necesidad_intervencion = 'Media' THEN 1 ELSE 0 END) AS casos_prioridad_media,
    SUM(CASE WHEN necesidad_intervencion = 'Baja' THEN 1 ELSE 0 END) AS casos_prioridad_baja,
    ROUND(AVG(prob_abandono_pct), 2) AS prob_abandono_media_pct,
    ROUND(AVG(indice_desanimo), 2) AS indice_desanimo_medio
FROM alumnos_hack4edu
GROUP BY escuela_id, grado_secundaria;

-- 3. VISTA DELEGADO (UGEL / Territorial): Agregados por escuela, distrito y ámbito rural/urbano
CREATE VIEW vista_delegado AS
SELECT
    ugel,
    distrito,
    escuela_id,
    zona_escuela,
    COUNT(*) AS total_estudiantes,
    ROUND(AVG(asistencia_pct_calculada), 2) AS asistencia_media_pct,
    ROUND(AVG(promedio_notas_calculado), 2) AS promedio_notas,
    ROUND(AVG(internet_hogar) * 100.0, 1) AS conectividad_hogar_pct,
    ROUND(AVG(distancia_hogar_escuela_km), 2) AS distancia_media_km,
    SUM(CASE WHEN beneficiario_juntos = 1 THEN 1 ELSE 0 END) AS total_beneficiarios_juntos,
    SUM(CASE WHEN necesidad_intervencion = 'Alta' THEN 1 ELSE 0 END) AS casos_prioridad_alta,
    ROUND(AVG(prob_abandono_pct), 2) AS prob_abandono_media_pct,
    ROUND(AVG(prob_repeticion_pct), 2) AS prob_repeticion_media_pct
FROM alumnos_hack4edu
GROUP BY ugel, distrito, escuela_id, zona_escuela;

-- 4. VISTA AVISOS PREDICTIVOS: Casos detectados para revisión y acompañamiento
CREATE VIEW vista_avisos_predictivos AS
SELECT
    alumno_id,
    escuela_id,
    grado_secundaria,
    necesidad_intervencion,
    prob_abandono_pct,
    prediccion_nota_t3,
    prediccion_faltas_t3,
    prob_perdida_beca_pct,
    prob_repeticion_pct,
    indice_desanimo,
    factor_principal_riesgo,
    recomendacion_pedagogica,
    fecha_prediccion
FROM alumnos_hack4edu
WHERE necesidad_intervencion IS NOT NULL;
