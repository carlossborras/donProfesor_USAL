import React, { useEffect, useMemo, useState } from "react";
import { createStudentApi, fetchModelFieldsApi, pasteStudentDataApi } from "../services/api.js";

/* ==========================================================================
   ALTA DE ESTUDIANTES
   Los campos y sus opciones salen del propio modelo (GET /api/modelo/campos): así el formulario
   pide exactamente lo que el modelo necesita. Nada viene relleno: lo que dejes vacío lo estima el
   modelo (y se avisa). Al guardar, la API calcula las predicciones al momento.
   ========================================================================== */

const ETIQUETAS = {
  sexo: "Sexo",
  edad: "Edad",
  zona_escuela: "Zona de la escuela",
  distancia_hogar_escuela_km: "Distancia hogar–escuela (km)",
  tiempo_desplazamiento: "Tiempo de desplazamiento",
  tiempo_estudio_semanal: "Tiempo de estudio semanal",
  tamano_familia: "Tamaño de la familia",
  ocupacion_madre: "Ocupación de la madre",
  ocupacion_padre: "Ocupación del padre",
  educacion_madre_0_4: "Estudios de la madre (0–4)",
  educacion_padre_0_4: "Estudios del padre (0–4)",
  repeticiones_previas: "Cursos repetidos antes",
  horas_trabajo_semanal: "Horas de trabajo a la semana",
  dias_lectivos_previstos: "Días lectivos previstos",
  internet_hogar: "Internet en casa",
  apoyo_escolar: "Apoyo escolar",
  apoyo_familiar: "Apoyo familiar",
  beneficiario_juntos: "Familia en el programa Juntos",
  grado_secundaria: "Grado de secundaria",
};

const SI_NO = new Set(["internet_hogar", "apoyo_escolar", "apoyo_familiar", "beneficiario_juntos"]);
const RANGOS = {
  edad: { min: 10, max: 22, step: 1 },
  grado_secundaria: { min: 1, max: 5, step: 1 },
  educacion_madre_0_4: { min: 0, max: 4, step: 1 },
  educacion_padre_0_4: { min: 0, max: 4, step: 1 },
  repeticiones_previas: { min: 0, max: 5, step: 1 },
  distancia_hogar_escuela_km: { min: 0, max: 100, step: 0.1 },
  horas_trabajo_semanal: { min: 0, max: 80, step: 1 },
  dias_lectivos_previstos: { min: 1, max: 366, step: 1 },
};
const SEGUIMIENTO = [
  { id: "faltas_trimestre_1", label: "Faltas 1.er trimestre", min: 0, max: 200, step: 1 },
  { id: "faltas_trimestre_2", label: "Faltas 2.º trimestre", min: 0, max: 200, step: 1 },
  { id: "nota_trimestre_1_0_20", label: "Nota 1.er trimestre (0–20)", min: 0, max: 20, step: 0.1 },
  { id: "nota_trimestre_2_0_20", label: "Nota 2.º trimestre (0–20)", min: 0, max: 20, step: 0.1 },
];

const etiqueta = (c) => ETIQUETAS[c] || c.replace(/_/g, " ");

function Campo({ id, label, value, onChange, children, hint }) {
  return (
    <div className="form-group" style={{ marginBottom: 10 }}>
      <label htmlFor={`f-${id}`} style={{ fontSize: 12 }}>{label}</label>
      {children || (
        <input id={`f-${id}`} className="form-input" value={value ?? ""} onChange={(e) => onChange(e.target.value)} />
      )}
      {hint && <div className="muted" style={{ fontSize: 11 }}>{hint}</div>}
    </div>
  );
}

