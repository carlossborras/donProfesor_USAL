import React, { useState } from "react";
import { createStudentApi, pasteStudentDataApi } from "../services/api.js";

export function StudentEntryModal({ token, onClose, onSuccess, currentSchoolId, currentGrade }) {
  const [activeTab, setActiveTab] = useState("form"); // "form" | "paste"
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Estado del formulario manual
  const [formData, setFormData] = useState({
    alumno_id: `ALU-${Math.floor(10000 + Math.random() * 90000)}`,
    escuela_id: currentSchoolId || "ESC-01",
    grado_secundaria: currentGrade || 2,
    sexo: "F",
    edad: 14,
    zona_escuela: "Rural",
    distancia_hogar_escuela_km: 3.2,
    tiempo_desplazamiento: "15-30 min",
    tiempo_estudio_semanal: "2-5 h",
    tamano_familia: "Mas de 3",
    internet_hogar: 0,
    horas_trabajo_semanal: 0,
    beneficiario_juntos: 1,
    apoyo_familiar: 1,
    apoyo_escolar: 0,
    dias_lectivos_previstos: 180,
    faltas_trimestre_1: 4,
    faltas_trimestre_2: 12,
    nota_trimestre_1_0_20: 13.5,
    nota_trimestre_2_0_20: 10.5,
  });

  // Estado de pegar datos
  const [pastedText, setPastedText] = useState("");

  const handleChange = (field, value) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const handleFormSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await createStudentApi(token, {
        ...formData,
        edad: parseInt(formData.edad, 10) || 14,
        grado_secundaria: parseInt(formData.grado_secundaria, 10) || 2,
        distancia_hogar_escuela_km: parseFloat(formData.distancia_hogar_escuela_km) || 0,
        horas_trabajo_semanal: parseFloat(formData.horas_trabajo_semanal) || 0,
        internet_hogar: parseInt(formData.internet_hogar, 10) || 0,
        beneficiario_juntos: parseInt(formData.beneficiario_juntos, 10) || 0,
        apoyo_familiar: parseInt(formData.apoyo_familiar, 10) || 0,
        apoyo_escolar: parseInt(formData.apoyo_escolar, 10) || 0,
        faltas_trimestre_1: parseInt(formData.faltas_trimestre_1, 10) || 0,
        faltas_trimestre_2: parseInt(formData.faltas_trimestre_2, 10) || 0,
        nota_trimestre_1_0_20: parseFloat(formData.nota_trimestre_1_0_20) || 12.0,
        nota_trimestre_2_0_20: parseFloat(formData.nota_trimestre_2_0_20) || 12.0,
      });
      onSuccess(res.message || `Estudiante ${formData.alumno_id} registrado correctamente.`);
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
      onSuccess(res.message || "Datos importados y analizados correctamente.");
      onClose();
    } catch (err) {
      setError(err.message || "Error al importar los datos pegados.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose} role="dialog" aria-modal="true">
      <div
        className="modal-card"
        onClick={(e) => e.stopPropagation()}
        style={{ maxWidth: "680px", width: "95%", maxHeight: "90vh", overflowY: "auto" }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
          <div>
            <h3 style={{ margin: 0, fontFamily: "Newsreader, serif", fontSize: "22px", color: "#192823" }}>
              Registrar estudiantes en el aula
            </h3>
            <p style={{ margin: "4px 0 0", fontSize: "13px", color: "#5a7066" }}>
              Introduce los datos de un alumno o pega varias filas directamente desde Excel.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            style={{ background: "transparent", border: "none", fontSize: "20px", cursor: "pointer", color: "#5a7066" }}
          >
            &times;
          </button>
        </div>

        {/* Selector de pestañas */}
        <div style={{ display: "flex", gap: "8px", borderBottom: "1px solid #e7e4dc", marginBottom: "20px" }}>
          <button
            type="button"
            className={`btn-tab ${activeTab === "form" ? "active" : ""}`}
            style={{
              padding: "8px 16px",
              background: "transparent",
              border: "none",
              borderBottom: activeTab === "form" ? "2px solid #1f6351" : "2px solid transparent",
              fontWeight: activeTab === "form" ? 600 : 400,
              color: activeTab === "form" ? "#1f6351" : "#5a7066",
              cursor: "pointer",
              fontSize: "13.5px",
            }}
            onClick={() => setActiveTab("form")}
          >
            Ficha individual de estudiante
          </button>
          <button
            type="button"
            className={`btn-tab ${activeTab === "paste" ? "active" : ""}`}
            style={{
              padding: "8px 16px",
              background: "transparent",
              border: "none",
              borderBottom: activeTab === "paste" ? "2px solid #1f6351" : "2px solid transparent",
              fontWeight: activeTab === "paste" ? 600 : 400,
              color: activeTab === "paste" ? "#1f6351" : "#5a7066",
              cursor: "pointer",
              fontSize: "13.5px",
            }}
            onClick={() => setActiveTab("paste")}
          >
            Pegar tabla (Excel / CSV)
          </button>
        </div>

        {error && (
          <div style={{ background: "#fef2f2", color: "#991b1b", padding: "10px 14px", borderRadius: "6px", marginBottom: "16px", fontSize: "13px" }}>
            {error}
          </div>
        )}

        {/* PESTAÑA 1: FORMULARIO INDIVIDUAL */}
        {activeTab === "form" && (
          <form onSubmit={handleFormSubmit}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", marginBottom: "16px" }}>
              <div className="form-group">
                <label style={{ fontSize: "12px", fontWeight: 600, color: "#1c2a24", display: "block", marginBottom: "4px" }}>
                  Código o Identificador
                </label>
                <input
                  type="text"
                  className="form-input"
                  style={{ width: "100%", padding: "8px 10px", borderRadius: "6px", border: "1px solid #dcd8cf" }}
                  value={formData.alumno_id}
                  onChange={(e) => handleChange("alumno_id", e.target.value)}
                  required
                />
              </div>

              <div className="form-group">
                <label style={{ fontSize: "12px", fontWeight: 600, color: "#1c2a24", display: "block", marginBottom: "4px" }}>
                  Grado de Secundaria
                </label>
                <select
                  className="form-select"
                  style={{ width: "100%", padding: "8px 10px", borderRadius: "6px", border: "1px solid #dcd8cf" }}
                  value={formData.grado_secundaria}
                  onChange={(e) => handleChange("grado_secundaria", e.target.value)}
                >
                  <option value={1}>1º de Secundaria</option>
                  <option value={2}>2º de Secundaria</option>
                  <option value={3}>3º de Secundaria</option>
                  <option value={4}>4º de Secundaria</option>
                  <option value={5}>5º de Secundaria</option>
                </select>
              </div>

              <div className="form-group">
                <label style={{ fontSize: "12px", fontWeight: 600, color: "#1c2a24", display: "block", marginBottom: "4px" }}>
                  Sexo
                </label>
                <select
                  className="form-select"
                  style={{ width: "100%", padding: "8px 10px", borderRadius: "6px", border: "1px solid #dcd8cf" }}
                  value={formData.sexo}
                  onChange={(e) => handleChange("sexo", e.target.value)}
                >
                  <option value="F">Femenino</option>
                  <option value="M">Masculino</option>
                </select>
              </div>

              <div className="form-group">
                <label style={{ fontSize: "12px", fontWeight: 600, color: "#1c2a24", display: "block", marginBottom: "4px" }}>
                  Edad
                </label>
                <input
                  type="number"
                  min="11"
                  max="20"
                  className="form-input"
                  style={{ width: "100%", padding: "8px 10px", borderRadius: "6px", border: "1px solid #dcd8cf" }}
                  value={formData.edad}
                  onChange={(e) => handleChange("edad", e.target.value)}
                />
              </div>
            </div>

            <div style={{ borderTop: "1px solid #e7e4dc", paddingTop: "14px", marginBottom: "16px" }}>
              <div style={{ fontSize: "11px", fontWeight: 600, color: "#1f6351", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "12px" }}>
                Contexto escolar y desplazamiento
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
                <div className="form-group">
                  <label style={{ fontSize: "12px", fontWeight: 600, color: "#1c2a24", display: "block", marginBottom: "4px" }}>
                    Distancia hogar-escuela (km)
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    className="form-input"
                    style={{ width: "100%", padding: "8px 10px", borderRadius: "6px", border: "1px solid #dcd8cf" }}
                    value={formData.distancia_hogar_escuela_km}
                    onChange={(e) => handleChange("distancia_hogar_escuela_km", e.target.value)}
                  />
                </div>

                <div className="form-group">
                  <label style={{ fontSize: "12px", fontWeight: 600, color: "#1c2a24", display: "block", marginBottom: "4px" }}>
                    Tiempo de desplazamiento
                  </label>
                  <select
                    className="form-select"
                    style={{ width: "100%", padding: "8px 10px", borderRadius: "6px", border: "1px solid #dcd8cf" }}
                    value={formData.tiempo_desplazamiento}
                    onChange={(e) => handleChange("tiempo_desplazamiento", e.target.value)}
                  >
                    <option value="Menos de 15 min">Menos de 15 min</option>
                    <option value="15-30 min">15-30 min</option>
                    <option value="30-60 min">30-60 min</option>
                    <option value="Mas de 60 min">Más de 60 min</option>
                  </select>
                </div>

                <div className="form-group">
                  <label style={{ fontSize: "12px", fontWeight: 600, color: "#1c2a24", display: "block", marginBottom: "4px" }}>
                    Internet en el hogar
                  </label>
                  <select
                    className="form-select"
                    style={{ width: "100%", padding: "8px 10px", borderRadius: "6px", border: "1px solid #dcd8cf" }}
                    value={formData.internet_hogar}
                    onChange={(e) => handleChange("internet_hogar", e.target.value)}
                  >
                    <option value={1}>Sí tiene internet</option>
                    <option value={0}>No tiene internet</option>
                  </select>
                </div>

                <div className="form-group">
                  <label style={{ fontSize: "12px", fontWeight: 600, color: "#1c2a24", display: "block", marginBottom: "4px" }}>
                    Beneficiario Programa Juntos
                  </label>
                  <select
                    className="form-select"
                    style={{ width: "100%", padding: "8px 10px", borderRadius: "6px", border: "1px solid #dcd8cf" }}
                    value={formData.beneficiario_juntos}
                    onChange={(e) => handleChange("beneficiario_juntos", e.target.value)}
                  >
                    <option value={1}>Sí, beneficiario</option>
                    <option value={0}>No recibe subsidio</option>
                  </select>
                </div>

                <div className="form-group">
                  <label style={{ fontSize: "12px", fontWeight: 600, color: "#1c2a24", display: "block", marginBottom: "4px" }}>
                    Horas de trabajo semanal fuera de clase
                  </label>
                  <input
                    type="number"
                    step="0.5"
                    min="0"
                    className="form-input"
                    style={{ width: "100%", padding: "8px 10px", borderRadius: "6px", border: "1px solid #dcd8cf" }}
                    value={formData.horas_trabajo_semanal}
                    onChange={(e) => handleChange("horas_trabajo_semanal", e.target.value)}
                  />
                </div>

                <div className="form-group">
                  <label style={{ fontSize: "12px", fontWeight: 600, color: "#1c2a24", display: "block", marginBottom: "4px" }}>
                    Zona de la escuela
                  </label>
                  <select
                    className="form-select"
                    style={{ width: "100%", padding: "8px 10px", borderRadius: "6px", border: "1px solid #dcd8cf" }}
                    value={formData.zona_escuela}
                    onChange={(e) => handleChange("zona_escuela", e.target.value)}
                  >
                    <option value="Rural">Rural</option>
                    <option value="Urbana">Urbana</option>
                  </select>
                </div>
              </div>
            </div>

            <div style={{ borderTop: "1px solid #e7e4dc", paddingTop: "14px", marginBottom: "20px" }}>
              <div style={{ fontSize: "11px", fontWeight: 600, color: "#1f6351", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "12px" }}>
                Asistencia y Calificaciones (Escala vigesimal 0-20)
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: "12px" }}>
                <div className="form-group">
                  <label style={{ fontSize: "11.5px", fontWeight: 600, color: "#1c2a24", display: "block", marginBottom: "4px" }}>
                    Faltas T1
                  </label>
                  <input
                    type="number"
                    min="0"
                    className="form-input"
                    style={{ width: "100%", padding: "8px 8px", borderRadius: "6px", border: "1px solid #dcd8cf" }}
                    value={formData.faltas_trimestre_1}
                    onChange={(e) => handleChange("faltas_trimestre_1", e.target.value)}
                  />
                </div>

                <div className="form-group">
                  <label style={{ fontSize: "11.5px", fontWeight: 600, color: "#1c2a24", display: "block", marginBottom: "4px" }}>
                    Faltas T2
                  </label>
                  <input
                    type="number"
                    min="0"
                    className="form-input"
                    style={{ width: "100%", padding: "8px 8px", borderRadius: "6px", border: "1px solid #dcd8cf" }}
                    value={formData.faltas_trimestre_2}
                    onChange={(e) => handleChange("faltas_trimestre_2", e.target.value)}
                  />
                </div>

                <div className="form-group">
                  <label style={{ fontSize: "11.5px", fontWeight: 600, color: "#1c2a24", display: "block", marginBottom: "4px" }}>
                    Nota T1 (0-20)
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    max="20"
                    className="form-input"
                    style={{ width: "100%", padding: "8px 8px", borderRadius: "6px", border: "1px solid #dcd8cf" }}
                    value={formData.nota_trimestre_1_0_20}
                    onChange={(e) => handleChange("nota_trimestre_1_0_20", e.target.value)}
                  />
                </div>

                <div className="form-group">
                  <label style={{ fontSize: "11.5px", fontWeight: 600, color: "#1c2a24", display: "block", marginBottom: "4px" }}>
                    Nota T2 (0-20)
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    max="20"
                    className="form-input"
                    style={{ width: "100%", padding: "8px 8px", borderRadius: "6px", border: "1px solid #dcd8cf" }}
                    value={formData.nota_trimestre_2_0_20}
                    onChange={(e) => handleChange("nota_trimestre_2_0_20", e.target.value)}
                  />
                </div>
              </div>
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "20px" }}>
              <button type="button" className="btn-outline-calm" onClick={onClose} disabled={loading}>
                Cancelar
              </button>
              <button type="submit" className="btn-forest" disabled={loading} style={{ padding: "9px 20px" }}>
                {loading ? "Analizando y guardando..." : "Guardar estudiante"}
              </button>
            </div>
          </form>
        )}

        {/* PESTAÑA 2: PEGAR TABLA */}
        {activeTab === "paste" && (
          <form onSubmit={handlePasteSubmit}>
            <p style={{ fontSize: "13px", color: "#4e5d55", marginBottom: "10px", lineHeight: "1.5" }}>
              Puedes copiar y pegar filas directamente desde Microsoft Excel o Google Sheets. El sistema detectará las columnas automáticamente y aplicará el modelo predictivo:
            </p>

            <textarea
              rows={8}
              style={{
                width: "100%",
                padding: "10px",
                borderRadius: "6px",
                border: "1px solid #dcd8cf",
                fontFamily: "monospace",
                fontSize: "12px",
                lineHeight: "1.4",
                boxSizing: "border-box",
                marginBottom: "14px",
              }}
              placeholder={`alumno_id\tsexo\tedad\tgrado_secundaria\tdistancia_hogar_escuela_km\tfaltas_trimestre_1\tfaltas_trimestre_2\tnota_trimestre_1_0_20\tnota_trimestre_2_0_20\nALU-9901\tF\t15\t3\t4.5\t2\t8\t14.0\t11.5`}
              value={pastedText}
              onChange={(e) => setPastedText(e.target.value)}
              required
            />

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px" }}>
              <button type="button" className="btn-outline-calm" onClick={onClose} disabled={loading}>
                Cancelar
              </button>
              <button type="submit" className="btn-forest" disabled={loading || !pastedText.trim()} style={{ padding: "9px 20px" }}>
                {loading ? "Procesando estudiantes..." : "Procesar y guardar"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
