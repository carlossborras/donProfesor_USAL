import joblib
import numpy as np
import pandas as pd

from lightgbm import LGBMClassifier, LGBMRegressor
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor, VotingClassifier, VotingRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, OneHotEncoder

# 1. Carga del histórico de entrenamiento
RUTA_DATOS = 'alumnos_peru_sintetico (1).csv'
df = pd.read_csv(RUTA_DATOS)

# 2. Perfil de entrada (X): Lo que sabemos el día de la matriculación
numeric_features = ['distancia_hogar_escuela_km', 'horas_trabajo_semanal', 'dias_lectivos_previstos']

categorical_features = [
    'sexo', 'zona_escuela', 'ocupacion_madre', 'ocupacion_padre', 
    'tiempo_estudio_semanal', 'tiempo_desplazamiento', 'tamano_familia'
]

binary_ordinal_features = [
    'educacion_madre_0_4', 'educacion_padre_0_4', 'grado_secundaria', 'edad',
    'repeticiones_previas', 'internet_hogar', 'apoyo_escolar', 
    'apoyo_familiar', 'beneficiario_juntos'
]

features = numeric_features + categorical_features + binary_ordinal_features
X = df[features].copy()

# 3. Variables objetivo a aprender (y): El curso completo
targets_clasificacion = ['abandono_escolar', 'perdida_beca', 'repeticion', 'necesidad_intervencion']
targets_regresion = [
    'nota_trimestre_1_0_20', 'faltas_trimestre_1',
    'nota_trimestre_2_0_20', 'faltas_trimestre_2',
    'nota_trimestre_3_real', 'ausencias_trimestre_3',
    'desanimo_calculado'
]

# 4. Arquitectura de preprocesamiento y ensamblados
preprocessor = ColumnTransformer(
    transformers=[
        ('num', Pipeline([('imputar', SimpleImputer(strategy='median')), ('escalar', StandardScaler())]), numeric_features),
        ('cat', Pipeline([('imputar', SimpleImputer(strategy='most_frequent')), ('onehot', OneHotEncoder(drop='first', handle_unknown='ignore'))]), categorical_features),
        ('bin', SimpleImputer(strategy='most_frequent'), binary_ordinal_features)
    ])

clf_ensemble = VotingClassifier([
    ('rf', RandomForestClassifier(n_estimators=100, max_depth=7, class_weight='balanced', random_state=42)),
    ('lgbm', LGBMClassifier(n_estimators=100, max_depth=7, class_weight='balanced', random_state=42, verbose=-1))
], voting='soft')

reg_ensemble = VotingRegressor([
    ('rf', RandomForestRegressor(n_estimators=100, max_depth=7, random_state=42)),
    ('lgbm', LGBMRegressor(n_estimators=100, max_depth=7, random_state=42, verbose=-1))
])

pipe_clf = Pipeline([('preprocesamiento', preprocessor), ('modelo', clf_ensemble)])
pipe_reg = Pipeline([('preprocesamiento', preprocessor), ('modelo', reg_ensemble)])

# 5. Bucle de Entrenamiento
artefactos_exportacion = {'modelos': {}}

print("Entrenando modelos de clasificación...")
for target in targets_clasificacion:
    print(f" -> Aprendiendo patrones de: {target}")
    artefactos_exportacion['modelos'][target] = clone(pipe_clf).fit(X, df[target])

print("Entrenando modelos de regresión...")
for target in targets_regresion:
    print(f" -> Aprendiendo patrones de: {target}")
    artefactos_exportacion['modelos'][target] = clone(pipe_reg).fit(X, df[target])

# 6. Extracción de metadatos para la explicabilidad (Factores de riesgo)
modelo_abandono = artefactos_exportacion['modelos']['abandono_escolar']
preproc_entrenado = modelo_abandono.named_steps['preprocesamiento']

nombres_cat = preproc_entrenado.named_transformers_['cat'].named_steps['onehot'].get_feature_names_out(categorical_features).tolist()
artefactos_exportacion['nombres_variables'] = numeric_features + nombres_cat + binary_ordinal_features
artefactos_exportacion['pesos_abandono'] = modelo_abandono.named_steps['modelo'].estimators_[0].feature_importances_

# 7. Exportación del paquete completo
joblib.dump(artefactos_exportacion, 'paquete_modelos_dia_cero.joblib')
print("\n[OK] Entrenamiento finalizado. Archivo 'paquete_modelos_dia_cero.joblib' listo para el Backend.")