"""
DONPROFESOR (#Hack4Edu) · Inicializador y Semilla de Base de Datos (Persona 3).
Crea todas las tablas, vistas de seguridad por rol y datos de semilla realistas
desde el minuto uno para que el Frontend (Persona 4), la API y el Servidor MCP
funcionen de inmediato sin esperar a las demás partes.
Soporta tanto PostgreSQL (DATABASE_URL) como SQLite local (db/donprofesor.db).
"""

from __future__ import annotations
import os
import sqlite3
from pathlib import Path
from typing import List, Tuple

DB_DIR = Path(__file__).resolve().parent
SQLITE_PATH = DB_DIR / "donprofesor.db"


def get_sqlite_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(SQLITE_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_and_seed_database(force_reset: bool = False) -> None:
    if force_reset and SQLITE_PATH.exists():
        SQLITE_PATH.unlink()

    conn = get_sqlite_connection()
    cur = conn.cursor()

    # Verificar si ya está poblada
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='escuela';"
    )
    if cur.fetchone() is not None and not force_reset:
        cur.execute("SELECT COUNT(*) FROM escuela;")
        if cur.fetchone()[0] > 0:
            conn.close()
            return

    # Crear tablas compatibles con SQLite y PostgreSQL
    cur.executescript(
        """
        DROP VIEW IF EXISTS vista_docente;
        DROP VIEW IF EXISTS vista_director;
        DROP VIEW IF EXISTS vista_director_clima;
        DROP VIEW IF EXISTS vista_delegado;
        DROP VIEW IF EXISTS vista_avisos_predictivos;

        DROP TABLE IF EXISTS registro_accion_humana;
        DROP TABLE IF EXISTS prediccion;
        DROP TABLE IF EXISTS alumno_contexto;
        DROP TABLE IF EXISTS calendario_entorno;
        DROP TABLE IF EXISTS grupo_aula;
        DROP TABLE IF EXISTS escuela;
        DROP TABLE IF EXISTS usuario_plataforma;

        CREATE TABLE escuela (
            escuela_id TEXT PRIMARY KEY,
            nombre TEXT NOT NULL,
            region TEXT NOT NULL,
            zona TEXT NOT NULL,
            conectividad_pct REAL NOT NULL,
            dispositivos_disponibles_pct REAL NOT NULL,
            tasa_uso_recursos_pct REAL NOT NULL,
            horas_formacion_docente_media REAL NOT NULL,
            participacion_familiar_media_pct REAL NOT NULL,
            asistencia_media_pct REAL NOT NULL,
            aprendizaje_medio_pts REAL NOT NULL,
            total_alumnos INTEGER NOT NULL,
            latitud REAL NOT NULL,
            longitud REAL NOT NULL
        );

        CREATE TABLE grupo_aula (
            grupo_id TEXT PRIMARY KEY,
            escuela_id TEXT NOT NULL,
            nombre_grupo TEXT NOT NULL,
            grado TEXT NOT NULL,
            materia_foco TEXT NOT NULL,
            docente_tutor TEXT NOT NULL,
            num_estudiantes INTEGER NOT NULL,
            asistencia_media_pct REAL NOT NULL,
            participacion_aula_pct REAL NOT NULL,
            uso_recursos_aula_pct REAL NOT NULL,
            horas_formacion_docente REAL NOT NULL,
            vinculo_familiar_pct REAL NOT NULL,
            nota_media_grupo REAL NOT NULL
        );

        CREATE TABLE calendario_entorno (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            escuela_id TEXT NOT NULL,
            semana_num INTEGER NOT NULL,
            etiqueta_semana TEXT NOT NULL,
            mm_lluvia REAL NOT NULL,
            es_semana_cosecha INTEGER NOT NULL,
            asistencia_semanal_pct REAL NOT NULL,
            uso_recursos_semanal_pct REAL NOT NULL,
            participacion_semanal_pct REAL NOT NULL
        );

        CREATE TABLE alumno_contexto (
            codigo_seguimiento TEXT PRIMARY KEY,
            escuela_id TEXT NOT NULL,
            grupo_id TEXT NOT NULL,
            distancia_km REAL NOT NULL,
            tiene_beca INTEGER NOT NULL,
            apoyo_cosecha_familiar INTEGER NOT NULL,
            segundo_empleo_familiar INTEGER NOT NULL,
            acceso_internet_hogar INTEGER NOT NULL,
            faltas_dias_lluvia INTEGER NOT NULL,
            faltas_semanas_cosecha INTEGER NOT NULL,
            faltas_totales INTEGER NOT NULL,
            participacion_actividades_pct REAL NOT NULL,
            continuidad_entregas_pct REAL NOT NULL,
            nota_media REAL NOT NULL,
            tendencia_notas REAL NOT NULL
        );

        CREATE TABLE prediccion (
            prediccion_id TEXT PRIMARY KEY,
            rol_destino TEXT NOT NULL,
            escuela_id TEXT NOT NULL,
            grupo_id TEXT,
            codigo_seguimiento TEXT,
            categoria_contexto TEXT NOT NULL,
            titulo_humano TEXT NOT NULL,
            descripcion_situacion TEXT NOT NULL,
            factor_1_texto TEXT NOT NULL,
            factor_1_peso REAL NOT NULL,
            factor_2_texto TEXT NOT NULL,
            factor_2_peso REAL NOT NULL,
            factor_3_texto TEXT NOT NULL,
            factor_3_peso REAL NOT NULL,
            recomendacion_pedagogica TEXT NOT NULL,
            accion_sugerida_boton TEXT NOT NULL,
            estado_revision TEXT NOT NULL DEFAULT 'Pendiente de revisión'
        );

        CREATE TABLE registro_accion_humana (
            accion_id INTEGER PRIMARY KEY AUTOINCREMENT,
            prediccion_id TEXT NOT NULL,
            rol_usuario TEXT NOT NULL,
            usuario_nombre TEXT NOT NULL,
            ambito_id TEXT NOT NULL,
            decision_tomada TEXT NOT NULL,
            comentario_pedagogico TEXT,
            fecha_registro TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE usuario_plataforma (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            nombre_completo TEXT NOT NULL,
            rol TEXT NOT NULL,
            escuela_id TEXT,
            grupo_id TEXT,
            titulo_cargo TEXT NOT NULL
        );
        """
    )

    # Crear vistas de seguridad por rol
    views_sql_path = DB_DIR / "views_and_grants.sql"
    cur.executescript(views_sql_path.read_text(encoding="utf-8"))

    # 1. Insertar usuarios de demostración para los 3 roles
    usuarios = [
        (
            "docente",
            "donprofesor2026",
            "Prof. Carmen Morales",
            "docente",
            "ESC-01",
            "ESC-01-2B",
            "Tutora de 2º Secundaria · Sección B (I.E. Valle Verde)",
        ),
        (
            "director",
            "donprofesor2026",
            "D. Manuel Estrada",
            "director",
            "ESC-01",
            "ALL",
            "Director de Centro · I.E. Valle Verde (6 Grupos)",
        ),
        (
            "delegado",
            "donprofesor2026",
            "Dña. Rosa Menéndez",
            "delegado",
            "ALL",
            "ALL",
            "Coordinadora Territorial · Red Regional Sur (12 Centros Cabecera)",
        ),
    ]
    cur.executemany(
        "INSERT INTO usuario_plataforma VALUES (?, ?, ?, ?, ?, ?, ?);", usuarios
    )

    # 2. Insertar 12 centros educativos representativos de la región (Urbanos, Periurbanos y Rurales)
    escuelas = [
        ("ESC-01", "I.E. Valle Verde", "Comarca Andina Sur", "Rural", 38.0, 84.0, 52.5, 16.5, 79.0, 84.2, 68.5, 164, -13.5319, -71.9675),
        ("ESC-02", "Colegio Técnico San Martín", "Valle Central", "Periurbana", 65.0, 80.0, 71.0, 24.0, 74.5, 88.0, 73.2, 240, -13.5180, -71.9450),
        ("ESC-03", "Centro Horizonte Digital", "Área Metropolitana", "Urbana", 94.0, 92.0, 86.0, 32.0, 84.0, 93.1, 80.4, 310, -13.5226, -71.9780),
        ("ESC-04", "Escuela Comunitaria Río Alto", "Cuenca Amazónica", "Rural", 25.0, 74.0, 31.0, 9.5, 68.0, 76.8, 59.0, 128, -13.4890, -71.9120),
        ("ESC-05", "Instituto Bicentenario Norte", "Sierra Central", "Periurbana", 58.0, 82.0, 49.0, 14.0, 71.0, 83.5, 66.0, 195, -13.5510, -72.0110),
        ("ESC-06", "Liceo Gabriela Mistral", "Sector Sur Urbano", "Urbana", 82.0, 88.0, 79.0, 28.5, 77.0, 89.4, 75.8, 280, -13.5420, -71.9540),
        ("ESC-07", "Escuela Rural Las Cumbres", "Altiplano Sur", "Rural", 22.0, 78.0, 29.5, 8.0, 64.0, 75.2, 57.4, 112, -13.5890, -72.0450),
        ("ESC-08", "Colegio Integrado Santa Rosa", "Valle Central", "Periurbana", 62.0, 76.0, 64.0, 21.0, 73.0, 86.4, 70.1, 215, -13.5050, -71.9920),
        ("ESC-09", "I.E. Agrícola Pampa Blanca", "Comarca Andina Sur", "Rural", 31.0, 85.0, 36.0, 11.0, 70.5, 78.9, 61.8, 145, -13.5680, -71.9210),
        ("ESC-10", "Centro Educativo Los Pinos", "Sector Norte", "Periurbana", 70.0, 84.0, 44.0, 12.5, 69.0, 84.8, 67.2, 205, -13.4980, -71.9610),
        ("ESC-11", "Escuela Ribereña San Juan", "Cuenca Amazónica", "Rural", 19.0, 70.0, 28.0, 7.5, 66.0, 74.5, 56.0, 98, -13.4750, -71.8950),
        ("ESC-12", "Instituto Politécnico Central", "Área Metropolitana", "Urbana", 91.0, 90.0, 83.5, 30.0, 82.0, 91.8, 78.9, 340, -13.5290, -71.9620),
    ]
    cur.executemany(
        "INSERT INTO escuela VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);",
        escuelas,
    )

    # 3. Insertar los 6 grupos/aulas de I.E. Valle Verde (ESC-01) y aulas de referencia
    grupos = [
        ("ESC-01-1A", "ESC-01", "1º Secundaria A", "1º Secundaria", "Matemática Aplicada y Taller", "Prof. Jorge Quispe", 27, 83.0, 68.0, 34.0, 9.0, 74.0, 64.5),
        ("ESC-01-1B", "ESC-01", "1º Secundaria B", "1º Secundaria", "Comprensión Lectora y Proyectos", "Prof. Elena Vargas", 26, 84.5, 71.0, 38.0, 10.5, 76.0, 66.2),
        ("ESC-01-2A", "ESC-01", "2º Secundaria A", "2º Secundaria", "Ciencias Naturales y Entorno", "Prof. Marcos Flores", 28, 81.2, 72.0, 48.0, 15.0, 78.0, 67.0),
        ("ESC-01-2B", "ESC-01", "2º Secundaria B", "2º Secundaria", "Ciencias, Laboratorio y Ciudadanía", "Prof. Carmen Morales", 28, 87.5, 76.0, 68.4, 22.0, 81.0, 71.4),
        ("ESC-01-3A", "ESC-01", "3º Secundaria A", "3º Secundaria", "Tecnología y Pensamiento Crítico", "Prof. Lucía Mendoza", 29, 86.8, 82.0, 78.0, 26.0, 84.0, 74.2),
        ("ESC-01-4A", "ESC-01", "4º Secundaria A", "4º Secundaria", "Proyectos STEAM y Comunidad", "Prof. Ricardo Soto", 26, 82.4, 75.0, 49.0, 16.5, 81.0, 68.0),
        ("ESC-02-2A", "ESC-02", "2º Secundaria A", "2º Secundaria", "Innovación Digital", "Prof. Ana Salazar", 30, 88.5, 79.0, 72.0, 24.0, 75.0, 73.5),
        ("ESC-04-1A", "ESC-04", "1º Secundaria A", "1º Secundaria", "Lengua y Territorio", "Prof. Raúl Ibarra", 24, 76.0, 67.0, 30.0, 9.0, 68.0, 58.5),
    ]
    cur.executemany(
        "INSERT INTO grupo_aula VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);",
        grupos,
    )

    # 4. Insertar serie semanal de 12 semanas para la Gráfica Estrella (asistencia vs lluvia y cosecha)
    # Semanas 5, 6, 7 y 8 coinciden con temporada de cosecha y pico de lluvias
    calendario = [
        ("ESC-01", 1, "Sem 1 (Mar)", 12.0, 0, 91.5, 48.0, 75.0),
        ("ESC-01", 2, "Sem 2 (Mar)", 18.0, 0, 90.2, 50.0, 76.0),
        ("ESC-01", 3, "Sem 3 (Abr)", 24.0, 0, 88.4, 52.0, 75.5),
        ("ESC-01", 4, "Sem 4 (Abr)", 35.0, 0, 86.0, 54.0, 74.0),
        ("ESC-01", 5, "Sem 5 (May)", 68.0, 1, 76.5, 55.0, 70.0),
        ("ESC-01", 6, "Sem 6 (May)", 82.0, 1, 72.4, 58.0, 68.5),
        ("ESC-01", 7, "Sem 7 (Jun)", 74.0, 1, 74.8, 63.0, 72.0),
        ("ESC-01", 8, "Sem 8 (Jun)", 52.0, 1, 79.5, 68.4, 76.0),
        ("ESC-01", 9, "Sem 9 (Jul)", 22.0, 0, 87.2, 71.0, 79.5),
        ("ESC-01", 10, "Sem 10 (Ago)", 14.0, 0, 89.8, 74.0, 81.0),
        ("ESC-01", 11, "Sem 11 (Sep)", 10.0, 0, 91.2, 76.5, 82.5),
        ("ESC-01", 12, "Sem 12 (Oct)", 16.0, 0, 91.8, 78.0, 83.0),
    ]
    cur.executemany(
        """
        INSERT INTO calendario_entorno
        (escuela_id, semana_num, etiqueta_semana, mm_lluvia, es_semana_cosecha,
         asistencia_semanal_pct, uso_recursos_semanal_pct, participacion_semanal_pct)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """,
        calendario,
    )

    # 5. Insertar los 28 estudiantes de seguimiento contextual del Aula 2º B (ESC-01-2B)
    # Sin nombres personales identificables (código de tutoría) y sin etiquetas punitivas.
    alumnos_2b = [
        ("ALU-2B-01", "ESC-01", "ESC-01-2B", 4.6, 1, 1, 0, 0, 5, 4, 9, 78.0, 82.0, 68.5, -1.2),
        ("ALU-2B-02", "ESC-01", "ESC-01-2B", 4.2, 0, 1, 0, 0, 6, 5, 11, 74.0, 75.0, 62.0, -3.4),
        ("ALU-2B-03", "ESC-01", "ESC-01-2B", 3.8, 1, 0, 1, 0, 4, 2, 7, 81.0, 85.0, 71.0, 0.5),
        ("ALU-2B-04", "ESC-01", "ESC-01-2B", 5.1, 0, 1, 0, 0, 7, 4, 11, 72.0, 70.0, 60.5, -4.1),
        ("ALU-2B-05", "ESC-01", "ESC-01-2B", 1.2, 1, 0, 0, 1, 0, 0, 1, 88.0, 94.0, 81.0, 2.4),
        ("ALU-2B-06", "ESC-01", "ESC-01-2B", 0.8, 0, 0, 0, 1, 1, 0, 1, 85.0, 92.0, 79.5, 1.8),
        ("ALU-2B-07", "ESC-01", "ESC-01-2B", 2.4, 1, 1, 1, 0, 2, 3, 5, 80.0, 86.0, 72.0, 0.8),
        ("ALU-2B-08", "ESC-01", "ESC-01-2B", 3.5, 0, 0, 1, 0, 4, 1, 6, 69.0, 73.0, 63.5, -2.8),
        ("ALU-2B-09", "ESC-01", "ESC-01-2B", 1.5, 1, 0, 0, 1, 1, 0, 2, 84.0, 90.0, 76.0, 1.5),
        ("ALU-2B-10", "ESC-01", "ESC-01-2B", 4.0, 1, 1, 0, 0, 4, 3, 7, 79.0, 84.0, 70.0, -0.4),
        ("ALU-2B-11", "ESC-01", "ESC-01-2B", 0.9, 0, 0, 0, 1, 0, 0, 1, 90.0, 95.0, 84.0, 3.1),
        ("ALU-2B-12", "ESC-01", "ESC-01-2B", 2.1, 1, 0, 0, 0, 1, 1, 2, 82.0, 88.0, 74.5, 1.2),
    ]
    # Completar hasta los 28 estudiantes del grupo con perfiles equilibrados
    for idx in range(13, 29):
        cod = f"ALU-2B-{idx:02d}"
        dist = round(1.1 + (idx % 4) * 0.7, 1)
        beca = 1 if idx % 2 == 0 else 0
        cosecha = 1 if idx % 5 == 0 else 0
        empleo = 1 if idx % 7 == 0 else 0
        net = 1 if dist < 2.2 else 0
        f_lluvia = 2 if dist > 3.0 else 0
        f_cos = 2 if cosecha == 1 else 0
        f_tot = f_lluvia + f_cos + (1 if idx % 3 == 0 else 0)
        part = round(74.0 + (idx % 6) * 2.5, 1)
        ent = round(80.0 + (idx % 5) * 3.0 - f_tot * 1.5, 1)
        nota = round(69.0 + (idx % 7) * 2.2 - f_tot * 0.8, 1)
        tend = round(1.4 - f_tot * 0.45, 1)
        alumnos_2b.append(
            (cod, "ESC-01", "ESC-01-2B", dist, beca, cosecha, empleo, net, f_lluvia, f_cos, f_tot, part, ent, nota, tend)
        )

    cur.executemany(
        "INSERT INTO alumno_contexto VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);",
        alumnos_2b,
    )

    # 6. Insertar Avisos del Modelo Predictivo en lenguaje humano para los 3 roles
    avisos = [
        # --- AVISOS PARA DOCENTE (ESC-01-2B) ---
        (
            "PRED-DOC-01",
            "docente",
            "ESC-01",
            "ESC-01-2B",
            "Subgrupo Traslado (>3 km)",
            "Factor de traslado · 4 estudiantes",
            "Dificultad de traslado en días de lluvia para alumnado con residencia alejada",
            "El modelo observa que las ausencias de los códigos ALU-2B-01, ALU-2B-02, ALU-2B-04 y ALU-2B-10 se concentran en jornadas con más de 35 mm de lluvia. Cuando asisten al centro, su participación en clase (76%) y entrega de tareas se mantienen constantes.",
            "Distancia al centro superior a 3,8 km en días de lluvia",
            42.0,
            "Coincidencia con semanas de labor agrícola familiar",
            34.0,
            "Sin conexión a internet en el hogar para descarga previa",
            24.0,
            "Facilitar guías modulares impresas o descargadas en el aula los viernes previos a semanas lluviosas y flexibilizar tres días la entrega.",
            "Registrar apoyo pedagógico",
            "Pendiente de revisión",
        ),
        (
            "PRED-DOC-02",
            "docente",
            "ESC-01",
            "ESC-01-2B",
            "ALU-2B-03 y ALU-2B-08",
            "Compatibilidad horaria · 2 estudiantes",
            "Descenso en ritmo de entregas por apoyo laboral vespertino familiar",
            "Se identifica una bajada reciente en la continuidad de entregas (-2,8 pts) vinculada a responsabilidades de segundo empleo familiar en horario de tarde. En el caso de ALU-2B-03, contar con beca escolar amortigua el impacto y sostiene su asistencia.",
            "Responsabilidad laboral vespertina fuera del horario escolar",
            46.0,
            "Efecto protector de beca escolar y comedor activo",
            31.0,
            "Participación positiva en dinámicas cooperativas de aula",
            23.0,
            "Priorizar que los ejercicios prácticos se cierren dentro de la sesión lectiva mediante trabajo por estaciones en parejas.",
            "Acordar adaptación en tutoría",
            "Pendiente de revisión",
        ),
        (
            "PRED-DOC-03",
            "docente",
            "ESC-01",
            "ESC-01-2B",
            "Grupo completo 2º B",
            "Oportunidad metodológica",
            "Alta respuesta del grupo al combinar el aula digital con proyectos prácticos",
            "Los registros del trimestre muestran que en las semanas en que el grupo utiliza las cápsulas offline de Ciencias al menos 2 horas, la participación grupal sube del 68% al 84% y mejora la comprensión de la unidad.",
            "Disponibilidad de franja libre en el aula digital los jueves",
            45.0,
            "Formación práctica docente completada en metodologías activas (22h)",
            35.0,
            "Material interactivo precargado en el servidor local del centro",
            20.0,
            "Reservar la tercera hora del jueves para cerrar el bloque de Ciencias con la actividad colaborativa local.",
            "Reservar franja y registrar sesión",
            "En seguimiento",
        ),

        # --- AVISOS PARA DIRECCIÓN DE CENTRO (ESC-01) ---
        (
            "PRED-DIR-01",
            "director",
            "ESC-01",
            "ESC-01-1A",
            "Grupos de 1º de Secundaria",
            "Brecha de utilización de recursos",
            "Equipamiento digital disponible en el centro con bajo uso efectivo en 1º de Secundaria",
            "El centro cuenta con un 84% de dispositivos operativos, pero en 1ºA y 1ºB su utilización en aula es del 34% y 38%. El análisis muestra que la diferencia respecto a 3ºA (78% de uso) se explica por las horas de acompañamiento práctico docente.",
            "Horas de formación práctica docente inferiores a 11h en 1º grado",
            49.0,
            "Horarios de laboratorio concentrados en un solo bloque semanal",
            31.0,
            "Necesidad de precarga de contenidos offline los lunes",
            20.0,
            "Organizar dos sesiones quincenales de co-docencia entre el profesorado de 3ºA y los tutores de 1º de Secundaria.",
            "Programar acompañamiento entre pares",
            "Pendiente de revisión",
        ),
        (
            "PRED-DIR-02",
            "director",
            "ESC-01",
            "ALL",
            "Todo el centro · Semanas 5 a 8",
            "Previsión estacional de centro",
            "Previsión de descenso de asistencia del 11% en semanas de lluvia y calendario agrícola",
            "El cruce histórico del centro confirma que cuando la precipitación semanal supera los 50 mm durante los meses de cosecha local, la asistencia media baja del 89% al 73%, afectando sobre todo a quienes viven a más de 3 km.",
            "Interacción entre lluvia intensa (>50 mm) y distancia >3 km",
            44.0,
            "Calendario comarcal de cosecha en semanas 5 a 8",
            36.0,
            "Efecto protector comprobado en grupos con vínculo familiar >80%",
            20.0,
            "Activar el calendario flexible de entregas en mayo-junio y coordinar con las familias el préstamo de cuadernillos modulares.",
            "Activar protocolo estacional de centro",
            "Pendiente de revisión",
        ),
        (
            "PRED-DIR-03",
            "director",
            "ESC-01",
            "ESC-01-3A",
            "3º Secundaria A",
            "Referente positivo del centro",
            "El vínculo familiar y el aprendizaje por proyectos sostienen un 86,8% de asistencia en 3º A",
            "Pese a compartir el mismo entorno rural y climático, el grupo 3º A reduce a la mitad las ausencias estacionales gracias a las reuniones mensuales con familias y al uso regular de talleres prácticos.",
            "Participación familiar en tutorías del 84%",
            43.0,
            "Adopción de proyectos colaborativos con recursos del centro (78%)",
            37.0,
            "Cobertura de becas de transporte y comedor en el grupo",
            20.0,
            "Compartir la dinámica de comunicación familiar de 3º A en la próxima reunión de coordinación de tutores.",
            "Documentar buena práctica en claustro",
            "Acuerdo registrado",
        ),

        # --- AVISOS PARA COORDINACIÓN TERRITORIAL / DELEGADO (ALL) ---
        (
            "PRED-DEL-01",
            "delegado",
            "ALL",
            "ALL",
            "Escuelas Rurales (Cuenca y Altiplano)",
            "Prioridad territorial · Becas y Transporte",
            "4 centros rurales concentran la mayor caída de asistencia en temporada de lluvias y cosecha",
            "Las escuelas Río Alto, Las Cumbres, Ribereña San Juan y Pampa Blanca presentan asistencias de entre 74% y 78%. El factor determinante es la distancia superior a 3 km sin ruta cubierta durante las lluvias.",
            "Trayectos escolares superiores a 3 km en época de lluvias",
            45.0,
            "Calendario agrícola comarcal sin flexibilidad curricular",
            33.0,
            "Cobertura insuficiente de becas de transporte y comedor rural",
            22.0,
            "Priorizar la partida de becas de transporte y comedor en los 4 centros rurales antes del inicio del próximo trimestre.",
            "Simular asignación de becas",
            "Pendiente de revisión",
        ),
        (
            "PRED-DEL-02",
            "delegado",
            "ALL",
            "ALL",
            "Red Periurbana y Rural (5 escuelas)",
            "Eficiencia en asignación de recursos",
            "Infrautilización de equipamiento disponible (brecha del 40%) por falta de mentoría docente in-situ",
            "Cinco centros de la red disponen de más del 75% de equipamiento digital, pero su tasa de uso en clase es inferior al 45%. Enviar formación docente práctica multiplica por 3,2 el retorno en aprendizaje frente a comprar nuevo hardware.",
            "Docentes con menos de 12 horas de formación práctica aplicada",
            51.0,
            "Baja conectividad que requiere servidor local de contenidos",
            29.0,
            "Falta de tiempo liberado para planificación tecnopedagógica",
            20.0,
            "Desplegar brigadas de mentoría docente práctica y servidores locales offline en lugar de adquirir más dispositivos.",
            "Asignar brigada de formación docente",
            "Pendiente de revisión",
        ),
        (
            "PRED-DEL-03",
            "delegado",
            "ALL",
            "ALL",
            "Auditoría Ética Regional",
            "Garantía de equidad y privacidad",
            "Auditoría de sesgo del modelo verificada entre zonas rurales, periurbanas y urbanas",
            "La validación cruzada confirma una diferencia de error menor al 1,1% entre zonas geográficas y paridad por sexo, operando exclusivamente sobre vistas agregadas con k-anonimato (k >= 15 en vista territorial).",
            "Calibración equitativa Rural vs. Urbana verificada",
            40.0,
            "Protección de privacidad por diseño en vistas SQL por rol",
            35.0,
            "Ausencia total de decisiones automáticas sobre el alumnado",
            25.0,
            "Mantener la revisión trimestral de equidad junto con los directores de la red escolar.",
            "Consultar ficha técnica de equidad",
            "Verificado",
        ),
    ]
    cur.executemany(
        """
        INSERT INTO prediccion VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        avisos,
    )

    # 7. Insertar un registro inicial de acción humana para mostrar el historial vivo
    cur.execute(
        """
        INSERT INTO registro_accion_humana
        (prediccion_id, rol_usuario, usuario_nombre, ambito_id, decision_tomada, comentario_pedagogico)
        VALUES (?, ?, ?, ?, ?, ?);
        """,
        (
            "PRED-DOC-03",
            "docente",
            "Prof. Carmen Morales",
            "ESC-01-2B",
            "Reservar franja horaria en aula digital",
            "Se reserva los jueves a 3ª hora para trabajo por estaciones en la unidad de Ciencias con material offline.",
        ),
    )

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_and_seed_database(force_reset=True)
    print(f"Base de datos inicializada correctamente en: {SQLITE_PATH}")
