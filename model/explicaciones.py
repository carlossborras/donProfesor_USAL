"""
DONPROFESOR · Textos para explicar las predicciones a personas (no contiene números del modelo).

- ETIQUETAS: nombre legible de cada variable de entrada del modelo.
- SUGERENCIAS: idea de acompañamiento cuando esa variable empuja la predicción al alza.
  Son orientaciones para el criterio profesional, nunca decisiones.
"""

from __future__ import annotations

from typing import Any, Optional

ETIQUETAS = {
    "distancia_hogar_escuela_km": "Distancia de casa a la escuela",
    "horas_trabajo_semanal": "Horas de trabajo a la semana",
    "dias_lectivos_previstos": "Días lectivos previstos",
    "sexo": "Sexo",
    "zona_escuela": "Zona de la escuela",
    "ocupacion_madre": "Ocupación de la madre",
    "ocupacion_padre": "Ocupación del padre",
    "tiempo_estudio_semanal": "Tiempo de estudio en casa",
    "tiempo_desplazamiento": "Tiempo de desplazamiento",
    "tamano_familia": "Tamaño de la familia",
    "educacion_madre_0_4": "Estudios de la madre",
    "educacion_padre_0_4": "Estudios del padre",
    "grado_secundaria": "Grado",
    "edad": "Edad",
    "repeticiones_previas": "Cursos repetidos antes",
    "internet_hogar": "Internet en casa",
    "apoyo_escolar": "Apoyo escolar (refuerzo)",
    "apoyo_familiar": "Apoyo de la familia en los estudios",
    "beneficiario_juntos": "Familia en el programa Juntos",
}

SUGERENCIAS = {
    "distancia_hogar_escuela_km": "Valorar apoyo de transporte o materiales para estudiar en casa los días sin clase.",
    "tiempo_desplazamiento": "Flexibilizar la hora de entrada y facilitar materiales impresos.",
    "horas_trabajo_semanal": "Hablar con la familia para compatibilizar el trabajo (p. ej. la cosecha) con la escuela.",
    "tiempo_estudio_semanal": "Proponer rutinas cortas de estudio y espacios de estudio en la escuela.",
    "internet_hogar": "Ofrecer materiales sin conexión y acceso a dispositivos en la escuela.",
    "apoyo_escolar": "Incluir al estudiante en grupos de refuerzo.",
    "apoyo_familiar": "Mantener una tutoría con la familia para implicarla en el seguimiento.",
    "repeticiones_previas": "Plan de seguimiento individual desde el inicio del curso.",
    "beneficiario_juntos": "Vigilar la asistencia para proteger el subsidio y coordinar con el programa Juntos.",
    "educacion_madre_0_4": "Ofrecer orientación a la familia sobre cómo acompañar el estudio.",
    "educacion_padre_0_4": "Ofrecer orientación a la familia sobre cómo acompañar el estudio.",
}

EDUCACION = {0: "sin estudios", 1: "primaria", 2: "secundaria", 3: "superior no universitaria", 4: "universitaria"}
SI_NO = {"internet_hogar", "apoyo_escolar", "apoyo_familiar", "beneficiario_juntos"}


def describir_valor(variable: str, valor: Any) -> Optional[str]:
    """Texto corto con el valor del estudiante (p. ej. «6.5 km», «no», «primaria»)."""
    if valor is None or (isinstance(valor, float) and valor != valor):
        return None
    if variable in SI_NO:
        try:
            return "sí" if float(valor) >= 0.5 else "no"
        except (TypeError, ValueError):
            return str(valor)
    if variable in ("educacion_madre_0_4", "educacion_padre_0_4"):
        try:
            return EDUCACION.get(int(float(valor)), str(valor))
        except (TypeError, ValueError):
            return str(valor)
    if variable == "distancia_hogar_escuela_km":
        return f"{float(valor):g} km"
    if variable == "horas_trabajo_semanal":
        return f"{float(valor):g} h"
    if variable == "repeticiones_previas":
        return f"{int(float(valor))}"
    if variable == "edad":
        return f"{int(float(valor))} años"
    if isinstance(valor, (int, float)):
        return f"{float(valor):g}"
    return str(valor)


def texto_factor(variable: str, valor: Any) -> str:
    etiqueta = ETIQUETAS.get(variable, variable.replace("_", " ").capitalize())
    descripcion = describir_valor(variable, valor)
    return f"{etiqueta}: {descripcion}" if descripcion else etiqueta

# Variables que el modelo usa pero que NO se muestran como "factor" a las personas usuarias:
# no son accionables o mostrarlas podría estigmatizar (p. ej. el sexo).
NO_EXPLICAR = {"sexo", "grado_secundaria", "dias_lectivos_previstos"}
