"""
DONPROFESOR (#Hack4Edu 2026, Reto 13) · Carga de estudiantes (con predicción automática).

  POST /api/datos/alumno         -> alta manual de un estudiante (formulario)
  POST /api/datos/importar-csv   -> subida de CSV/TSV
  POST /api/datos/pegar          -> datos pegados desde Excel / Google Sheets
  POST /api/datos/semilla-prueba -> carga la muestra data/muestra_30_alumnos_peru.csv en TU ámbito
  POST /api/datos/vaciar         -> borra SOLO los estudiantes de tu ámbito

Cada alta o importación ejecuta el modelo predictivo (db/students.py).
"""

from __future__ import annotations

import hashlib

from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from api.security import get_current_user
from db.students import DatosInvalidos, guardar_alumnos, leer_tabla, vaciar_ambito
from model.config import ROOT_DIR

router = APIRouter(prefix="/api/datos", tags=["datos"])

MUESTRA = ROOT_DIR / "data" / "muestra_30_alumnos_peru.csv"
MAX_BYTES = 10 * 1024 * 1024


class PasteDataRequest(BaseModel):
    data_text: str = Field(min_length=1, max_length=MAX_BYTES)


def _mensaje(resumen: Dict[str, Any]) -> str:
    partes = []
    if resumen["creados"]:
        partes.append(f"{resumen['creados']} estudiante(s) dados de alta")
    if resumen["actualizados"]:
        partes.append(f"{resumen['actualizados']} actualizado(s)")
    if resumen["rechazados"]:
        partes.append(f"{len(resumen['rechazados'])} rechazado(s)")
    texto = ", ".join(partes) or "No se ha guardado ningún estudiante"
    pred = resumen["predicciones"]
    if pred["calculadas"]:
        texto += f". Predicciones calculadas para {pred['calculadas']}."
    elif pred["pendientes"]:
        texto += ". Las predicciones quedan pendientes: el modelo no está disponible."
    if resumen["datos_incompletos"]:
        texto += f" {resumen['datos_incompletos']} con datos incompletos (el modelo ha estimado los que faltan)."
    return texto


def _responder(resumen: Dict[str, Any]) -> Dict[str, Any]:
    return {"message": _mensaje(resumen), **resumen}


@router.post("/alumno", summary="Dar de alta un estudiante y predecir")
def crear_alumno(datos: Dict[str, Any] = Body(...), user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    try:
        resumen = guardar_alumnos([datos], user, generar_id=True)
    except DatosInvalidos as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    if not resumen["alumno_ids"]:
        motivo = resumen["rechazados"][0]["motivo"] if resumen["rechazados"] else "Datos no válidos."
        raise HTTPException(status_code=422, detail=motivo)
    return _responder(resumen)


@router.post("/importar-csv", summary="Importar un CSV de estudiantes y predecir")
async def importar_csv(file: UploadFile = File(...), user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    contenido = await file.read(MAX_BYTES + 1)
    if len(contenido) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="El fichero supera los 10 MB.")
    try:
        return _responder(guardar_alumnos(leer_tabla(contenido), user))
    except DatosInvalidos as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.post("/pegar", summary="Importar datos pegados desde una hoja de cálculo")
def pegar(req: PasteDataRequest, user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    try:
        return _responder(guardar_alumnos(leer_tabla(req.data_text), user))
    except DatosInvalidos as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.post("/semilla-prueba", summary="Cargar la muestra de 30 estudiantes en tu ámbito")
def semilla(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    if not MUESTRA.exists():
        raise HTTPException(status_code=404, detail="No se encuentra data/muestra_30_alumnos_peru.csv.")
    filas = leer_tabla(MUESTRA.read_bytes())
    # Cada ámbito recibe su propia copia de la muestra: el código se marca con una huella del ámbito
    # para que dos personas puedan cargarla sin chocar entre sí.
    ambito = "|".join(str(user.get(k) or "").strip().upper() for k in ("rol", "escuela_id", "grado_secundaria", "ugel"))
    huella = hashlib.sha1(ambito.encode("utf-8")).hexdigest()[:6].upper()
    for f in filas:
        f["alumno_id"] = f"{f.get('alumno_id')}-{huella}"
        if user.get("rol") == "delegado":
            f["ugel"] = None  # la muestra se asigna a la UGEL de quien la carga
    try:
        return _responder(guardar_alumnos(filas, user))
    except DatosInvalidos as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.post("/vaciar", summary="Borrar los estudiantes de tu ámbito")
def vaciar(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    borrados = vaciar_ambito(user)
    return {"status": "ok", "message": f"Se han borrado {borrados} estudiantes de tu ámbito.", "borrados": borrados}
