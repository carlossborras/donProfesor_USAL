import React, { useState } from "react";

export function RainHarvestChart({ serie = [], role = "director" }) {
  const [hoveredIdx, setHoveredIdx] = useState(null);

  const width = 780;
  const height = 225;
  const startX = 52;
  const stepX = 60;

  const titleText =
    role === "director"
      ? "Gráfica Estrella de Dirección: Asistencia superpuesta con lluvia (mm), cosecha y uso de recursos"
      : "Seguimiento del centro y aula: Asistencia frente a lluvia y semanas de cosecha";

  const attPoints = serie
    .map((s, idx) => {
      const x = startX + idx * stepX;
      const y = Math.round(175 - ((s.asistencia_semanal_pct - 60) / 40.0) * 135);
      return `${x},${y}`;
    })
    .join(" ");

  const resPoints = serie
    .map((s, idx) => {
      const x = startX + idx * stepX;
      const y = Math.round(175 - ((s.uso_recursos_semanal_pct - 30) / 70.0) * 135);
      return `${x},${y}`;
    })
    .join(" ");

  const hoveredItem = hoveredIdx !== null && serie[hoveredIdx] ? serie[hoveredIdx] : null;

  return (
    <div className="panel-card">
      <div className="panel-header">
        <div>
          <h2>{titleText}</h2>
          <p>
            Superpone la tasa de asistencia semanal (línea azul), el uso de recursos didácticos (línea verde), la lluvia en milímetros (barras grises) y las semanas de cosecha (franja ámbar).
          </p>
        </div>
        <span className="badge-neutral">Vista SQL: vista_director_clima</span>
      </div>

      <div className="chart-box">
        <div className="legend-row">
          <div className="legend-entry">
            <span className="legend-swatch" style={{ background: "#2563eb" }} />
            <span>Asistencia semanal (%)</span>
          </div>
          <div className="legend-entry">
            <span className="legend-swatch" style={{ background: "#0d9488" }} />
            <span>Utilización de recursos del centro (%)</span>
          </div>
          <div className="legend-entry">
            <span className="legend-swatch" style={{ background: "#94a3b8" }} />
            <span>Precipitación pluvial semanal (mm)</span>
          </div>
          <div className="legend-entry">
            <span
              className="legend-swatch"
              style={{ background: "#fef3c7", border: "1px solid #fde68a" }}
            />
            <span>Temporada de cosecha comarcal (Semanas 5 a 8)</span>
          </div>
        </div>

        {hoveredItem && (
          <div className="chart-tooltip-banner">
            <strong>{hoveredItem.etiqueta_semana}:</strong> Asistencia{" "}
            <strong>{hoveredItem.asistencia_semanal_pct}%</strong> · Lluvia{" "}
            <strong>{hoveredItem.mm_lluvia} mm</strong> · Uso de recursos{" "}
            <strong>{hoveredItem.uso_recursos_semanal_pct}%</strong> ·{" "}
            {hoveredItem.es_semana_cosecha === 1
              ? "Periodo activo de cosecha comarcal"
              : "Semana lectiva ordinaria"}
          </div>
        )}

        <svg
          viewBox={`0 0 ${width} ${height}`}
          width="100%"
          height="225"
          style={{ background: "#ffffff", border: "1px solid #e2e8f0", borderRadius: "8px" }}
        >
          <rect
            x={startX + 4 * stepX - 24}
            y="18"
            width={stepX * 3 + 48}
            height="157"
            fill="#fffbeb"
            stroke="#fde68a"
          />
          <text x={startX + 4 * stepX - 14} y="34" fontSize="10.5" fontWeight="600" fill="#92400e">
            Semanas de Cosecha Comarcal (Sem 5 a 8)
          </text>

          {serie.map((s, idx) => {
            const x = startX + idx * stepX;
            const barH = Math.round((s.mm_lluvia / 90.0) * 140);
            const y = 175 - barH;
            const barColor = s.es_semana_cosecha === 1 ? "#94a3b8" : "#cbd5e1";
            return (
              <g
                key={s.semana_num || idx}
                onMouseEnter={() => setHoveredIdx(idx)}
                style={{ cursor: "pointer" }}
              >
                <rect x={x - 11} y={y} width="22" height={barH} fill={barColor} rx="2" />
                <text x={x} y={y - 4} textAnchor="middle" fontSize="9.5" fill="#64748b">
                  {s.mm_lluvia}mm
                </text>
              </g>
            );
          })}

          <polyline
            fill="none"
            stroke="#0d9488"
            strokeWidth="2.2"
            strokeDasharray="5,3"
            points={resPoints}
          />
          <polyline fill="none" stroke="#2563eb" strokeWidth="3" points={attPoints} />

          {serie.map((s, idx) => {
            const x = startX + idx * stepX;
            const y = Math.round(175 - ((s.asistencia_semanal_pct - 60) / 40.0) * 135);
            return (
              <circle
                key={`pt-${idx}`}
                cx={x}
                cy={y}
                r={hoveredIdx === idx ? 6 : 4}
                fill={s.es_semana_cosecha === 1 ? "#b45309" : "#2563eb"}
                onMouseEnter={() => setHoveredIdx(idx)}
                style={{ cursor: "pointer" }}
              />
            );
          })}

          <text
            x={startX + 5 * stepX + 8}
            y="146"
            fontSize="10.5"
            fontWeight="600"
            fill="#92400e"
          >
            Mínimo 72,4% (Lluvia 82mm + Cosecha)
          </text>

          <text
            x={startX + 8 * stepX - 10}
            y="52"
            fontSize="10.5"
            fontWeight="600"
            fill="#0f766e"
          >
            Recuperación (91,8%) con guías offline y becas
          </text>

          {serie.map((s, idx) => {
            const x = startX + idx * stepX;
            const parts = (s.etiqueta_semana || "").split(" ");
            return (
              <text
                key={`lbl-${idx}`}
                x={x}
                y="198"
                textAnchor="middle"
                fontSize="10.5"
                fill="#475569"
                fontWeight="500"
              >
                {parts[0]} {parts[1] || ""}
              </text>
            );
          })}
        </svg>
      </div>
    </div>
  );
}
