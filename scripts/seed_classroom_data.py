"""
DONPROFESOR (#Hack4Edu 2026, Reto 13) · Población de la clase del docente con 30 alumnos realistas.
Extrae datos del dataset sintético oficial peruano (alumnos_peru_sintetico.csv) y garantiza:
1. 30 alumnos en la clase del usuario 'borjavalher' (USAL-01, 3º de secundaria).
2. 30 alumnos en la clase de demostración 'docente' (ESC-01, 2º de secundaria).
3. Aislamiento estricto por grupo y trazabilidad ética sin clasificaciones punitivas.
"""

from __future__ import annotations
import math
import os
import sys
from pathlib import Path

# Asegurar raíz del proyecto en sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import numpy as np
import pandas as pd
from db.adapter import db_adapter
from db.seed_db import get_sqlite_connection

CSV_CANDIDATES = [
    Path(r"c:\Users\valve\Downloads\alumnos_peru_sintetico (1).csv"),
    Path(r"c:\Users\valve\Downloads\alumnos_peru_sintetico.csv"),
    Path("data/alumnos_peru_sintetico.csv"),
    Path("data/muestra_30_alumnos_peru.csv"),
]


def find_csv() -> Path:
    for p in CSV_CANDIDATES:
        if p.exists():
            return p
    raise FileNotFoundError("No se encontró ningún archivo CSV de alumnos.")


def generate_factors_and_recommendation(row: dict) -> tuple[str, str]:
    dist = float(row.get("distancia_hogar_escuela_km") or 0.0)
    trabajo = float(row.get("horas_trabajo_semanal") or 0.0)
    prom = float(row.get("promedio_notas_calculado") or 12.0)
    f1 = int(row.get("faltas_trimestre_1") or 0)
    f2 = int(row.get("faltas_trimestre_2") or 0)
    juntos = int(row.get("beneficiario_juntos") or 0)
    asist = float(row.get("asistencia_pct_calculada") or 90.0)

    if dist >= 3.5 and (f2 > f1 + 2 or f1 + f2 >= 10):
        factor = f"Distancia al colegio ({dist:g} km) con acumulación de ausencias ({f1 + f2} días) en época de lluvias"
        recom = "Facilitar recursos impresos offline, flexibilizar horario de llegada y evaluar transporte rural."
    elif trabajo > 4.0:
        factor = f"Apoyo laboral semanal ({trabajo:g} h) en actividades agropecuarias o comerciales familiares"
        recom = "Coordinar calendario flexible de tareas y tutoría de refuerzo adaptada a la jornada familiar."
    elif f2 > f1 + 3:
        factor = f"Incremento marcado de inasistencias en el 2.º trimestre ({f1} → {f2} faltas)"
        recom = "Entrevista diagnóstica con la familia para identificar dificultades y reenganchar al estudiante."
    elif prom < 11.0:
        factor = f"Rendimiento en zona de refuerzo prioritario (promedio actual {prom:g}/20)"
        recom = "Tutoría académica individualizada y asignación de compañero monitor en materias clave."
    elif juntos == 1 and asist < 85.0:
        factor = f"Asistencia vulnerable ({asist:g}%) con riesgo de pérdida del subsidio educativo Juntos"
        recom = "Contacto con el promotor del programa Juntos para proteger la permanencia de la familia."
    else:
        factor = "Evolución académica regular y compromiso escolar sostenido"
        recom = "Acompañamiento pedagógico ordinario y estímulo a la participación en proyectos de aula."

    return factor, recom


def to_int_bool(val: any) -> int:
    if pd.isnull(val):
        return 0
    if isinstance(val, (bool, np.bool_)):
        return 1 if val else 0
    s = str(val).strip().lower()
    return 1 if s in ["1", "true", "si", "sí", "t"] else 0


