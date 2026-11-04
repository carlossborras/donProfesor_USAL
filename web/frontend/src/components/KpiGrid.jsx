import React from "react";

export function KpiGrid({ kpis = [] }) {
  return (
    <section className="kpi-row" aria-label="Indicadores de las 5 dimensiones educativas">
      {kpis.map((kpi, idx) => (
        <div className="kpi-card" key={idx}>
          <span className="kpi-label">{kpi.label}</span>
          <span className="kpi-value">{kpi.value}</span>
          <span className="kpi-note">{kpi.note}</span>
        </div>
      ))}
    </section>
  );
}
