"""
DONPROFESOR (#Hack4Edu 2026, Reto 13) · Cargador de Datos CSV.
Permite importar el CSV generado por Persona 1 (30 variables de entrada) o el CSV con predicciones de Persona 2
directamente a la tabla `alumnos_hack4edu` de la base de datos real.
"""

from __future__ import annotations
import argparse
import csv
import random
from pathlib import Path
from db.adapter import db_adapter
from db.seed_db import init_and_seed_database, get_sqlite_connection


def clear_alumnos_table() -> int:
    """Vacía la tabla de alumnos para dejar la base de datos lista."""
    conn = get_sqlite_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM alumnos_hack4edu;")
    deleted = cur.rowcount
    conn.commit()
    conn.close()
    return deleted


def import_csv_file(csv_path: str) -> int:
    """Importa un archivo CSV mapeando sus columnas a `alumnos_hack4edu`."""
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Archivo no encontrado: {csv_path}")

    rows_to_insert = []
    with open(path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            # Calcular variables derivadas si no vienen en el CSV
            f1 = int(r.get("faltas_trimestre_1") or 0)
            f2 = int(r.get("faltas_trimestre_2") or 0)
            faltas_tot = int(r.get("faltas_totales_calculadas") or (f1 + f2))

            dias = int(r.get("dias_lectivos_previstos") or 180)
            asist_pct = float(
                r.get("asistencia_pct_calculada")
                or max(0.0, round(((dias - faltas_tot) / dias) * 100, 2))
            )

            n1 = float(r.get("nota_trimestre_1_0_20") or 12.0)
            n2 = float(r.get("nota_trimestre_2_0_20") or 12.0)
            prom = float(r.get("promedio_notas_calculado") or round((n1 + n2) / 2.0, 2))

            rows_to_insert.append(
                (
                    r.get("alumno_id"),
                    r.get("escuela_id", "ESC-01"),
                    r.get("ugel", "UGEL-01-NORTE"),
                    r.get("distrito", "Valle Alto"),
                    r.get("zona_escuela", "Rural"),
                    r.get("sexo", "M"),
                    int(r.get("edad") or 14),
                    int(r.get("grado_secundaria") or 2),
                    int(r.get("tamano_familia") or 4),
                    int(r.get("educacion_madre_0_4") or 2),
                    int(r.get("educacion_padre_0_4") or 2),
                    r.get("ocupacion_madre", "Agricultora"),
                    r.get("ocupacion_padre", "Agricultor"),
                    int(r.get("internet_hogar") or 0),
                    float(r.get("tiempo_estudio_semanal") or 5.0),
                    int(r.get("tiempo_desplazamiento") or 30),
                    float(r.get("distancia_hogar_escuela_km") or 3.5),
                    int(r.get("repeticiones_previas") or 0),
                    int(r.get("apoyo_escolar") or 0),
                    int(r.get("apoyo_familiar") or 1),
                    int(r.get("beneficiario_juntos") or 0),
                    float(r.get("horas_trabajo_semanal") or 0.0),
                    dias,
                    f1,
                    f2,
                    n1,
                    n2,
                    faltas_tot,
                    asist_pct,
                    prom,
                    float(r["prob_abandono_pct"]) if r.get("prob_abandono_pct") else None,
                    float(r["prediccion_nota_t3"]) if r.get("prediccion_nota_t3") else None,
                    int(r["prediccion_faltas_t3"]) if r.get("prediccion_faltas_t3") else None,
                    float(r["prob_perdida_beca_pct"]) if r.get("prob_perdida_beca_pct") else None,
                    float(r["prob_repeticion_pct"]) if r.get("prob_repeticion_pct") else None,
                    r.get("necesidad_intervencion"),
                    float(r["indice_desanimo"]) if r.get("indice_desanimo") else None,
                    r.get("factor_principal_riesgo"),
                    r.get("recomendacion_pedagogica"),
                )
            )

    conn = get_sqlite_connection()
    cur = conn.cursor()
    cur.executemany(
        """
        INSERT OR REPLACE INTO alumnos_hack4edu (
            alumno_id, escuela_id, ugel, distrito, zona_escuela,
            sexo, edad, grado_secundaria, tamano_familia,
            educacion_madre_0_4, educacion_padre_0_4, ocupacion_madre, ocupacion_padre,
            internet_hogar, tiempo_estudio_semanal, tiempo_desplazamiento, distancia_hogar_escuela_km,
            repeticiones_previas, apoyo_escolar, apoyo_familiar, beneficiario_juntos, horas_trabajo_semanal,
            dias_lectivos_previstos, faltas_trimestre_1, faltas_trimestre_2,
            nota_trimestre_1_0_20, nota_trimestre_2_0_20,
            faltas_totales_calculadas, asistencia_pct_calculada, promedio_notas_calculado,
            prob_abandono_pct, prediccion_nota_t3, prediccion_faltas_t3,
            prob_perdida_beca_pct, prob_repeticion_pct, necesidad_intervencion,
            indice_desanimo, factor_principal_riesgo, recomendacion_pedagogica
        ) VALUES (
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?,
            ?, ?,
            ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?
        );
        """,
        rows_to_insert,
    )
    conn.commit()
    conn.close()
    return len(rows_to_insert)


def generate_sample_dataset(count: int = 40) -> int:
    """Genera datos realistas calibrados para pruebas antes de que P1 entregue el CSV final."""
    apellidos = ["Quispe", "Flores", "Mamani", "Rojas", "Huamán", "Condori", "Díaz", "García", "Pérez", "Chávez"]
    nombres_m = ["José", "Juan", "Carlos", "Luis", "David", "Ángel", "Diego", "Mateo"]
    nombres_f = ["María", "Rosa", "Ana", "Lucía", "Carmen", "Sofía", "Camila", "Elena"]
    escuelas = ["ESC-01", "ESC-02", "ESC-03"]
    distritos = ["Valle del Río", "Cerro Verde", "La Quebrada", "San Pedro"]

    rows = []
    for i in range(1, count + 1):
        aid = f"ALU-{i:04d}"
        esc = random.choice(escuelas)
        dist = random.choice(distritos)
        zona = "Rural" if dist in ["Valle del Río", "La Quebrada"] else "Urbana"
        sexo = random.choice(["M", "F"])
        grado = random.randint(1, 5)
        edad = grado + 11 + (random.choice([0, 0, 0, 1, 2]))

        dist_km = round(random.uniform(0.5, 7.5), 2)
        minutos = int(dist_km * 12 + random.randint(5, 20))
        juntos = 1 if (zona == "Rural" or random.random() < 0.35) else 0
        internet = 1 if (zona == "Urbana" or random.random() < 0.25) else 0

        trabajo_h = round(random.uniform(4.0, 18.0), 1) if (zona == "Rural" and random.random() < 0.45) else 0.0

        dias = 180
        faltas_1 = random.randint(1, 10)
        # Efecto lluvia y cosecha en T2 si rural o trabaja
        faltas_2 = faltas_1 + (random.randint(4, 12) if (dist_km > 3.0 or trabajo_h > 0) else random.randint(0, 3))
        tot_faltas = faltas_1 + faltas_2
        asist_pct = max(0.0, round(((dias - tot_faltas) / dias) * 100, 2))

        nota_1 = round(random.uniform(9.0, 17.5), 1)
        nota_2 = round(nota_1 - (random.uniform(1.0, 3.5) if trabajo_h > 8 else random.uniform(-1.0, 1.5)), 1)
        nota_2 = max(5.0, min(20.0, nota_2))
        prom = round((nota_1 + nota_2) / 2.0, 2)

        # Salidas calculadas del modelo predictivo (Persona 2)
        if prom < 10.5 or asist_pct < 78.0:
            riesgo = "Alta"
            prob_ab = round(random.uniform(45.0, 85.0), 1)
            p_nota3 = round(max(6.0, nota_2 - 1.0), 1)
            p_falt3 = random.randint(10, 18)
            desanimo = round(random.uniform(65.0, 92.0), 1)
            p_rep = round(random.uniform(60.0, 90.0), 1)
            factor = (
                f"Distancia de traslado ({dist_km} km) y ausencias acumuladas ({tot_faltas} días)"
                if dist_km > 3.0
                else f"Carga laboral semanal ({trabajo_h} h) con descenso de calificaciones en T2"
            )
            recom = "Priorizar tutoría personalizada, flexibilizar calendario de tareas y evaluar apoyo de movilidad escolar."
        elif prom < 12.5 or asist_pct < 85.0:
            riesgo = "Media"
            prob_ab = round(random.uniform(20.0, 44.0), 1)
            p_nota3 = round(nota_2, 1)
            p_falt3 = random.randint(5, 9)
            desanimo = round(random.uniform(35.0, 60.0), 1)
            p_rep = round(random.uniform(25.0, 55.0), 1)
            factor = "Disminución en el tiempo semanal de estudio y conectividad limitada en hogar"
            recom = "Facilitar recursos impresos offline y seguimiento en sesiones de refuerzo grupal."
        else:
            riesgo = "Baja"
            prob_ab = round(random.uniform(3.0, 18.0), 1)
            p_nota3 = round(min(20.0, nota_2 + 0.5), 1)
            p_falt3 = random.randint(1, 4)
            desanimo = round(random.uniform(5.0, 25.0), 1)
            p_rep = round(random.uniform(2.0, 12.0), 1)
            factor = "Trayectoria académica regular y asistencia continua"
            recom = "Mantener el acompañamiento formativo ordinario."

        prob_beca = (
            round(random.uniform(40.0, 80.0), 1)
            if (juntos == 1 and (asist_pct < 85.0 or p_falt3 > 8))
            else (round(random.uniform(5.0, 25.0), 1) if juntos == 1 else None)
        )

        rows.append(
            (
                aid, esc, "UGEL-01-NORTE", dist, zona,
                sexo, edad, grado, random.randint(3, 7),
                random.randint(1, 3), random.randint(1, 4),
                "Comercio / Agrícola", "Agricultor / Transporte",
                internet, round(random.uniform(3.0, 14.0), 1),
                minutos, dist_km,
                1 if random.random() < 0.15 else 0,
                1 if random.random() < 0.3 else 0,
                1 if random.random() < 0.7 else 0,
                juntos, trabajo_h,
                dias, faltas_1, faltas_2,
                nota_1, nota_2,
                tot_faltas, asist_pct, prom,
                prob_ab, p_nota3, p_falt3, prob_beca, p_rep, riesgo,
                desanimo, factor, recom,
            )
        )

    conn = get_sqlite_connection()
    cur = conn.cursor()
    cur.executemany(
        """
        INSERT OR REPLACE INTO alumnos_hack4edu (
            alumno_id, escuela_id, ugel, distrito, zona_escuela,
            sexo, edad, grado_secundaria, tamano_familia,
            educacion_madre_0_4, educacion_padre_0_4, ocupacion_madre, ocupacion_padre,
            internet_hogar, tiempo_estudio_semanal, tiempo_desplazamiento, distancia_hogar_escuela_km,
            repeticiones_previas, apoyo_escolar, apoyo_familiar, beneficiario_juntos, horas_trabajo_semanal,
            dias_lectivos_previstos, faltas_trimestre_1, faltas_trimestre_2,
            nota_trimestre_1_0_20, nota_trimestre_2_0_20,
            faltas_totales_calculadas, asistencia_pct_calculada, promedio_notas_calculado,
            prob_abandono_pct, prediccion_nota_t3, prediccion_faltas_t3,
            prob_perdida_beca_pct, prob_repeticion_pct, necesidad_intervencion,
            indice_desanimo, factor_principal_riesgo, recomendacion_pedagogica
        ) VALUES (
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?,
            ?, ?,
            ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?
        );
        """,
        rows,
    )
    conn.commit()
    conn.close()
    return len(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Importador de datos para DONPROFESOR (#Hack4Edu)")
    parser.add_argument("--csv", type=str, help="Ruta al archivo CSV a importar")
    parser.add_argument("--clear", action="store_true", help="Vacía la tabla de alumnos dejándola en 0 registros")
    parser.add_argument("--sample", type=int, help="Genera N registros realistas para pruebas")

    args = parser.parse_args()

    if args.clear:
        n = clear_alumnos_table()
        print(f"Tabla alumnos_hack4edu vaciada. Registros eliminados: {n}. Queda en 0 registros.")
    elif args.csv:
        n = import_csv_file(args.csv)
        print(f"Importados {n} registros correctamente desde {args.csv}.")
    elif args.sample:
        n = generate_sample_dataset(args.sample)
        print(f"Generados {n} registros de prueba con las 37 variables oficiales.")
    else:
        parser.print_help()
