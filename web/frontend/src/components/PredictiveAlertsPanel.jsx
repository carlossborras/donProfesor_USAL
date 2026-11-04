import React from "react";

export function PredictiveAlertsPanel({ alerts = [], onOpenActionModal }) {
  return (
    <div className="panel-card">
      <div className="panel-header">
        <div>
          <h2>Situaciones prioritarias de acompañamiento (Modelo Predictivo)</h2>
          <p>
            Observaciones generadas a partir de los 3 factores de contexto que más pesan, sin clasificaciones automáticas.
          </p>
        </div>
        <span className="badge-neutral">{alerts.length} observaciones del modelo</span>
      </div>

      <div className="alerts-container">
        {alerts.map((item) => {
          const isDone =
            item.estado_revision === "Acuerdo registrado" || item.estado_revision === "Verificado";
          const scopeLabel = item.codigo_seguimiento || item.grupo_id || item.escuela_id;

          return (
            <div className="alert-card" key={item.prediccion_id}>
              <div className="alert-top">
                <div>
                  <div className="alert-title">{item.titulo_humano}</div>
                  <div className="alert-meta-sub">
                    Ámbito: <strong>{scopeLabel}</strong> · Estado: <strong>{item.estado_revision}</strong>
                  </div>
                </div>
                <span className={`tag-context ${isDone ? "tag-status-done" : ""}`}>
                  {item.categoria_contexto}
                </span>
              </div>

              <p className="alert-body">{item.descripcion_situacion}</p>

              <div className="factors-block">
                <span className="factors-heading">
                  Los 3 factores que más pesan en esta observación del modelo
                </span>
                <div className="factors-list">
                  <span className="factor-item">
                    1. {item.factor_1_texto} <span className="factor-weight">({item.factor_1_peso}%)</span>
                  </span>
                  <span className="factor-item">
                    2. {item.factor_2_texto} <span className="factor-weight">({item.factor_2_peso}%)</span>
                  </span>
                  <span className="factor-item">
                    3. {item.factor_3_texto} <span className="factor-weight">({item.factor_3_peso}%)</span>
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
                  Revisar / {item.accion_sugerida_boton}
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
