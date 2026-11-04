import React from "react";

export function PredictiveAlertsPanel({ alerts = [], onOpenActionModal }) {
  return (
    <div className="panel-card">
      <div className="panel-header">
        <div>
          <h2>Situaciones prioritarias de acompañamiento (Modelo Predictivo · 7 variables)</h2>
          <p>
            Alertas generadas a partir de las estimaciones del modelo (probabilidad de abandono, nota T3 proyectada, faltas T3 y subsidio Juntos).
          </p>
        </div>
        <span className="badge-neutral">{alerts.length} observaciones registradas</span>
      </div>

      <div className="alerts-container">
        {alerts.length === 0 ? (
          <div style={{ padding: "26px 16px", textAlign: "center", color: "#64748b" }}>
            <div style={{ fontSize: "14px", fontWeight: 600, color: "#334155", marginBottom: "4px" }}>
              Base de datos en espera de alertas predictivas
            </div>
            <div style={{ fontSize: "12.5px" }}>
              Actualmente no hay estudiantes con alertas predictivas en la base de datos real. Cuando se ejecute el modelo de Persona 2 o se cargue el CSV con predicciones, se listarán automáticamente aquí.
            </div>
          </div>
        ) : (
          alerts.map((item) => {
            const isDone =
              item.estado_revision === "Acuerdo registrado" || item.estado_revision === "Verificado";
            const scopeLabel = item.codigo_seguimiento || item.prediccion_id;

            return (
              <div className="alert-card" key={item.prediccion_id}>
                <div className="alert-top">
                  <div>
                    <div className="alert-title">{item.titulo_humano}</div>
                    <div className="alert-meta-sub">
                      Estudiante: <strong>{scopeLabel}</strong> · Grado: <strong>{item.grado_id || "2º Sec"}</strong>
                    </div>
                  </div>
                  <span className={`tag-context ${isDone ? "tag-status-done" : ""}`}>
                    {item.categoria_contexto}
                  </span>
                </div>

                <p className="alert-body">{item.descripcion_situacion}</p>

                <div className="factors-block">
                  <span className="factors-heading">
                    Factores que orientan esta observación del modelo
                  </span>
                  <div className="factors-list">
                    <span className="factor-item">
                      1. {item.factor_1_texto} <span className="factor-weight">({item.factor_1_peso}%)</span>
                    </span>
                    <span className="factor-item">
                      2. {item.factor_2_texto}
                    </span>
                    <span className="factor-item">
                      3. {item.factor_3_texto}
                    </span>
                  </div>
                </div>

                <div className="alert-footer">
                  <span className="recommendation-text">
                    Orientación sugerida: {item.recomendacion_pedagogica}
                  </span>
                  <button
                    type="button"
                    className="btn-primary"
                    onClick={() => onOpenActionModal(item)}
                  >
                    Revisar / {item.accion_sugerida_boton || "Registrar acuerdo"}
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