export function StudentEntryModal({ token, userRole = "docente", currentSchoolId, currentGrade, currentUgel, onClose, onSuccess }) {
  const [activeTab, setActiveTab] = useState("form");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [campos, setCampos] = useState(null);
  const [camposError, setCamposError] = useState(null);
  const [formData, setFormData] = useState({});
  const [pastedText, setPastedText] = useState("");

  useEffect(() => {
    let vivo = true;
    fetchModelFieldsApi(token)
      .then((r) => vivo && setCampos(r))
      .catch((err) => vivo && setCamposError(err.message || "No se pudo leer el modelo."));
    return () => {
      vivo = false;
    };
  }, [token]);

  const modelo = useMemo(() => {
    if (!campos) return [];
    const lista = [
      ...(campos.categoricas ? Object.keys(campos.categoricas) : []),
      ...(campos.numericas || []),
      ...(campos.binarias || []),
    ];
    // el grado lo fija el ámbito del docente
    return lista.filter((c) => !(userRole === "docente" && c === "grado_secundaria"));
  }, [campos, userRole]);

  const set = (campo, valor) => setFormData((prev) => ({ ...prev, [campo]: valor }));

  const handleFormSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    const datos = {};
    for (const [k, v] of Object.entries(formData)) {
      if (v !== "" && v !== null && v !== undefined) datos[k] = v;
    }
    try {
      const res = await createStudentApi(token, datos);
      onSuccess(res.message || "Estudiante guardado.");
      onClose();
    } catch (err) {
      setError(err.message || "Error al registrar el estudiante.");
    } finally {
      setLoading(false);
    }
  };

  const handlePasteSubmit = async (e) => {
    e.preventDefault();
    if (!pastedText.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await pasteStudentDataApi(token, pastedText);
      onSuccess(res.message || "Datos importados.");
      onClose();
    } catch (err) {
      setError(err.message || "Error al importar los datos pegados.");
    } finally {
      setLoading(false);
    }
  };

  const ambito =
    userRole === "docente"
      ? `Tu grupo: ${currentGrade ?? "?"}.º de secundaria · ${currentSchoolId ?? "sin escuela"}`
      : userRole === "director"
        ? `Tu escuela: ${currentSchoolId ?? "sin escuela"}`
        : `Tu UGEL: ${currentUgel ?? "sin UGEL"}`;

  const renderCampoModelo = (c) => {
    const opciones = campos?.categoricas?.[c];
    if (opciones) {
      return (
        <Campo key={c} id={c} label={etiqueta(c)}>
          <select id={`f-${c}`} className="form-select" value={formData[c] ?? ""} onChange={(e) => set(c, e.target.value)}>
            <option value="">— Sin dato —</option>
            {opciones.map((o) => (
              <option key={o} value={o}>{o}</option>
            ))}
          </select>
        </Campo>
      );
    }
    if (SI_NO.has(c)) {
      return (
        <Campo key={c} id={c} label={etiqueta(c)}>
          <select id={`f-${c}`} className="form-select" value={formData[c] ?? ""} onChange={(e) => set(c, e.target.value)}>
            <option value="">— Sin dato —</option>
            <option value="1">Sí</option>
            <option value="0">No</option>
          </select>
        </Campo>
      );
    }
    const r = RANGOS[c] || { step: "any" };
    return (
      <Campo key={c} id={c} label={etiqueta(c)}>
        <input
          id={`f-${c}`}
          className="form-input"
          type="number"
          min={r.min}
          max={r.max}
          step={r.step}
          required={c === "grado_secundaria"}
          value={formData[c] ?? ""}
          onChange={(e) => set(c, e.target.value)}
        />
      </Campo>
    );
  };

  return (
    <div className="modal-backdrop" onClick={onClose} role="dialog" aria-modal="true">
      <div className="modal-card" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 760, width: "95%", maxHeight: "90vh", overflowY: "auto" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
          <div>
            <h3 style={{ margin: 0, fontFamily: "Newsreader, serif", fontSize: 22, color: "#192823" }}>Dar de alta estudiantes</h3>
            <p style={{ margin: "4px 0 0", fontSize: 13, color: "#5a7066" }}>
              Al guardar, el modelo calcula sus predicciones al momento. Los datos sin rellenar los estima el modelo.
            </p>
            <div className="scope-chip">{ambito}</div>
          </div>
          <button type="button" onClick={onClose} aria-label="Cerrar" style={{ background: "transparent", border: "none", fontSize: 20, cursor: "pointer", color: "#5a7066" }}>
            &times;
          </button>
        </div>

        <div className="tab-row">
          <button type="button" className={`tab-btn ${activeTab === "form" ? "active" : ""}`} onClick={() => setActiveTab("form")}>Un estudiante</button>
          <button type="button" className={`tab-btn ${activeTab === "paste" ? "active" : ""}`} onClick={() => setActiveTab("paste")}>Pegar desde una hoja de cálculo</button>
        </div>

        {error && <div className="alert-error">{error}</div>}

        {activeTab === "form" ? (
          <form onSubmit={handleFormSubmit}>
            {camposError && (
              <div className="alert-warn">
                El modelo no está disponible ({camposError}). Puedes guardar al estudiante igualmente: sus predicciones quedarán pendientes.
              </div>
            )}
            <fieldset className="form-fieldset">
              <legend>Identificación y ámbito</legend>
              <div className="form-grid-3">
                <Campo id="alumno_id" label="Código del estudiante" value={formData.alumno_id} onChange={(v) => set("alumno_id", v)} hint="Si lo dejas vacío se genera uno." />
                {userRole === "delegado" && (
                  <Campo id="escuela_id" label="Escuela (código)" value={formData.escuela_id} onChange={(v) => set("escuela_id", v)}>
                    <input id="f-escuela_id" className="form-input" required value={formData.escuela_id ?? ""} onChange={(e) => set("escuela_id", e.target.value)} />
                  </Campo>
                )}
                {userRole !== "docente" && !modelo.includes("grado_secundaria") && (
                  <Campo id="grado_secundaria" label="Grado de secundaria">
                    <input id="f-grado_secundaria" className="form-input" type="number" min={1} max={5} required value={formData.grado_secundaria ?? ""} onChange={(e) => set("grado_secundaria", e.target.value)} />
                  </Campo>
                )}
                <Campo id="distrito" label="Distrito" value={formData.distrito} onChange={(v) => set("distrito", v)} />
              </div>
            </fieldset>

            <fieldset className="form-fieldset">
              <legend>Datos que usa el modelo {campos?.version ? <span className="muted">· modelo {campos.version}</span> : null}</legend>
              {!campos && !camposError && <div className="muted">Cargando campos del modelo…</div>}
              <div className="form-grid-3">{modelo.map(renderCampoModelo)}</div>
            </fieldset>

            <fieldset className="form-fieldset">
              <legend>Seguimiento del curso (opcional)</legend>
              <div className="form-grid-3">
                {SEGUIMIENTO.map((c) => (
                  <Campo key={c.id} id={c.id} label={c.label}>
                    <input id={`f-${c.id}`} className="form-input" type="number" min={c.min} max={c.max} step={c.step} value={formData[c.id] ?? ""} onChange={(e) => set(c.id, e.target.value)} />
                  </Campo>
                ))}
              </div>
            </fieldset>

            <div style={{ display: "flex", gap: 10, justifyContent: "flex-end", marginTop: 12 }}>
              <button type="button" className="btn-outline-calm" onClick={onClose}>Cancelar</button>
              <button type="submit" className="btn-forest" disabled={loading}>{loading ? "Guardando y prediciendo…" : "Guardar y predecir"}</button>
            </div>
          </form>
        ) : (
          <form onSubmit={handlePasteSubmit}>
            <p style={{ fontSize: 13, color: "#5a7066" }}>
              Copia las filas desde Excel o Google Sheets <strong>con la fila de cabecera</strong> (la columna <code>alumno_id</code> es obligatoria).
              Se aceptan tabuladores, punto y coma o comas.
            </p>
            <textarea className="form-textarea" rows={10} value={pastedText} onChange={(e) => setPastedText(e.target.value)} placeholder="alumno_id	sexo	edad	…" />
            <div style={{ display: "flex", gap: 10, justifyContent: "flex-end", marginTop: 12 }}>
              <button type="button" className="btn-outline-calm" onClick={onClose}>Cancelar</button>
              <button type="submit" className="btn-forest" disabled={loading || !pastedText.trim()}>{loading ? "Importando y prediciendo…" : "Importar y predecir"}</button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
