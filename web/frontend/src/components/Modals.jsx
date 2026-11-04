import React, { useState, useEffect } from "react";

const DEMO_ACCOUNTS = [
  {
    rol: "docente",
    nombre: "Elena Martín · Tutora de 2º B (I.E. Valle Verde)",
    ambito: "Vista SQL: vista_docente · Grupo ESC-01-2B (Sin rankings ni semáforos)",
  },
  {
    rol: "director",
    nombre: "Carlos Mendoza · Director de Centro (I.E. Valle Verde)",
    ambito: "Vista SQL: vista_director + vista_director_clima · Clima, Cosecha y Recursos",
  },
  {
    rol: "delegado",
    nombre: "Sofía Herrera · Coordinadora Territorial (Red Sur · 12 Escuelas)",
    ambito: "Vista SQL: vista_delegado · Mapa de Conectividad y Simulador de Subvenciones",
  },
];

export function LoginModal({ isOpen, onClose, currentRole, onSelectRole }) {
  const [selectedRole, setSelectedRole] = useState(currentRole || "docente");

  useEffect(() => {
    if (currentRole) setSelectedRole(currentRole);
  }, [currentRole]);

  if (!isOpen) return null;

  const handleConfirm = (e) => {
    e.preventDefault();
    onSelectRole(selectedRole);
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <h3>Autenticación JWT y Control de Acceso por Rol SQL</h3>
        <p>
          Selecciona una cuenta institucional para emitir un token JWT firmado. El backend FastAPI y el Servidor MCP aplicarán los permisos <code>GRANT SELECT</code> exclusivos de la vista SQL correspondiente.
        </p>

        <form onSubmit={handleConfirm}>
          <div className="form-group">
            <label htmlFor="select-jwt-role">Cuenta institucional de demostración</label>
            <select
              id="select-jwt-role"
              className="form-select"
              value={selectedRole}
              onChange={(e) => setSelectedRole(e.target.value)}
            >
              {DEMO_ACCOUNTS.map((acc) => (
                <option key={acc.rol} value={acc.rol}>
                  {acc.nombre}
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label>Permisos SQL que se activarán en el token JWT</label>
            <div className="modal-scope-preview">
              {DEMO_ACCOUNTS.find((a) => a.rol === selectedRole)?.ambito}
            </div>
          </div>

          <div className="modal-actions">
            <button type="button" className="btn-secondary" onClick={onClose}>
              Cancelar
            </button>
            <button type="submit" className="btn-primary">
              Emitir Token JWT y Entrar
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export function ActionModal({ isOpen, alertItem, onClose, onSubmit }) {
  const [decision, setDecision] = useState(
    "Adaptación temporal de entregas durante semanas de cosecha y lluvia"
  );
  const [comment, setComment] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (alertItem) {
      setDecision("Adaptación temporal de entregas durante semanas de cosecha y lluvia");
      setComment("");
    }
  }, [alertItem]);

  if (!isOpen || !alertItem) return null;

  const handleConfirm = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await onSubmit({
        prediccion_id: alertItem.prediccion_id,
        decision_tomada: decision,
        comentario_pedagogico:
          comment.trim() ||
          "Acuerdo revisado y validado bajo criterio profesional docente.",
      });
      onClose();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <h3>Registrar decisión humana ({alertItem.prediccion_id})</h3>
        <p>
          «La decisión es tuya; el modelo puede equivocarse». Documenta el acuerdo pedagógico o descarta el aviso si el contexto directo del aula indica otra prioridad.
        </p>

        <div className="modal-scope-preview" style={{ marginBottom: "14px" }}>
          <strong>{alertItem.titulo_humano}</strong>
          <div style={{ marginTop: "4px", fontSize: "12px", color: "#475569" }}>
            Sugerencia orientativa: {alertItem.recomendacion_pedagogica}
          </div>
        </div>

        <form onSubmit={handleConfirm}>
          <div className="form-group">
            <label htmlFor="select-decision">Decisión profesional adoptada</label>
            <select
              id="select-decision"
              className="form-select"
              value={decision}
              onChange={(e) => setDecision(e.target.value)}
            >
              <option value="Adaptación temporal de entregas durante semanas de cosecha y lluvia">
                Adaptación temporal de entregas durante semanas de cosecha y lluvia
              </option>
              <option value="Contacto dialogado con la familia y entrega de guía modular impresa">
                Contacto dialogado con la familia y entrega de guía modular impresa
              </option>
              <option value="Solicitud de beca de transporte/comedor como factor protector">
                Solicitud de beca de transporte/comedor como factor protector
              </option>
              <option value="Talleres prácticos de co-docencia para uso de equipamiento">
                Talleres prácticos de co-docencia para uso de equipamiento
              </option>
              <option value="Descartar aviso del modelo tras contraste directo en el aula">
                Descartar aviso del modelo tras contraste directo en el aula
              </option>
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="input-comentario">
              Observación contextual del profesional (opcional)
            </label>
            <textarea
              id="input-comentario"
              className="form-textarea"
              rows={3}
              placeholder="Anota los acuerdos alcanzados con la familia, el equipo docente o la coordinación..."
              value={comment}
              onChange={(e) => setComment(e.target.value)}
            />
          </div>

          <div className="modal-actions">
            <button type="button" className="btn-secondary" onClick={onClose}>
              Cancelar
            </button>
            <button type="submit" className="btn-primary" disabled={saving}>
              {saving ? "Guardando..." : "Guardar decisión en Base de Datos"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