def seed_classroom_students() -> None:
    csv_file = find_csv()
    print(f"Cargando datos desde: {csv_file}")
    df = pd.read_csv(csv_file)

    conn = get_sqlite_connection()
    cur = conn.cursor()

    # -------------------------------------------------------------------------
    # 1. Clase de borjavalher: USAL-01, 3º de Secundaria, docente_tutor = 'borjavalher'
    # -------------------------------------------------------------------------
    print("Preparando 30 alumnos para borjavalher (USAL-01, 3º de secundaria)...")

    # Verificar si ALU-98521 ya existe
    cur.execute("SELECT COUNT(*) FROM alumnos_hack4edu WHERE alumno_id = 'ALU-98521';")
    has_test_student = (cur.fetchone()[0] > 0)

    # Filtrar candidatos de grado 3 del dataset
    g3 = df[df["grado_secundaria"] == 3].copy()
    if len(g3) < 30:
        g3 = df.copy()

    # Muestrear casos variados
    needed = 29 if has_test_student else 30
    n_baja = math.ceil(needed * 0.55)
    n_media = math.ceil(needed * 0.28)
    n_alta = needed - (n_baja + n_media)

    sub_baja = g3[g3["necesidad_intervencion"] == "Baja"].sample(min(n_baja, len(g3[g3["necesidad_intervencion"] == "Baja"])), random_state=42)
    sub_media = g3[g3["necesidad_intervencion"] == "Media"].sample(min(n_media, len(g3[g3["necesidad_intervencion"] == "Media"])), random_state=42)
    sub_alta = g3[g3["necesidad_intervencion"] == "Alta"].sample(min(n_alta, len(g3[g3["necesidad_intervencion"] == "Alta"])), random_state=42)

    sample_g3 = pd.concat([sub_baja, sub_media, sub_alta]).sample(frac=1.0, random_state=42).reset_index(drop=True)

    rows_borja = []
    for i, (_, r) in enumerate(sample_g3.iterrows()):
        aid = f"ALU-3{i+1:04d}"
        f1 = int(r.get("faltas_trimestre_1") or 2)
        f2 = int(r.get("faltas_trimestre_2") or 3)
        dias = int(r.get("dias_lectivos_previstos") or 116)
        faltas_tot = f1 + f2
        asist_pct = round(max(0.0, ((dias - faltas_tot) / dias) * 100), 2)

        n1 = round(float(r.get("nota_trimestre_1_0_20") or 12.0), 2)
        n2 = round(float(r.get("nota_trimestre_2_0_20") or 12.0), 2)
        prom = round((n1 + n2) / 2.0, 2)

        juntos = to_int_bool(r.get("beneficiario_juntos"))
        internet = to_int_bool(r.get("internet_hogar"))
        dist_km = round(float(r.get("distancia_hogar_escuela_km") or 2.5), 2)
        trabajo_h = round(float(r.get("horas_trabajo_semanal") or 0.0), 1)

        row_dict = {
            "distancia_hogar_escuela_km": dist_km,
            "horas_trabajo_semanal": trabajo_h,
            "promedio_notas_calculado": prom,
            "faltas_trimestre_1": f1,
            "faltas_trimestre_2": f2,
            "beneficiario_juntos": juntos,
            "asistencia_pct_calculada": asist_pct,
        }
        factor, recom = generate_factors_and_recommendation(row_dict)

        # Predicciones coherentes
        interv = str(r.get("necesidad_intervencion") or "Baja")
        if interv == "Alta":
            prob_ab = round(float(r.get("prob_abandono_pct") or np.random.uniform(35.0, 65.0)), 1)
            pred_n3 = round(min(prom, float(r.get("nota_trimestre_3_real") or prom - 1.5)), 1)
            pred_f3 = int(r.get("ausencias_trimestre_3") or 8)
            prob_rep = round(float(np.random.uniform(25.0, 50.0)), 1)
        elif interv == "Media":
            prob_ab = round(float(r.get("prob_abandono_pct") or np.random.uniform(15.0, 34.0)), 1)
            pred_n3 = round(float(r.get("nota_trimestre_3_real") or prom), 1)
            pred_f3 = int(r.get("ausencias_trimestre_3") or 4)
            prob_rep = round(float(np.random.uniform(8.0, 20.0)), 1)
        else:
            prob_ab = round(float(r.get("prob_abandono_pct") or np.random.uniform(2.0, 12.0)), 1)
            pred_n3 = round(max(prom, float(r.get("nota_trimestre_3_real") or prom + 0.5)), 1)
            pred_f3 = int(r.get("ausencias_trimestre_3") or 1)
            prob_rep = round(float(np.random.uniform(0.5, 5.0)), 1)

        prob_beca = round(prob_ab * 0.8, 1) if juntos == 1 else 0.0
        desanimo = round(float(r.get("desanimo_calculado") or np.random.uniform(3.0, 7.5)), 2)

        rows_borja.append((
            aid,
            "USAL-01",
            "UGEL-01-NORTE",
            str(r.get("distrito") or "Valle Alto"),
            str(r.get("zona_escuela") or "Rural"),
            str(r.get("sexo") or "M"),
            int(r.get("edad") or 14),
            3,  # 3º de secundaria
            str(r.get("tamano_familia") or "Mas de 3"),
            int(r.get("educacion_madre_0_4") or 2),
            int(r.get("educacion_padre_0_4") or 2),
            str(r.get("ocupacion_madre") or "Agricultora"),
            str(r.get("ocupacion_padre") or "Agricultor"),
            internet,
            str(r.get("tiempo_estudio_semanal") or "2-5 h"),
            str(r.get("tiempo_desplazamiento") or "15-30 min"),
            dist_km,
            int(r.get("repeticiones_previas") or 0),
            to_int_bool(r.get("apoyo_escolar")),
            to_int_bool(r.get("apoyo_familiar")),
            juntos,
            trabajo_h,
            dias,
            f1,
            f2,
            n1,
            n2,
            faltas_tot,
            asist_pct,
            prom,
            prob_ab,
            pred_n3,
            pred_f3,
            prob_beca,
            prob_rep,
            interv,
            desanimo,
            factor,
            recom,
            "borjavalher"
        ))

    insert_sql = """
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
        indice_desanimo, factor_principal_riesgo, recomendacion_pedagogica,
        docente_tutor
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
        ?, ?, ?,
        ?
    );
    """

    cur.executemany(insert_sql, rows_borja)
    print(f"Insertados/actualizados {len(rows_borja)} alumnos para borjavalher.")

    # -------------------------------------------------------------------------
    # 2. Clase de demostración 'docente': ESC-01, 2º de Secundaria, tutor = 'docente'
    # -------------------------------------------------------------------------
    print("Preparando 30 alumnos para docente demo (ESC-01, 2º de secundaria)...")
    g2 = df[df["grado_secundaria"] == 2].copy()
    if len(g2) < 30:
        g2 = df.copy()

    sample_g2 = g2.sample(30, random_state=123).reset_index(drop=True)
    rows_demo = []
    for i, (_, r) in enumerate(sample_g2.iterrows()):
        aid = f"ALU-2{i+1:04d}"
        f1 = int(r.get("faltas_trimestre_1") or 1)
        f2 = int(r.get("faltas_trimestre_2") or 2)
        dias = int(r.get("dias_lectivos_previstos") or 116)
        faltas_tot = f1 + f2
        asist_pct = round(max(0.0, ((dias - faltas_tot) / dias) * 100), 2)

        n1 = round(float(r.get("nota_trimestre_1_0_20") or 13.0), 2)
        n2 = round(float(r.get("nota_trimestre_2_0_20") or 13.0), 2)
        prom = round((n1 + n2) / 2.0, 2)

        juntos = to_int_bool(r.get("beneficiario_juntos"))
        internet = to_int_bool(r.get("internet_hogar"))
        dist_km = round(float(r.get("distancia_hogar_escuela_km") or 1.8), 2)
        trabajo_h = round(float(r.get("horas_trabajo_semanal") or 0.0), 1)

        row_dict = {
            "distancia_hogar_escuela_km": dist_km,
            "horas_trabajo_semanal": trabajo_h,
            "promedio_notas_calculado": prom,
            "faltas_trimestre_1": f1,
            "faltas_trimestre_2": f2,
            "beneficiario_juntos": juntos,
            "asistencia_pct_calculada": asist_pct,
        }
        factor, recom = generate_factors_and_recommendation(row_dict)

        interv = str(r.get("necesidad_intervencion") or "Baja")
        prob_ab = round(float(r.get("prob_abandono_pct") or np.random.uniform(4.0, 28.0)), 1)
        pred_n3 = round(float(r.get("nota_trimestre_3_real") or prom), 1)
        pred_f3 = int(r.get("ausencias_trimestre_3") or 3)
        prob_rep = round(float(np.random.uniform(1.0, 15.0)), 1)
        prob_beca = round(prob_ab * 0.7, 1) if juntos == 1 else 0.0
        desanimo = round(float(r.get("desanimo_calculado") or 4.5), 2)

        rows_demo.append((
            aid,
            "ESC-01",
            "UGEL-01-NORTE",
            str(r.get("distrito") or "Distrito Central"),
            str(r.get("zona_escuela") or "Urbana"),
            str(r.get("sexo") or "F"),
            int(r.get("edad") or 13),
            2,  # 2º de secundaria
            str(r.get("tamano_familia") or "3 o menos"),
            int(r.get("educacion_madre_0_4") or 2),
            int(r.get("educacion_padre_0_4") or 2),
            str(r.get("ocupacion_madre") or "Servicios"),
            str(r.get("ocupacion_padre") or "Comercio"),
            internet,
            str(r.get("tiempo_estudio_semanal") or "2-5 h"),
            str(r.get("tiempo_desplazamiento") or "15-30 min"),
            dist_km,
            int(r.get("repeticiones_previas") or 0),
            to_int_bool(r.get("apoyo_escolar")),
            to_int_bool(r.get("apoyo_familiar")),
            juntos,
            trabajo_h,
            dias,
            f1,
            f2,
            n1,
            n2,
            faltas_tot,
            asist_pct,
            prom,
            prob_ab,
            pred_n3,
            pred_f3,
            prob_beca,
            prob_rep,
            interv,
            desanimo,
            factor,
            recom,
            "docente"
        ))

    cur.executemany(insert_sql, rows_demo)
    print(f"Insertados/actualizados {len(rows_demo)} alumnos para docente demo.")

    conn.commit()
    conn.close()

    # -------------------------------------------------------------------------
    # Verificaciones finales
    # -------------------------------------------------------------------------
    count_borja = db_adapter.fetch_one(
        "SELECT COUNT(*) AS total FROM alumnos_hack4edu WHERE escuela_id = 'USAL-01' AND grado_secundaria = 3;"
    )
    count_demo = db_adapter.fetch_one(
        "SELECT COUNT(*) AS total FROM alumnos_hack4edu WHERE escuela_id = 'ESC-01' AND grado_secundaria = 2;"
    )
    total_db = db_adapter.fetch_one("SELECT COUNT(*) AS total FROM alumnos_hack4edu;")

    print("\n================== ESTADO DE LA BASE DE DATOS ==================")
    print(f"Total en clase de borjavalher (USAL-01, 3º de secundaria): {count_borja['total']}")
    print(f"Total en clase de docente (ESC-01, 2º de secundaria):     {count_demo['total']}")
    print(f"Total general en tabla alumnos_hack4edu:                 {total_db['total']}")
    print("================================================================\n")


if __name__ == "__main__":
    seed_classroom_students()
