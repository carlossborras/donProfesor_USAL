"""
DONPROFESOR (#Hack4Edu 2026, Reto 13) · Pipeline de Modelos Predictivos (Persona 2).
Entrena y predice las 7 variables objetivo oficiales a partir de las 30 variables de entrada:
1. prob_abandono_pct (FLOAT 0-100)
2. prediccion_nota_t3 (FLOAT 0-20)
3. prediccion_faltas_t3 (INT días de ausencia proyectados)
4. prob_perdida_beca_pct (FLOAT 0-100)
5. prob_repeticion_pct (FLOAT 0-100)
6. necesidad_intervencion (VARCHAR: 'Alta', 'Media', 'Baja')
7. indice_desanimo (FLOAT 0-100)
Adicionalmente genera explicabilidad pedagógica (factor_principal_riesgo y recomendacion_pedagogica).
"""

from __future__ import annotations
import argparse
import pickle
from pathlib import Path
from typing import Dict, Any, Tuple, List

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.preprocessing import StandardScaler

MODEL_DIR = Path(__file__).resolve().parent
CHECKPOINT_DIR = MODEL_DIR / "checkpoints"
CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

# 30 Variables de entrada oficiales (Reto 13)
NUMERIC_FEATURES = [
    "edad",
    "grado_secundaria",
    "tamano_familia",
    "educacion_madre_0_4",
    "educacion_padre_0_4",
    "internet_hogar",
    "tiempo_estudio_semanal",
    "tiempo_desplazamiento",
    "distancia_hogar_escuela_km",
    "repeticiones_previas",
    "apoyo_escolar",
    "apoyo_familiar",
    "beneficiario_juntos",
    "horas_trabajo_semanal",
    "dias_lectivos_previstos",
    "faltas_trimestre_1",
    "faltas_trimestre_2",
    "nota_trimestre_1_0_20",
    "nota_trimestre_2_0_20",
    "faltas_totales_calculadas",
    "asistencia_pct_calculada",
    "promedio_notas_calculado",
]

CATEGORICAL_FEATURES = [
    "zona_escuela",
    "sexo",
]


def generate_synthetic_dataset(n_samples: int = 1500, seed: int = 42) -> pd.DataFrame:
    """Genera un dataset sintético coherente con las reglas del sistema educativo peruano y Reto 13."""
    rng = np.random.default_rng(seed)

    records = []
    escuelas = ["ESC-01", "ESC-02", "ESC-03", "ESC-04"]
    distritos_rurales = ["Valle del Río", "La Quebrada", "San Pedro de Puna"]
    distritos_urbanos = ["Cerro Verde", "El Molino"]

    for i in range(1, n_samples + 1):
        aid = f"ALU-{i:05d}"
        esc = rng.choice(escuelas)
        is_rural = rng.random() < 0.55
        dist = rng.choice(distritos_rurales) if is_rural else rng.choice(distritos_urbanos)
        zona = "Rural" if is_rural else "Urbana"
        sexo = rng.choice(["M", "F"])
        grado = int(rng.integers(1, 6))
        edad = int(grado + 11 + rng.choice([0, 0, 0, 1, 2], p=[0.75, 0.12, 0.08, 0.03, 0.02]))
        tamano_familia = int(rng.integers(3, 8))

        edu_m = int(rng.integers(0, 4))
        edu_p = int(rng.integers(0, 4))
        ocup_m = "Agricultora" if is_rural else "Comercio"
        ocup_p = "Agricultor" if is_rural else "Transporte / Construcción"

        internet = 1 if (not is_rural and rng.random() < 0.70) or (is_rural and rng.random() < 0.20) else 0
        juntos = 1 if (is_rural and rng.random() < 0.65) or (not is_rural and rng.random() < 0.25) else 0

        dist_km = round(float(rng.uniform(0.5, 8.5) if is_rural else rng.uniform(0.2, 3.0)), 2)
        minutos = int(dist_km * 12 + rng.integers(5, 20))

        trabajo_h = round(float(rng.uniform(4.0, 20.0) if (is_rural and rng.random() < 0.40) else 0.0), 1)
        estudio_sem = round(float(max(1.0, 10.0 - trabajo_h * 0.4 + rng.normal(0, 2))), 1)

        repeticiones = int(rng.choice([0, 1, 2], p=[0.82, 0.14, 0.04]))
        apoyo_esc = int(rng.choice([0, 1], p=[0.75, 0.25]))
        apoyo_fam = int(rng.choice([0, 1], p=[0.30, 0.70]))

        dias = 180
        # Faltas: mayor en época de lluvia/cosecha (T2) si vive lejos o trabaja
        base_f1 = rng.integers(1, 8)
        incremento_t2 = int(
            (dist_km > 3.5) * rng.integers(3, 10) +
            (trabajo_h > 5) * rng.integers(4, 12) +
            rng.integers(0, 4)
        )
        f1 = int(base_f1)
        f2 = int(f1 + incremento_t2)
        faltas_tot = f1 + f2
        asist_pct = round(max(0.0, ((dias - faltas_tot) / dias) * 100), 2)

        # Notas en escala vigesimal 0-20
        base_nota = 14.5 - (dist_km * 0.3) - (trabajo_h * 0.2) + (apoyo_fam * 1.5) + (internet * 1.2) - (repeticiones * 1.8)
        nota_1 = round(float(np.clip(base_nota + rng.normal(0, 1.8), 5.0, 20.0)), 1)
        # Nota T2 refleja desgaste por lluvia y ausencias
        caida_t2 = (incremento_t2 > 6) * rng.uniform(1.0, 3.5)
        nota_2 = round(float(np.clip(nota_1 - caida_t2 + rng.normal(0, 1.0), 4.0, 20.0)), 1)
        prom = round(float((nota_1 + nota_2) / 2.0), 2)

        # Generar las 7 variables objetivo coherentes
        p_nota3 = round(float(np.clip(nota_2 + (nota_2 - nota_1) * 0.4 + rng.normal(0, 1.2), 3.0, 20.0)), 1)
        p_falt3 = int(max(0, round(f2 * 0.9 + (dist_km > 4.0) * 3 + rng.normal(0, 2))))

        score_riesgo = (
            (20.0 - prom) * 3.5 +
            (100.0 - asist_pct) * 1.2 +
            (dist_km * 2.5) +
            (trabajo_h * 1.8) +
            (repeticiones * 8.0) -
            (juntos * 6.0) -
            (internet * 4.0)
        )
        score_riesgo = float(np.clip(score_riesgo + rng.normal(0, 5), 0.0, 100.0))

        prob_ab = round(float(np.clip(score_riesgo * 0.85, 2.0, 95.0)), 1)
        prob_rep = round(float(np.clip((14.0 - prom) * 8.5 + (100.0 - asist_pct) * 0.8, 1.0, 98.0)), 1)
        desanimo = round(float(score_riesgo), 1)

        if score_riesgo > 55.0 or prom < 10.5 or asist_pct < 78.0:
            necesidad = "Alta"
        elif score_riesgo > 32.0 or prom < 12.5 or asist_pct < 85.0:
            necesidad = "Media"
        else:
            necesidad = "Baja"

        prob_beca = (
            round(float(np.clip((100.0 - asist_pct) * 2.2 + p_falt3 * 2.5, 5.0, 95.0)), 1)
            if juntos == 1
            else 0.0
        )

        # Explicabilidad pedagógica
        if dist_km >= 3.5 and incremento_t2 > 5:
            factor = f"Distancia de desplazamiento ({dist_km} km) e incremento de ausencias por clima en T2"
            recom = "Flexibilizar entregas en días de lluvia y coordinar transporte escolar rural."
        elif trabajo_h > 6:
            factor = f"Carga laboral semanal ({trabajo_h} h) con reducción de horas de estudio ({estudio_sem} h)"
            recom = "Adaptar el calendario de tareas para compatibilizar la época de cosecha con la permanencia escolar."
        elif prom < 11.0:
            factor = f"Rendimiento vigesimal bajo en T2 ({nota_2}/20) con riesgo de no superación de grado"
            recom = "Refuerzo pedagógico en materias instrumentales y acompañamiento individualizado."
        else:
            factor = "Trayectoria escolar regular y compromiso familiar sostenido"
            recom = "Mantener el seguimiento formativo habitual."

        records.append({
            "alumno_id": aid,
            "escuela_id": esc,
            "ugel": "UGEL-01-NORTE",
            "distrito": dist,
            "zona_escuela": zona,
            "sexo": sexo,
            "edad": edad,
            "grado_secundaria": grado,
            "tamano_familia": tamano_familia,
            "educacion_madre_0_4": edu_m,
            "educacion_padre_0_4": edu_p,
            "ocupacion_madre": ocup_m,
            "ocupacion_padre": ocup_p,
            "internet_hogar": internet,
            "tiempo_estudio_semanal": estudio_sem,
            "tiempo_desplazamiento": minutos,
            "distancia_hogar_escuela_km": dist_km,
            "repeticiones_previas": repeticiones,
            "apoyo_escolar": apoyo_esc,
            "apoyo_familiar": apoyo_fam,
            "beneficiario_juntos": juntos,
            "horas_trabajo_semanal": trabajo_h,
            "dias_lectivos_previstos": dias,
            "faltas_trimestre_1": f1,
            "faltas_trimestre_2": f2,
            "nota_trimestre_1_0_20": nota_1,
            "nota_trimestre_2_0_20": nota_2,
            "faltas_totales_calculadas": faltas_tot,
            "asistencia_pct_calculada": asist_pct,
            "promedio_notas_calculado": prom,
            "prob_abandono_pct": prob_ab,
            "prediccion_nota_t3": p_nota3,
            "prediccion_faltas_t3": p_falt3,
            "prob_perdida_beca_pct": prob_beca,
            "prob_repeticion_pct": prob_rep,
            "necesidad_intervencion": necesidad,
            "indice_desanimo": desanimo,
            "factor_principal_riesgo": factor,
            "recomendacion_pedagogica": recom,
        })

    return pd.DataFrame(records)


def prepare_features(df: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
    """Convierte las 30 variables de entrada en vector numérico para los modelos."""
    df_copy = df.copy()

    # Variables calculadas si faltan
    if "faltas_totales_calculadas" not in df_copy.columns:
        df_copy["faltas_totales_calculadas"] = (
            df_copy.get("faltas_trimestre_1", 0) + df_copy.get("faltas_trimestre_2", 0)
        )
    if "asistencia_pct_calculada" not in df_copy.columns:
        dias = df_copy.get("dias_lectivos_previstos", 180)
        df_copy["asistencia_pct_calculada"] = np.clip(
            ((dias - df_copy["faltas_totales_calculadas"]) / dias) * 100, 0.0, 100.0
        )
    if "promedio_notas_calculado" not in df_copy.columns:
        df_copy["promedio_notas_calculado"] = (
            df_copy.get("nota_trimestre_1_0_20", 12.0) + df_copy.get("nota_trimestre_2_0_20", 12.0)
        ) / 2.0

    X_num = df_copy[NUMERIC_FEATURES].fillna(0).values

    # Codificación de categóricas
    zona_encoded = (df_copy["zona_escuela"].astype(str).str.lower() == "rural").astype(float).values[:, None]
    sexo_encoded = (df_copy["sexo"].astype(str).str.upper() == "M").astype(float).values[:, None]

    X = np.hstack([X_num, zona_encoded, sexo_encoded])
    feature_names = NUMERIC_FEATURES + ["is_rural", "is_male"]
    return X, feature_names


def train_models(df_train: pd.DataFrame) -> Dict[str, Any]:
    """Entrena los estimadores Random Forest para cada variable objetivo."""
    X, feat_names = prepare_features(df_train)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    models = {}

    # 1. Regresión para notas y porcentajes
    targets_reg = {
        "prediccion_nota_t3": df_train["prediccion_nota_t3"].values,
        "prediccion_faltas_t3": df_train["prediccion_faltas_t3"].values,
        "prob_abandono_pct": df_train["prob_abandono_pct"].values,
        "prob_perdida_beca_pct": df_train["prob_perdida_beca_pct"].fillna(0).values,
        "prob_repeticion_pct": df_train["prob_repeticion_pct"].values,
        "indice_desanimo": df_train["indice_desanimo"].values,
    }

    for name, y in targets_reg.items():
        reg = RandomForestRegressor(n_estimators=100, max_depth=8, random_state=42)
        reg.fit(X_scaled, y)
        models[name] = reg

    # 2. Clasificación para necesidad_intervencion ('Alta', 'Media', 'Baja')
    clf = RandomForestClassifier(n_estimators=100, max_depth=6, random_state=42)
    clf.fit(X_scaled, df_train["necesidad_intervencion"].values)
    models["necesidad_intervencion"] = clf

    pipeline_package = {
        "models": models,
        "scaler": scaler,
        "feature_names": feat_names,
    }

    out_path = CHECKPOINT_DIR / "donprofesor_rf_models.pkl"
    with open(out_path, "wb") as f:
        pickle.dump(pipeline_package, f)

    print(f"[OK] Modelos entrenados y guardados en {out_path}")
    return pipeline_package


def predict_dataset(df_input: pd.DataFrame, pipeline: Dict[str, Any] = None) -> pd.DataFrame:
    """Aplica el modelo entrenado sobre un dataset con las 30 variables de entrada."""
    if pipeline is None:
        pkl_path = CHECKPOINT_DIR / "donprofesor_rf_models.pkl"
        if not pkl_path.exists():
            print("[INFO] Checkpoint no encontrado. Entrenando modelos base...")
            df_train = generate_synthetic_dataset(1200)
            pipeline = train_models(df_train)
        else:
            with open(pkl_path, "rb") as f:
                pipeline = pickle.load(f)

    models = pipeline["models"]
    scaler = pipeline["scaler"]

    X, _ = prepare_features(df_input)
    X_scaled = scaler.transform(X)

    df_res = df_input.copy()

    df_res["prob_abandono_pct"] = np.round(np.clip(models["prob_abandono_pct"].predict(X_scaled), 0.0, 100.0), 1)
    df_res["prediccion_nota_t3"] = np.round(np.clip(models["prediccion_nota_t3"].predict(X_scaled), 0.0, 20.0), 1)
    df_res["prediccion_faltas_t3"] = np.round(np.clip(models["prediccion_faltas_t3"].predict(X_scaled), 0, 50)).astype(int)
    df_res["prob_perdida_beca_pct"] = np.round(np.clip(models["prob_perdida_beca_pct"].predict(X_scaled), 0.0, 100.0), 1)
    # Solo aplica pérdida de beca si es beneficiario de Juntos
    df_res.loc[df_res["beneficiario_juntos"] == 0, "prob_perdida_beca_pct"] = 0.0

    df_res["prob_repeticion_pct"] = np.round(np.clip(models["prob_repeticion_pct"].predict(X_scaled), 0.0, 100.0), 1)
    df_res["indice_desanimo"] = np.round(np.clip(models["indice_desanimo"].predict(X_scaled), 0.0, 100.0), 1)
    df_res["necesidad_intervencion"] = models["necesidad_intervencion"].predict(X_scaled)

    # Explicabilidad pedagógica
    factores = []
    recoms = []
    for _, row in df_res.iterrows():
        dist = row.get("distancia_hogar_escuela_km", 0)
        trabajo = row.get("horas_trabajo_semanal", 0)
        prom = row.get("promedio_notas_calculado", 12)
        asist = row.get("asistencia_pct_calculada", 90)

        if dist >= 3.5:
            factores.append(f"Distancia al centro educativo ({dist} km) y dificultad en días de lluvia")
            recoms.append("Flexibilizar entregas y facilitar recursos impresos offline.")
        elif trabajo > 5:
            factores.append(f"Horas de trabajo semanal ({trabajo} h) en semanas de cosecha agrícola")
            recoms.append("Coordinar con la familia un calendario adaptado para proteger su continuidad.")
        elif prom < 11.0:
            factores.append(f"Descenso de notas en el segundo trimestre (promedio {prom}/20)")
            recoms.append("Refuerzo pedagógico en grupos pequeños y tutoría individual.")
        else:
            factores.append("Evolución académica regular y vínculo escolar estable")
            recoms.append("Acompañamiento pedagógico ordinario.")

    df_res["factor_principal_riesgo"] = factores
    df_res["recomendacion_pedagogica"] = recoms

    return df_res


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DONPROFESOR · Modelo Predictivo (Reto 13)")
    parser.add_argument("--generate-train", type=int, help="Genera CSV de entrenamiento sintético y lo guarda en data/train.csv")
    parser.add_argument("--train", action="store_true", help="Entrena los modelos y guarda donprofesor_rf_models.pkl")
    parser.add_argument("--predict", type=str, help="Ruta al CSV de entrada (30 variables) para generar predicciones")
    parser.add_argument("--output", type=str, default="data/alumnos_predicciones.csv", help="Ruta del CSV generado")
    parser.add_argument("--predict-and-load", type=str, help="Genera predicciones sobre un CSV y las importa directamente en la BD real")

    args = parser.parse_args()

    data_dir = MODEL_DIR.parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    if args.generate_train:
        df = generate_synthetic_dataset(args.generate_train)
        target = data_dir / "dataset_entrenamiento_reto13.csv"
        df.to_csv(target, index=False, encoding="utf-8")
        print(f"[OK] Generado dataset de entrenamiento con {len(df)} registros en {target}")
    elif args.train:
        df = generate_synthetic_dataset(1500)
        train_models(df)
    elif args.predict:
        df_in = pd.read_csv(args.predict)
        df_out = predict_dataset(df_in)
        out_p = Path(args.output)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        df_out.to_csv(out_p, index=False, encoding="utf-8")
        print(f"[OK] Predicciones generadas con éxito en {out_p} ({len(df_out)} filas).")
    elif args.predict_and_load:
        from db.import_csv import import_csv_file
        df_in = pd.read_csv(args.predict_and_load)
        df_out = predict_dataset(df_in)
        tmp = data_dir / "temp_predicciones.csv"
        df_out.to_csv(tmp, index=False, encoding="utf-8")
        count = import_csv_file(str(tmp))
        tmp.unlink(missing_ok=True)
        print(f"[OK] Se predijeron e importaron {count} alumnos en la base de datos real.")
    else:
        # Por defecto: entrenar si no existe y generar un archivo de ejemplo listo para el equipo
        print("Ejecutando pipeline de preparación inicial...")
        df_train = generate_synthetic_dataset(1500)
        train_models(df_train)
        sample_input = df_train[NUMERIC_FEATURES + CATEGORICAL_FEATURES + ["alumno_id", "escuela_id", "ugel", "distrito", "ocupacion_madre", "ocupacion_padre"]].head(50)
        sample_output = predict_dataset(sample_input)
        sample_path = data_dir / "ejemplo_50_alumnos_con_predicciones.csv"
        sample_output.to_csv(sample_path, index=False, encoding="utf-8")
        print(f"[OK] Archivo de ejemplo con las 37 variables guardado en {sample_path}")
